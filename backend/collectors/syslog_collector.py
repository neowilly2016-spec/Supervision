#!/usr/bin/env python3
"""
Syslog Collector - Performance Edition  
Centralized syslog collection and parsing for Juniper and Huawei devices

Supported vendors:
- Juniper MX/NE series
- Huawei NE series
"""

import logging
import socketserver
import psycopg2
import re
import os
from datetime import datetime
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Syslog severity levels (RFC 5424)
SEVERITY_MAP = {
    0: 'emergency',
    1: 'alert',
    2: 'critical',
    3: 'error',
    4: 'warning',
    5: 'notice',
    6: 'informational',
    7: 'debug'
}

# Facility map
FACILITY_MAP = {
    0: 'kernel',
    1: 'user',
    16: 'local0',
    17: 'local1',
    18: 'local2',
    19: 'local3',
    20: 'local4',
    21: 'local5',
    22: 'local6',
    23: 'local7'
}

class SyslogParser:
    """Parse syslog messages from different vendors"""
    
    # Juniper syslog pattern
    # Example: <14>Jun 23 13:00:00 mx960-algiers rpd[1234]: RPD_BGP_NEIGHBOR_STATE_CHANGED: BGP peer 10.0.0.1 changed state from Established to Active
    JUNIPER_PATTERN = re.compile(
        r'<(\d+)>(\w+\s+\d+\s+\d+:\d+:\d+)\s+(\S+)\s+(\S+):\s+(.+)'
    )
    
    # Huawei syslog pattern  
    # Example: <165>Jun 23 13:00:00 2026 ne9000-oran %%01BGP/4/NBR_CHG(l): Neighbor 10.0.0.1 changed from Established to Idle
    HUAWEI_PATTERN = re.compile(
        r'<(\d+)>(\w+\s+\d+\s+\d+:\d+:\d+)\s+(\d+)\s+(\S+)\s+%%(.+)'
    )
    
    @staticmethod
    def parse_priority(priority):
        """Extract facility and severity from priority"""
        facility = priority // 8
        severity = priority % 8
        return facility, severity
    
    @staticmethod
    def parse_juniper(message):
        """Parse Juniper syslog message"""
        match = SyslogParser.JUNIPER_PATTERN.match(message)
        if not match:
            return None
        
        priority, timestamp, hostname, process, content = match.groups()
        facility, severity = SyslogParser.parse_priority(int(priority))
        
        return {
            'vendor': 'juniper',
            'hostname': hostname,
            'timestamp': timestamp,
            'facility': FACILITY_MAP.get(facility, str(facility)),
            'severity': SEVERITY_MAP.get(severity, str(severity)),
            'severity_level': severity,
            'process': process,
            'message': content,
            'raw_message': message
        }
    
    @staticmethod
    def parse_huawei(message):
        """Parse Huawei syslog message"""
        match = SyslogParser.HUAWEI_PATTERN.match(message)
        if not match:
            return None
        
        priority, timestamp, year, hostname, content = match.groups()
        facility, severity = SyslogParser.parse_priority(int(priority))
        
        return {
            'vendor': 'huawei',
            'hostname': hostname,
            'timestamp': f"{timestamp} {year}",
            'facility': FACILITY_MAP.get(facility, str(facility)),
            'severity': SEVERITY_MAP.get(severity, str(severity)),
            'severity_level': severity,
            'process': 'huawei',
            'message': content,
            'raw_message': message
        }
    
    @staticmethod
    def parse(message):
        """Parse syslog message - auto-detect vendor"""
        # Try Juniper first
        parsed = SyslogParser.parse_juniper(message)
        if parsed:
            return parsed
        
        # Try Huawei
        parsed = SyslogParser.parse_huawei(message)
        if parsed:
            return parsed
        
        # Generic fallback
        return {
            'vendor': 'unknown',
            'hostname': 'unknown',
            'timestamp': datetime.now().strftime('%b %d %H:%M:%S'),
            'facility': 'unknown',
            'severity': 'unknown',
            'severity_level': 7,
            'process': 'unknown',
            'message': message,
            'raw_message': message
        }

class SyslogHandler(socketserver.BaseRequestHandler):
    """Handle incoming syslog messages"""
    
    def handle(self):
        """Process syslog message"""
        try:
            data = self.request[0].strip().decode('utf-8')
            client_ip = self.client_address[0]
            
            # Parse message
            parsed = SyslogParser.parse(data)
            parsed['source_ip'] = client_ip
            
            # Log to console
            logger.info(f"[{parsed['hostname']}] {parsed['severity']}: {parsed['message']}")
            
            # Store in database
            self.server.store_syslog(parsed)
            
        except Exception as e:
            logger.error(f"Error processing syslog: {e}")

class SyslogCollector:
    """Syslog collector server"""
    
    def __init__(self):
        self.db_conn = None
        self.host = os.getenv('SYSLOG_HOST', '0.0.0.0')
        self.port = int(os.getenv('SYSLOG_PORT', 514))
        
    def connect_db(self):
        """Connect to TimescaleDB"""
        try:
            self.db_conn = psycopg2.connect(
                host=os.getenv('TIMESCALE_HOST', 'timescaledb'),
                port=os.getenv('TIMESCALE_PORT', 5432),
                database=os.getenv('TIMESCALE_DB', 'supervision'),
                user=os.getenv('TIMESCALE_USER', 'postgres'),
                password=os.getenv('TIMESCALE_PASSWORD', 'postgres')
            )
            logger.info("Connected to TimescaleDB")
        except Exception as e:
            logger.error(f"DB connection failed: {e}")
            raise
    
    def store_syslog(self, parsed):
        """Store syslog message in database"""
        if not self.db_conn:
            self.connect_db()
        
        cursor = self.db_conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO syslog_messages (
                    time, source_ip, hostname, vendor, facility, severity, severity_level,
                    process, message, raw_message
                ) VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                parsed['source_ip'],
                parsed['hostname'],
                parsed['vendor'],
                parsed['facility'],
                parsed['severity'],
                parsed['severity_level'],
                parsed['process'],
                parsed['message'],
                parsed['raw_message']
            ))
            self.db_conn.commit()
            
            # Trigger alerts for critical messages
            if parsed['severity_level'] <= 2:  # emergency, alert, critical
                self.trigger_alert(parsed)
                
        except Exception as e:
            logger.error(f"Failed to store syslog: {e}")
            self.db_conn.rollback()
        finally:
            cursor.close()
    
    def trigger_alert(self, parsed):
        """Trigger alert for critical syslog messages"""
        logger.warning(f"CRITICAL ALERT from {parsed['hostname']}: {parsed['message']}")
        
        # Store alert in alerts table
        cursor = self.db_conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO alerts (
                    time, device_hostname, alert_type, severity, message, acknowledged
                ) VALUES (NOW(), %s, 'syslog', %s, %s, false)
            """, (
                parsed['hostname'],
                parsed['severity'],
                parsed['message']
            ))
            self.db_conn.commit()
        except Exception as e:
            logger.error(f"Failed to create alert: {e}")
            self.db_conn.rollback()
        finally:
            cursor.close()
    
    def run(self):
        """Start syslog server"""
        logger.info(f"Starting Syslog collector on {self.host}:{self.port}")
        
        # Connect to database
        self.connect_db()
        
        # Create UDP server
        server = socketserver.UDPServer((self.host, self.port), SyslogHandler)
        server.store_syslog = self.store_syslog
        
        try:
            logger.info("Syslog collector ready")
            server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Stopping syslog collector")
            server.shutdown()

if __name__ == '__main__':
    collector = SyslogCollector()
    collector.run()

#!/usr/bin/env python3
"""
BGP Collector - Performance Edition
Collects BGP session state and metrics via SNMP from Juniper and Huawei routers

Supported vendors:
- Juniper MX/NE series
- Huawei NE series
"""

import logging
import psycopg2
import time
from pysnmp.hlapi import *
from datetime import datetime
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# BGP4-MIB OIDs (RFC 4273)
BGP_PEER_TABLE = '1.3.6.1.2.1.15.3.1'
BGP_PEER_STATE = '1.3.6.1.2.1.15.3.1.2'  # bgpPeerState
BGP_PEER_ADMIN_STATUS = '1.3.6.1.2.1.15.3.1.3'  # bgpPeerAdminStatus
BGP_PEER_REMOTE_AS = '1.3.6.1.2.1.15.3.1.9'  # bgpPeerRemoteAs
BGP_PEER_IN_UPDATES = '1.3.6.1.2.1.15.3.1.10'  # bgpPeerInUpdates
BGP_PEER_OUT_UPDATES = '1.3.6.1.2.1.15.3.1.11'  # bgpPeerOutUpdates
BGP_PEER_IN_TOTAL_MESSAGES = '1.3.6.1.2.1.15.3.1.12'  # bgpPeerInTotalMessages
BGP_PEER_OUT_TOTAL_MESSAGES = '1.3.6.1.2.1.15.3.1.13'  # bgpPeerOutTotalMessages
BGP_PEER_LAST_ERROR = '1.3.6.1.2.1.15.3.1.14'  # bgpPeerLastError
BGP_PEER_FSM_ESTABLISHED_TRANSITIONS = '1.3.6.1.2.1.15.3.1.15'  # bgpPeerFsmEstablishedTransitions
BGP_PEER_FSM_ESTABLISHED_TIME = '1.3.6.1.2.1.15.3.1.16'  # bgpPeerFsmEstablishedTime
BGP_PEER_IN_UPDATE_ELAPSED_TIME = '1.3.6.1.2.1.15.3.1.24'  # bgpPeerInUpdateElapsedTime

BGP_STATE_MAP = {
    1: 'idle',
    2: 'connect',
    3: 'active',
    4: 'opensent',
    5: 'openconfirm',
    6: 'established'
}

class BGPCollector:
    def __init__(self):
        self.db_conn = None
        self.community = os.getenv('SNMP_COMMUNITY', 'public')
        
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
    
    def snmp_walk(self, device_ip, oid):
        """Perform SNMP walk on device"""
        results = []
        try:
            for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
                SnmpEngine(),
                CommunityData(self.community, mpModel=1),  # SNMPv2c
                UdpTransportTarget((device_ip, 161), timeout=5, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False
            ):
                if errorIndication or errorStatus:
                    break
                for varBind in varBinds:
                    results.append(varBind)
            return results
        except Exception as e:
            logger.error(f"SNMP walk failed for {device_ip}: {e}")
            return []
    
    def snmp_get(self, device_ip, oid):
        """Perform SNMP GET"""
        try:
            errorIndication, errorStatus, errorIndex, varBinds = next(
                getCmd(
                    SnmpEngine(),
                    CommunityData(self.community, mpModel=1),
                    UdpTransportTarget((device_ip, 161), timeout=5, retries=2),
                    ContextData(),
                    ObjectType(ObjectIdentity(oid))
                )
            )
            if not errorIndication and not errorStatus:
                return varBinds[0][1]
            return None
        except Exception as e:
            logger.error(f"SNMP GET failed for {device_ip}: {e}")
            return None
    
    def collect_bgp_sessions(self, device):
        """Collect BGP session information"""
        device_ip = device['device_ip']
        hostname = device.get('hostname', device_ip)
        
        logger.info(f"Collecting BGP sessions from {hostname} ({device_ip})")
        
        # Get BGP peer states
        peer_states = self.snmp_walk(device_ip, BGP_PEER_STATE)
        
        bgp_sessions = []
        for peer in peer_states:
            # Extract peer IP from OID
            oid_parts = str(peer[0]).split('.')
            peer_ip = '.'.join(oid_parts[-4:])
            
            # Get peer state
            state_value = int(peer[1])
            state = BGP_STATE_MAP.get(state_value, 'unknown')
            
            # Get additional metrics
            remote_as = self.snmp_get(device_ip, f"{BGP_PEER_REMOTE_AS}.{peer_ip}")
            in_updates = self.snmp_get(device_ip, f"{BGP_PEER_IN_UPDATES}.{peer_ip}")
            out_updates = self.snmp_get(device_ip, f"{BGP_PEER_OUT_UPDATES}.{peer_ip}")
            in_total_msgs = self.snmp_get(device_ip, f"{BGP_PEER_IN_TOTAL_MESSAGES}.{peer_ip}")
            out_total_msgs = self.snmp_get(device_ip, f"{BGP_PEER_OUT_TOTAL_MESSAGES}.{peer_ip}")
            fsm_established_transitions = self.snmp_get(device_ip, f"{BGP_PEER_FSM_ESTABLISHED_TRANSITIONS}.{peer_ip}")
            fsm_established_time = self.snmp_get(device_ip, f"{BGP_PEER_FSM_ESTABLISHED_TIME}.{peer_ip}")
            
            session = {
                'device_ip': device_ip,
                'device_hostname': hostname,
                'peer_ip': peer_ip,
                'peer_as': int(remote_as) if remote_as else None,
                'state': state,
                'in_updates': int(in_updates) if in_updates else 0,
                'out_updates': int(out_updates) if out_updates else 0,
                'in_total_messages': int(in_total_msgs) if in_total_msgs else 0,
                'out_total_messages': int(out_total_msgs) if out_total_msgs else 0,
                'fsm_established_transitions': int(fsm_established_transitions) if fsm_established_transitions else 0,
                'uptime_seconds': int(fsm_established_time) if fsm_established_time else 0
            }
            bgp_sessions.append(session)
            logger.debug(f"BGP peer: {peer_ip} AS{session['peer_as']} state={state}")
        
        return bgp_sessions
    
    def store_bgp_metrics(self, sessions):
        """Store BGP metrics in TimescaleDB"""
        if not self.db_conn:
            self.connect_db()
        
        cursor = self.db_conn.cursor()
        try:
            for session in sessions:
                cursor.execute("""
                    INSERT INTO bgp_sessions (
                        time, device_ip, device_hostname, peer_ip, peer_as, state,
                        in_updates, out_updates, in_total_messages, out_total_messages,
                        fsm_established_transitions, uptime_seconds
                    ) VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    session['device_ip'],
                    session['device_hostname'],
                    session['peer_ip'],
                    session['peer_as'],
                    session['state'],
                    session['in_updates'],
                    session['out_updates'],
                    session['in_total_messages'],
                    session['out_total_messages'],
                    session['fsm_established_transitions'],
                    session['uptime_seconds']
                ))
            self.db_conn.commit()
            logger.info(f"Stored {len(sessions)} BGP sessions")
        except Exception as e:
            logger.error(f"Failed to store BGP metrics: {e}")
            self.db_conn.rollback()
        finally:
            cursor.close()
    
    def get_devices(self):
        """Get list of devices from database"""
        if not self.db_conn:
            self.connect_db()
        
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT device_ip, hostname FROM devices WHERE status = 'active'")
        devices = [{'device_ip': row[0], 'hostname': row[1]} for row in cursor.fetchall()]
        cursor.close()
        return devices
    
    def run(self, interval=300):
        """Main collection loop"""
        logger.info(f"Starting BGP collector (interval: {interval}s)")
        
        while True:
            try:
                devices = self.get_devices()
                logger.info(f"Polling {len(devices)} devices for BGP metrics")
                
                for device in devices:
                    try:
                        sessions = self.collect_bgp_sessions(device)
                        if sessions:
                            self.store_bgp_metrics(sessions)
                    except Exception as e:
                        logger.error(f"Failed to collect from {device['hostname']}: {e}")
                        continue
                
                logger.info(f"BGP collection complete. Sleeping {interval}s")
                time.sleep(interval)
                
            except KeyboardInterrupt:
                logger.info("Stopping BGP collector")
                break
            except Exception as e:
                logger.error(f"Collection error: {e}")
                time.sleep(60)

if __name__ == '__main__':
    collector = BGPCollector()
    collector.run(interval=int(os.getenv('BGP_POLL_INTERVAL', 300)))

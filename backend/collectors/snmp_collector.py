#!/usr/bin/env python3
"""
SNMP Collector Module - Polls network devices via SNMP
"""

import os
import yaml
import time
import logging
from pysnmp.hlapi import *
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import concurrent.futures

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SNMPCollector:
    def __init__(self, db_config):
        self.db_config = db_config
        self.devices = []
        self.profiles = {}
        
    def load_devices(self, config_path='../config/devices.yaml'):
        """Load device inventory from YAML"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                self.devices = config.get('devices', [])
            logger.info(f"Loaded {len(self.devices)} devices")
        except Exception as e:
            logger.error(f"Error loading devices: {e}")
            
    def load_profiles(self, config_path='../config/snmp_profiles.yaml'):
        """Load SNMP profiles"""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                self.profiles = config.get('profiles', {})
            logger.info(f"Loaded {len(self.profiles)} SNMP profiles")
        except Exception as e:
            logger.error(f"Error loading profiles: {e}")
            
    def get_snmp_value(self, device, oid, community='public'):
        """Perform SNMP GET operation"""
        try:
            iterator = getCmd(
                SnmpEngine(),
                CommunityData(community, mpModel=1),  # SNMPv2c
                UdpTransportTarget((device['ip'], 161), timeout=2, retries=1),
                ContextData(),
                ObjectType(ObjectIdentity(oid))
            )
            
            errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
            
            if errorIndication:
                logger.error(f"SNMP error for {device['hostname']}: {errorIndication}")
                return None
            elif errorStatus:
                logger.error(f"SNMP error for {device['hostname']}: {errorStatus}")
                return None
            else:
                for varBind in varBinds:
                    return str(varBind[1])
        except Exception as e:
            logger.error(f"Exception polling {device['hostname']}: {e}")
            return None
    
    def get_snmp_walk(self, device, oid, community='public'):
        """Perform SNMP WALK operation"""
        results = []
        try:
            for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
                SnmpEngine(),
                CommunityData(community, mpModel=1),
                UdpTransportTarget((device['ip'], 161), timeout=2, retries=1),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False
            ):
                if errorIndication:
                    logger.error(f"SNMP walk error for {device['hostname']}: {errorIndication}")
                    break
                elif errorStatus:
                    logger.error(f"SNMP walk error for {device['hostname']}: {errorStatus}")
                    break
                else:
                    for varBind in varBinds:
                        results.append((str(varBind[0]), str(varBind[1])))
        except Exception as e:
            logger.error(f"Exception during SNMP walk {device['hostname']}: {e}")
        return results
    
    def collect_device_metrics(self, device):
        """Collect metrics from a single device"""
        logger.info(f"Polling {device['hostname']} ({device['ip']})")
        
        metrics = []
        community = device.get('snmp', {}).get('community', 'public')
        
        # Get vendor-specific profile
        vendor = device.get('vendor', 'generic')
        profile = self.profiles.get(vendor, self.profiles.get('generic', {}))
        
        # System info
        sys_descr = self.get_snmp_value(device, '1.3.6.1.2.1.1.1.0', community)
        sys_uptime = self.get_snmp_value(device, '1.3.6.1.2.1.1.3.0', community)
        
        # CPU utilization
        cpu_oid = profile.get('oids', {}).get('cpu')
        if cpu_oid:
            cpu_value = self.get_snmp_value(device, cpu_oid, community)
            if cpu_value:
                metrics.append({
                    'metric_name': 'cpu_utilization',
                    'value': float(cpu_value),
                    'unit': 'percent'
                })
        
        # Memory utilization
        mem_oid = profile.get('oids', {}).get('memory')
        if mem_oid:
            mem_value = self.get_snmp_value(device, mem_oid, community)
            if mem_value:
                metrics.append({
                    'metric_name': 'memory_utilization',
                    'value': float(mem_value),
                    'unit': 'percent'
                })
        
        # Interface statistics
        if_walk = self.get_snmp_walk(device, '1.3.6.1.2.1.2.2.1', community)
        interfaces = self.parse_interface_stats(if_walk)
        
        for iface in interfaces:
            metrics.extend([{
                'metric_name': f"interface_{iface['name']}_in_octets",
                'value': iface.get('in_octets', 0),
                'unit': 'bytes'
            }, {
                'metric_name': f"interface_{iface['name']}_out_octets",
                'value': iface.get('out_octets', 0),
                'unit': 'bytes'
            }, {
                'metric_name': f"interface_{iface['name']}_status",
                'value': iface.get('status', 0),
                'unit': 'state'
            }])
        
        return {
            'hostname': device['hostname'],
            'metrics': metrics,
            'uptime': sys_uptime,
            'status': 'online' if sys_uptime else 'offline'
        }
    
    def parse_interface_stats(self, walk_results):
        """Parse interface statistics from SNMP walk"""
        interfaces = []
        if_data = {}
        
        for oid, value in walk_results:
            parts = oid.split('.')
            if len(parts) >= 11:
                if_index = parts[10]
                if_type = parts[9]
                
                if if_index not in if_data:
                    if_data[if_index] = {}
                
                # Map OID to metric
                if if_type == '2':  # ifDescr
                    if_data[if_index]['name'] = value
                elif if_type == '8':  # ifOperStatus
                    if_data[if_index]['status'] = int(value)
                elif if_type == '10':  # ifInOctets
                    if_data[if_index]['in_octets'] = int(value)
                elif if_type == '16':  # ifOutOctets
                    if_data[if_index]['out_octets'] = int(value)
        
        return list(if_data.values())
    
    def store_metrics(self, device_data):
        """Store metrics in TimescaleDB"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            # Update device last_seen
            cur.execute("""
                UPDATE devices 
                SET last_seen = NOW()
                WHERE hostname = %s
            """, (device_data['hostname'],))
            
            # Get device ID
            cur.execute("""
                SELECT id FROM devices WHERE hostname = %s
            """, (device_data['hostname'],))
            result = cur.fetchone()
            
            if result:
                device_id = result[0]
                
                # Insert metrics
                for metric in device_data['metrics']:
                    cur.execute("""
                        INSERT INTO metrics (device_id, metric_name, value, unit)
                        VALUES (%s, %s, %s, %s)
                    """, (device_id, metric['metric_name'], metric['value'], metric['unit']))
            
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error storing metrics: {e}")
    
    def poll_all_devices(self):
        """Poll all devices concurrently"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(self.collect_device_metrics, device): device 
                      for device in self.devices}
            
            for future in concurrent.futures.as_completed(futures):
                device = futures[future]
                try:
                    data = future.result()
                    self.store_metrics(data)
                except Exception as e:
                    logger.error(f"Error polling {device['hostname']}: {e}")

def main():
    """Main polling loop"""
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', 5432),
        'database': os.getenv('DB_NAME', 'supervision'),
        'user': os.getenv('DB_USER', 'admin'),
        'password': os.getenv('DB_PASSWORD', 'admin123')
    }
    
    collector = SNMPCollector(db_config)
    collector.load_devices()
    collector.load_profiles()
    
    poll_interval = int(os.getenv('POLL_INTERVAL', 30))  # 30 seconds
    
    logger.info(f"Starting SNMP collector with {poll_interval}s interval")
    
    while True:
        try:
            collector.poll_all_devices()
            logger.info(f"Poll cycle complete, sleeping {poll_interval}s")
            time.sleep(poll_interval)
        except KeyboardInterrupt:
            logger.info("Collector stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in poll loop: {e}")
            time.sleep(poll_interval)

if __name__ == '__main__':
    main()

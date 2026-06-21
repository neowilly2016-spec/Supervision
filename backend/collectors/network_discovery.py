#!/usr/bin/env python3
"""
Network Discovery Module - Auto-discover devices via SNMP
Scans configured network ranges and discovers devices automatically
"""

import os
import ipaddress
import concurrent.futures
import logging
from pysnmp.hlapi import *
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NetworkDiscovery:
    def __init__(self, db_config):
        self.db_config = db_config
        
        # Network ranges to scan with their SNMP communities
        self.scan_ranges = [
            {
                'network': '10.200.0.0/16',  # Zone 1 - Juniper MBH
                'community': 'mpbn',
                'zone': 'MBH-Zone1',
                'vendor_hint': 'juniper'
            },
            {
                'network': '10.40.0.0/16',   # Zone 2 - Huawei MBH
                'community': 'mobilis-read-only',
                'zone': 'MBH-Zone2',
                'vendor_hint': 'huawei'
            },
            {
                'network': '10.42.0.0/16',   # Zone 2 - Huawei MBH
                'community': 'mobilis-read-only',
                'zone': 'MBH-Zone2',
                'vendor_hint': 'huawei'
            },
            {
                'network': '10.44.0.0/16',   # Zone 2 - Huawei MBH
                'community': 'mobilis-read-only',
                'zone': 'MBH-Zone2',
                'vendor_hint': 'huawei'
            },
        ]
    
    def snmp_get(self, ip, community, oid):
        """Perform SNMP GET operation"""
        try:
            iterator = getCmd(
                SnmpEngine(),
                CommunityData(community, mpModel=1),
                UdpTransportTarget((ip, 161), timeout=1, retries=0),
                ContextData(),
                ObjectType(ObjectIdentity(oid))
            )
            
            errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
            
            if errorIndication or errorStatus:
                return None
            
            for varBind in varBinds:
                return str(varBind[1])
        except Exception:
            return None
    
    def probe_device(self, ip, community):
        """Probe a device via SNMP to get basic info"""
        # Standard SNMP OIDs
        sys_descr = self.snmp_get(ip, community, '1.3.6.1.2.1.1.1.0')  # sysDescr
        sys_name = self.snmp_get(ip, community, '1.3.6.1.2.1.1.5.0')   # sysName
        sys_oid = self.snmp_get(ip, community, '1.3.6.1.2.1.1.2.0')    # sysObjectID
        
        if not sys_descr:
            return None
        
        # Determine vendor from sysDescr or sysObjectID
        vendor = self.identify_vendor(sys_descr, sys_oid)
        device_type = self.identify_type(sys_descr)
        
        return {
            'ip': ip,
            'hostname': sys_name if sys_name else f'device-{ip}',
            'sys_descr': sys_descr,
            'vendor': vendor,
            'type': device_type,
            'community': community
        }
    
    def identify_vendor(self, sys_descr, sys_oid):
        """Identify vendor from SNMP data"""
        descr_lower = sys_descr.lower() if sys_descr else ''
        
        if 'juniper' in descr_lower or 'junos' in descr_lower:
            return 'juniper'
        elif 'huawei' in descr_lower or 'vrp' in descr_lower:
            return 'huawei'
        elif 'ericsson' in descr_lower:
            return 'ericsson'
        elif 'cisco' in descr_lower:
            return 'cisco'
        
        return 'generic'
    
    def identify_type(self, sys_descr):
        """Identify device type from sysDescr"""
        descr_lower = sys_descr.lower() if sys_descr else ''
        
        if 'router' in descr_lower or 'mx' in descr_lower or 'ne' in descr_lower:
            return 'router'
        elif 'switch' in descr_lower or 'ce' in descr_lower:
            return 'switch'
        elif 'microwave' in descr_lower or 'mw' in descr_lower or 'mini-link' in descr_lower:
            return 'microwave'
        
        return 'unknown'
    
    def scan_network_range(self, range_config):
        """Scan a network range for devices"""
        network = ipaddress.ip_network(range_config['network'])
        community = range_config['community']
        zone = range_config['zone']
        
        logger.info(f"Scanning {range_config['network']} (Zone: {zone})")
        
        discovered_devices = []
        
        # Use ThreadPoolExecutor for concurrent scanning
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = {}
            
            for ip in network.hosts():
                ip_str = str(ip)
                futures[executor.submit(self.probe_device, ip_str, community)] = ip_str
            
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    result['zone'] = zone
                    discovered_devices.append(result)
                    logger.info(f"Discovered: {result['hostname']} ({result['ip']}) - {result['vendor']} {result['type']}")
        
        return discovered_devices
    
    def save_discovered_device(self, device):
        """Save discovered device to database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            # Check if device already exists
            cur.execute("""
                SELECT id FROM devices WHERE ip = %s
            """, (device['ip'],))
            
            existing = cur.fetchone()
            
            if existing:
                # Update existing device
                cur.execute("""
                    UPDATE devices SET
                        hostname = %s,
                        vendor = %s,
                        type = %s,
                        last_seen = NOW(),
                        sys_descr = %s
                    WHERE ip = %s
                """, (device['hostname'], device['vendor'], device['type'], 
                      device['sys_descr'], device['ip']))
                logger.info(f"Updated device: {device['hostname']}")
            else:
                # Insert new device
                cur.execute("""
                    INSERT INTO devices (hostname, ip, vendor, type, sys_descr, last_seen)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (device['hostname'], device['ip'], device['vendor'], 
                      device['type'], device['sys_descr']))
                logger.info(f"Added new device: {device['hostname']}")
            
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving device {device['ip']}: {e}")
    
    def run_discovery(self):
        """Run discovery on all configured ranges"""
        logger.info("Starting network discovery...")
        
        total_discovered = 0
        
        for range_config in self.scan_ranges:
            devices = self.scan_network_range(range_config)
            
            for device in devices:
                self.save_discovered_device(device)
            
            total_discovered += len(devices)
        
        logger.info(f"Discovery complete. Found {total_discovered} devices.")
        return total_discovered

def main():
    """Main discovery function"""
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', 5432),
        'database': os.getenv('DB_NAME', 'supervision'),
        'user': os.getenv('DB_USER', 'admin'),
        'password': os.getenv('DB_PASSWORD', 'admin123')
    }
    
    discovery = NetworkDiscovery(db_config)
    discovery.run_discovery()

if __name__ == '__main__':
    main()

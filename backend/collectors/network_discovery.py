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
                'network': '10.200.0.0/16',  # Backbone MX960 + MBH Zone 1 (Juniper)
                'community': 'mpbn',
                'zone': 'Backbone',
                'vendor_hint': 'juniper'
            },
            {
                'network': '10.44.0.0/16',  # MBH Zone 2 - Huawei
                'community': 'mpbn',
                'zone': 'MBH-Zone2',
                'vendor_hint': 'huawei'
            },
            {
                'network': '192.168.100.0/24',  # Microwave management
                'community': 'public',
                'zone': 'Microwave',
                'vendor_hint': 'microwave'
            }
        ]

    def discover_device(self, ip, community, zone, vendor_hint):
        """
        Try to discover a device at the given IP via SNMP
        Returns device info dict if successful, None otherwise
        """
        try:
            # Try to get sysDescr (OID 1.3.6.1.2.1.1.1.0)
            iterator = getCmd(
                SnmpEngine(),
                CommunityData(community),
                UdpTransportTarget((ip, 161), timeout=2, retries=1),
                ContextData(),
                ObjectType(ObjectIdentity('SNMPv2-MIB', 'sysDescr', 0)),
                ObjectType(ObjectIdentity('SNMPv2-MIB', 'sysName', 0))
            )
            
            errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
            
            if errorIndication or errorStatus:
                return None
            
            sys_descr = str(varBinds[0][1])
            sys_name = str(varBinds[1][1])
            
            # Identify device type and vendor from sysDescr
            device_type, vendor = self.identify_type(sys_descr, vendor_hint)
            
            device_info = {
                'ip': ip,
                'hostname': sys_name,
                'sys_descr': sys_descr,
                'type': device_type,
                'vendor': vendor,
                'zone': zone,
                'community': community
            }
            
            logger.info(f"Discovered device: {sys_name} ({ip}) - {vendor} {device_type} in {zone}")
            return device_info
            
        except Exception as e:
            # Device not responding or not SNMP-enabled
            return None

    def identify_type(self, sys_descr, vendor_hint):
        """
        Identify device type and vendor from sysDescr
        Returns (device_type, vendor)
        """
        sys_descr_lower = sys_descr.lower()
        
        # Identify Juniper devices
        if 'juniper' in sys_descr_lower or vendor_hint == 'juniper':
            if 'mx960' in sys_descr_lower:
                return 'Backbone', 'juniper'
            elif 'mx480' in sys_descr_lower or 'mx204' in sys_descr_lower or 'mx104' in sys_descr_lower:
                return 'MBH-Zone1', 'juniper'
            else:
                return 'router', 'juniper'
        
        # Identify Huawei devices
        elif 'huawei' in sys_descr_lower or vendor_hint == 'huawei':
            if 'ne9000' in sys_descr_lower or 'ne5000' in sys_descr_lower:
                # Check if in Backbone range (10.200.0.x) or MBH Zone 2 (10.44.x.y)
                return 'MBH-Zone2', 'huawei'  # Huawei mainly in Zone 2
            elif 'rtn' in sys_descr_lower:
                return 'microwave', 'huawei'
            else:
                return 'router', 'huawei'
        
        # Identify Ericsson microwave
        elif 'ericsson' in sys_descr_lower or 'mini-link' in sys_descr_lower:
            return 'microwave', 'ericsson'
        
        # Default
        return 'unknown', 'unknown'

    def scan_network(self, network_range, community, zone, vendor_hint):
        """
        Scan an entire network range for SNMP-enabled devices
        """
        network = ipaddress.ip_network(network_range, strict=False)
        discovered_devices = []
        
        logger.info(f"Scanning {network_range} (zone: {zone})...")
        
        # Use concurrent scanning for faster discovery
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = {
                executor.submit(self.discover_device, str(ip), community, zone, vendor_hint): ip
                for ip in network.hosts()
            }
            
            for future in concurrent.futures.as_completed(futures):
                device = future.result()
                if device:
                    discovered_devices.append(device)
        
        logger.info(f"Scan complete for {network_range}: found {len(discovered_devices)} devices")
        return discovered_devices

    def save_to_database(self, devices):
        """
        Save discovered devices to the database
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            for device in devices:
                # Insert or update device
                cur.execute(
                    """
                    INSERT INTO devices (hostname, ip_address, vendor, device_type, zone, snmp_community, sys_descr, discovered_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (ip_address) 
                    DO UPDATE SET 
                        hostname = EXCLUDED.hostname,
                        vendor = EXCLUDED.vendor,
                        device_type = EXCLUDED.device_type,
                        zone = EXCLUDED.zone,
                        sys_descr = EXCLUDED.sys_descr,
                        discovered_at = NOW()
                    """,
                    (device['hostname'], device['ip'], device['vendor'], 
                     device['type'], device['zone'], device['community'], 
                     device['sys_descr'])
                )
            
            conn.commit()
            cur.close()
            conn.close()
            logger.info(f"Saved {len(devices)} devices to database")
        except Exception as e:
            logger.error(f"Error saving to database: {e}")

    def run_discovery(self):
        """
        Run discovery on all configured network ranges
        """
        all_devices = []
        
        for scan_range in self.scan_ranges:
            devices = self.scan_network(
                scan_range['network'],
                scan_range['community'],
                scan_range['zone'],
                scan_range['vendor_hint']
            )
            all_devices.extend(devices)
        
        if all_devices:
            self.save_to_database(all_devices)
        
        return all_devices

if __name__ == '__main__':
    # Database configuration from environment
    db_config = {
        'host': os.getenv('POSTGRES_HOST', 'timescaledb'),
        'port': os.getenv('POSTGRES_PORT', 5432),
        'database': os.getenv('POSTGRES_DB', 'supervision'),
        'user': os.getenv('POSTGRES_USER', 'supervisor'),
        'password': os.getenv('POSTGRES_PASSWORD', 'supervision123')
    }
    
    discovery = NetworkDiscovery(db_config)
    devices = discovery.run_discovery()
    
    print(f"\nDiscovery complete: {len(devices)} devices found")
    for device in devices:
        print(f"  - {device['hostname']} ({device['ip']}) - {device['vendor']} {device['type']}")

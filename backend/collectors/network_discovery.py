#!/usr/bin/env python3
"""
Network Discovery Module - Auto-discover devices via SNMPv2
Scans configured network ranges and discovers Backbone & MBH devices
Performance Edition: Optimized for Backbone and MBH only
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
        
        # Network ranges to scan - Backbone and MBH only
        self.scan_ranges = [
            {
                'network': '10.200.0.0/16',
                'community': 'mpbn',
                'zone': 'Backbone-MBH-Zone1',
                'vendor_hint': 'juniper',
                'description': 'Backbone MX960 + MBH Zone 1 Juniper MX480/MX204/MX104'
            },
            {
                'network': '10.44.0.0/16',
                'community': 'mpbn',
                'zone': 'MBH-Zone2',
                'vendor_hint': 'huawei',
                'description': 'MBH Zone 2 Huawei NE9000/NE5000E'
            }
        ]

    def discover_device(self, ip, community, zone, vendor_hint):
        """
        Discover a device at the given IP via SNMPv2
        Returns device info dict if successful, None otherwise
        """
        try:
            # SNMP GET: sysDescr, sysName
            iterator = getCmd(
                SnmpEngine(),
                CommunityData(community, mpModel=1),  # SNMPv2c
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
            
            # Identify device type and vendor
            device_type, vendor = self.identify_type(sys_descr, vendor_hint, ip)
            
            device_info = {
                'ip': ip,
                'hostname': sys_name,
                'sys_descr': sys_descr,
                'type': device_type,
                'vendor': vendor,
                'zone': zone,
                'community': community,
                'snmp_version': '2c'
            }
            
            logger.info(f"Discovered: {sys_name} ({ip}) - {vendor} {device_type} in {zone}")
            return device_info
            
        except Exception as e:
            # Device not responding or SNMP disabled
            return None

    def identify_type(self, sys_descr, vendor_hint, ip):
        """
        Identify device type and vendor from sysDescr and IP
        Returns (device_type, vendor)
        """
        sys_descr_lower = sys_descr.lower()
        
        # Identify Juniper devices
        if 'juniper' in sys_descr_lower or vendor_hint == 'juniper':
            # Backbone MX960 (typically 10.200.0.x)
            if 'mx960' in sys_descr_lower:
                return 'Backbone', 'juniper'
            # MBH Zone 1 Juniper
            elif any(model in sys_descr_lower for model in ['mx480', 'mx204', 'mx104']):
                return 'MBH-Zone1', 'juniper'
            else:
                # Generic Juniper router
                return 'router', 'juniper'
        
        # Identify Huawei devices
        elif 'huawei' in sys_descr_lower or vendor_hint == 'huawei':
            # Check IP range to distinguish Backbone vs MBH
            ip_obj = ipaddress.ip_address(ip)
            backbone_network = ipaddress.ip_network('10.200.0.0/24')  # Backbone subnet
            
            if ip_obj in backbone_network:
                # Backbone Huawei NE9000
                return 'Backbone', 'huawei'
            else:
                # MBH Zone 2 Huawei (10.44.x.y)
                if any(model in sys_descr_lower for model in ['ne9000', 'ne5000']):
                    return 'MBH-Zone2', 'huawei'
                else:
                    return 'router', 'huawei'
        
        # Unknown device
        return 'unknown', 'unknown'

    def scan_network(self, network_range, community, zone, vendor_hint, description):
        """
        Scan entire network range for SNMPv2-enabled devices
        Uses concurrent workers for faster discovery
        """
        network = ipaddress.ip_network(network_range, strict=False)
        discovered_devices = []
        
        logger.info(f"Scanning {network_range} ({description})...")
        
        # Concurrent scanning with thread pool
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
        Save discovered devices to PostgreSQL/TimescaleDB
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            for device in devices:
                # Upsert device
                cur.execute(
                    """
                    INSERT INTO devices (
                        hostname, ip_address, vendor, device_type, zone, 
                        snmp_community, snmp_version, sys_descr, discovered_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
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
                     device['snmp_version'], device['sys_descr'])
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
        Backbone and MBH only
        """
        all_devices = []
        
        for scan_range in self.scan_ranges:
            devices = self.scan_network(
                scan_range['network'],
                scan_range['community'],
                scan_range['zone'],
                scan_range['vendor_hint'],
                scan_range['description']
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
    print(f"\n{'Hostname':<30} {'IP':<15} {'Vendor':<10} {'Type':<20} {'Zone':<25}")
    print("=" * 100)
    for device in devices:
        print(f"{device['hostname']:<30} {device['ip']:<15} {device['vendor']:<10} {device['type']:<20} {device['zone']:<25}")

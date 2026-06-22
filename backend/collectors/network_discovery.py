#!/usr/bin/env python3
"""
Network Discovery Module - SNMPv2 Auto-Discovery
Scans network ranges and classifies devices by role (PE/P/AGG/DIST)
"""

import os
import re
import yaml
import ipaddress
import concurrent.futures
import logging
from pysnmp.hlapi import *
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NetworkDiscovery:
    def __init__(self, db_config, config_file='config/devices.yaml'):
        self.db_config = db_config
        self.config = self.load_config(config_file)
        
    def load_config(self, config_file):
        """Load configuration from devices.yaml"""
        try:
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return None
    
    def discover_device(self, ip, community):
        """
        Discover device via SNMPv2 and extract basic info
        """
        try:
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
            
            # Classify device
            vendor, model = self.identify_vendor_model(sys_descr)
            role = self.classify_role(sys_descr, ip)
            
            if vendor and model and role:
                device_info = {
                    'ip': ip,
                    'hostname': sys_name,
                    'sys_descr': sys_descr,
                    'vendor': vendor,
                    'model': model,
                    'role': role,
                    'snmp_version': '2c',
                    'community': community
                }
                
                logger.info(f"Discovered: {sys_name} ({ip}) - {vendor} {model} [Role: {role}]")
                return device_info
            
            return None
            
        except Exception as e:
            return None
    
    def identify_vendor_model(self, sys_descr):
        """
        Identify vendor and model from sysDescr using patterns from config
        """
        sys_descr_lower = sys_descr.lower()
        vendor_detection = self.config.get('vendor_detection', {})
        
        for vendor, vendor_config in vendor_detection.items():
            # Check vendor pattern
            for pattern_entry in vendor_config.get('patterns', []):
                pattern = pattern_entry.get('sysDescr', '')
                if re.search(pattern, sys_descr_lower):
                    # Find model
                    models = vendor_config.get('models', {})
                    for model_name, model_pattern in models.items():
                        if re.search(model_pattern, sys_descr_lower):
                            return vendor, model_name
                    return vendor, 'Unknown'
        
        return None, None
    
    def classify_role(self, sys_descr, ip):
        """
        Classify device role (PE/P/AGG/DIST) based on sysDescr patterns
        """
        sys_descr_lower = sys_descr.lower()
        role_classification = self.config.get('role_classification', {})
        
        # Try each role in order: PE, P, AGG, DIST
        for role in ['PE', 'P', 'AGG', 'DIST']:
            role_config = role_classification.get(role, {})
            patterns = role_config.get('patterns', [])
            
            for pattern_entry in patterns:
                pattern = pattern_entry.get('sysDescr', '')
                if re.search(pattern, sys_descr_lower):
                    return role
        
        return 'Unknown'
    
    def scan_network(self, network_range, community):
        """
        Scan a network range for SNMP devices
        """
        network = ipaddress.ip_network(network_range, strict=False)
        discovered_devices = []
        
        logger.info(f"Scanning {network_range}...")
        
        workers = self.config.get('global', {}).get('discovery_workers', 20)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self.discover_device, str(ip), community): ip
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
        Save discovered devices to TimescaleDB
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            for device in devices:
                cur.execute(
                    """
                    INSERT INTO devices (
                        hostname, ip_address, vendor, model, role,
                        snmp_community, snmp_version, sys_descr, discovered_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (ip_address) 
                    DO UPDATE SET 
                        hostname = EXCLUDED.hostname,
                        vendor = EXCLUDED.vendor,
                        model = EXCLUDED.model,
                        role = EXCLUDED.role,
                        sys_descr = EXCLUDED.sys_descr,
                        discovered_at = NOW()
                    """,
                    (device['hostname'], device['ip'], device['vendor'],
                     device['model'], device['role'], device['community'],
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
        """
        all_devices = []
        
        network_ranges = self.config.get('network_ranges', [])
        community = self.config.get('global', {}).get('snmp_community', 'public')
        
        for network_range in network_ranges:
            devices = self.scan_network(network_range, community)
            all_devices.extend(devices)
        
        if all_devices:
            self.save_to_database(all_devices)
        
        # Group by role for summary
        by_role = {}
        for device in all_devices:
            role = device['role']
            if role not in by_role:
                by_role[role] = []
            by_role[role].append(device)
        
        return all_devices, by_role

if __name__ == '__main__':
    # Database configuration
    db_config = {
        'host': os.getenv('POSTGRES_HOST', 'timescaledb'),
        'port': os.getenv('POSTGRES_PORT', 5432),
        'database': os.getenv('POSTGRES_DB', 'supervision'),
        'user': os.getenv('POSTGRES_USER', 'supervisor'),
        'password': os.getenv('POSTGRES_PASSWORD', 'supervision123')
    }
    
    discovery = NetworkDiscovery(db_config)
    devices, by_role = discovery.run_discovery()
    
    print(f"\n{'='*80}")
    print(f"Discovery complete: {len(devices)} devices found")
    print(f"{'='*80}\n")
    
    # Summary by role
    for role, role_devices in sorted(by_role.items()):
        print(f"\n[{role}] - {len(role_devices)} devices:")
        print(f"{'-'*80}")
        for device in role_devices:
            print(f"  {device['hostname']:<30} {device['ip']:<15} {device['vendor']:<10} {device['model']:<10}")

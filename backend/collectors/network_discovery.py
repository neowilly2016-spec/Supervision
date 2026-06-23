#!/usr/bin/env python3
"""
Network Discovery Module - SNMPv2 Auto-Discovery
Scans network ranges and classifies devices by zone (Backbone/MBH) and role (PE/P/AGG/DIST)
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
        Returns: dict with hostname, sysDescr, vendor, model
        """
        try:
            # SNMPv2 GET for sysDescr, sysName
            iterator = getCmd(
                SnmpEngine(),
                CommunityData(community, mpModel=1),  # SNMPv2c
                UdpTransportTarget((ip, 161), timeout=5.0, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity('SNMPv2-MIB', 'sysDescr', 0)),
                ObjectType(ObjectIdentity('SNMPv2-MIB', 'sysName', 0))
            )
            
            errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
            
            if errorIndication or errorStatus:
                return None
            
            sys_descr = str(varBinds[0][1])
            hostname = str(varBinds[1][1])
            
            # Extract vendor from sysDescr
            vendor = self._extract_vendor(sys_descr)
            model = self._extract_model(sys_descr)
            
            return {
                'ip': ip,
                'hostname': hostname,
                'sys_descr': sys_descr,
                'vendor': vendor,
                'model': model
            }
        
        except Exception as e:
            logger.debug(f"Failed to discover {ip}: {e}")
            return None
    
    def _extract_vendor(self, sys_descr):
        """Extract vendor from sysDescr"""
        sys_descr_lower = sys_descr.lower()
        
        if 'juniper' in sys_descr_lower or 'junos' in sys_descr_lower:
            return 'Juniper'
        elif 'huawei' in sys_descr_lower:
            return 'Huawei'
        else:
            return 'Unknown'
    
    def _extract_model(self, sys_descr):
        """Extract model from sysDescr"""
        # Match common patterns
        patterns = [
            r'(MX\d+)',      # Juniper MX series
            r'(NE\d+[A-Z]*)', # Huawei NE series
            r'(ACX\d+)',      # Juniper ACX
        ]
        
        for pattern in patterns:
            match = re.search(pattern, sys_descr, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        
        return 'Unknown'
    
    def classify_zone(self, hostname, sys_descr, ip, model):
        """
        Classify device zone (backbone or mbh) based on zone_classification patterns
        Returns: 'backbone', 'mbh', or 'unknown'
        """
        zone_classification = self.config.get('zone_classification', {})
        
        # Check Backbone classification
        backbone_config = zone_classification.get('backbone', {})
        if self._matches_zone_patterns(hostname, sys_descr, ip, model, backbone_config):
            return 'backbone'
        
        # Check MBH classification
        mbh_config = zone_classification.get('mbh', {})
        if self._matches_zone_patterns(hostname, sys_descr, ip, model, mbh_config):
            return 'mbh'
        
        return 'unknown'
    
    def _matches_zone_patterns(self, hostname, sys_descr, ip, model, zone_config):
        """
        Check if device matches zone classification patterns
        """
        # Check hostname patterns
        hostname_patterns = zone_config.get('hostname_patterns', [])
        for pattern in hostname_patterns:
            if re.search(pattern, hostname, re.IGNORECASE):
                return True
        
        # Check sysDescr patterns
        sysdescr_patterns = zone_config.get('sysDescr_patterns', [])
        for pattern in sysdescr_patterns:
            if re.search(pattern, sys_descr, re.IGNORECASE):
                return True
        
        # Check IP ranges
        ip_ranges = zone_config.get('ip_ranges', [])
        for ip_range in ip_ranges:
            if ipaddress.ip_address(ip) in ipaddress.ip_network(ip_range):
                return True
        
        # Check conditional IP classification (for 10.42.0.0/16)
        ip_conditional = zone_config.get('ip_conditional', {})
        if ip_conditional:
            cond_range = ip_conditional.get('range')
            if cond_range and ipaddress.ip_address(ip) in ipaddress.ip_network(cond_range):
                include_models = ip_conditional.get('include_models', [])
                exclude_models = ip_conditional.get('exclude_models', [])
                
                # Check if model matches include list
                for inc_model in include_models:
                    if inc_model.upper() in model.upper():
                        # Make sure it's not in exclude list
                        for exc_model in exclude_models:
                            if exc_model.upper() in model.upper():
                                return False
                        return True
        
        return False
    
    def classify_role(self, sys_descr, ip, hostname):
        """
        Classify device role (PE/P/AGG/DIST) based on sysDescr and hostname patterns
        """
        sys_descr_lower = sys_descr.lower()
        role_classification = self.config.get('role_classification', {})
        
        # Try each role in order: PE, P, AGG, DIST
        for role in ['PE', 'P', 'AGG', 'DIST']:
            role_config = role_classification.get(role, {})
            patterns = role_config.get('patterns', [])
            
            for pattern_entry in patterns:
                # Check sysDescr pattern
                if 'sysDescr' in pattern_entry:
                    pattern = pattern_entry.get('sysDescr', '')
                    if re.search(pattern, sys_descr_lower):
                        return role
                
                # Check hostname pattern
                if 'hostname' in pattern_entry:
                    pattern = pattern_entry.get('hostname', '')
                    if re.search(pattern, hostname, re.IGNORECASE):
                        return role
        
        return 'Unknown'
    
    def scan_network(self, network_range, community):
        """
        Scan a network range for SNMP devices
        """
        network = ipaddress.ip_network(network_range, strict=False)
        discovered_devices = []
        
        logger.info(f"Scanning {network_range}...")
        
        # Parallel scanning with thread pool
        max_workers = self.config.get('global', {}).get('discovery_workers', 20)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.discover_device, str(ip), community): str(ip) 
                for ip in network.hosts()
            }
            
            for future in concurrent.futures.as_completed(futures):
                device = future.result()
                if device:
                    # Classify zone and role
                    zone = self.classify_zone(
                        device['hostname'], 
                        device['sys_descr'], 
                        device['ip'],
                        device['model']
                    )
                    role = self.classify_role(
                        device['sys_descr'], 
                        device['ip'],
                        device['hostname']
                    )
                    
                    device['zone'] = zone
                    device['role'] = role
                    discovered_devices.append(device)
                    
                    logger.info(f"Discovered: {device['hostname']} ({device['ip']}) - Zone: {zone}, Role: {role}")
        
        return discovered_devices
    
    def run_discovery(self):
        """
        Main discovery routine - scan all configured network ranges
        """
        global_config = self.config.get('global', {})
        community = global_config.get('snmp_community', 'public')
        network_ranges = self.config.get('network_ranges', [])
        
        all_devices = []
        
        for network_range in network_ranges:
            devices = self.scan_network(network_range, community)
            all_devices.extend(devices)
        
        # Save to database
        if all_devices:
            self.save_to_database(all_devices)
        
        # Group by role and zone for summary
        by_role = {}
        by_zone = {}
        for device in all_devices:
            role = device['role']
            zone = device['zone']
            
            if role not in by_role:
                by_role[role] = []
            by_role[role].append(device)
            
            if zone not in by_zone:
                by_zone[zone] = []
            by_zone[zone].append(device)
        
        return all_devices, by_role, by_zone
    
    def save_to_database(self, devices):
        """
        Save discovered devices to PostgreSQL database
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            for device in devices:
                cursor.execute("""
                    INSERT INTO devices (hostname, ip, vendor, model, sys_descr, zone, role, last_seen)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (ip) DO UPDATE SET
                        hostname = EXCLUDED.hostname,
                        vendor = EXCLUDED.vendor,
                        model = EXCLUDED.model,
                        sys_descr = EXCLUDED.sys_descr,
                        zone = EXCLUDED.zone,
                        role = EXCLUDED.role,
                        last_seen = NOW()
                """, (
                    device['hostname'],
                    device['ip'],
                    device['vendor'],
                    device['model'],
                    device['sys_descr'],
                    device['zone'],
                    device['role']
                ))
            
            conn.commit()
            cursor.close()
            conn.close()
            logger.info(f"Saved {len(devices)} devices to database")
        
        except Exception as e:
            logger.error(f"Database error: {e}")


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
    devices, by_role, by_zone = discovery.run_discovery()
    
    print(f"\n{'='*80}")
    print(f"Discovery complete: {len(devices)} devices found")
    print(f"{'='*80}\n")
    
    # Summary by zone
    print("Summary by Zone:")
    for zone, zone_devices in sorted(by_zone.items()):
        print(f"  {zone}: {len(zone_devices)} devices")
        for device in zone_devices:
            print(f"    - {device['hostname']} ({device['ip']}) [{device['role']}]")
    
    print("\n" + "="*80 + "\n")
    
    # Summary by role
    print("Summary by Role:")
    for role, role_devices in sorted(by_role.items()):
        print(f"  {role}: {len(role_devices)} devices")
        for device in role_devices:
            print(f"    - {device['hostname']} ({device['ip']}) [{device['zone']}]")

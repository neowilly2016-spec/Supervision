#!/usr/bin/env python3
"""
LLDP/CDP Topology Discovery Collector - Performance Edition
Discovers network topology via LLDP and CDP protocols

Supported vendors:
- Juniper MX/NE series (LLDP)
- Huawei NE series (LLDP)
"""

import logging
import psycopg2
import time
from pysnmp.hlapi import *
from datetime import datetime
import os
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# LLDP-MIB OIDs (IEEE 802.1AB)
LLDP_LOC_CHASSIS_ID = '1.0.8802.1.1.2.1.3.2.0'  # lldpLocChassisId
LLDP_LOC_SYS_NAME = '1.0.8802.1.1.2.1.3.3.0'  # lldpLocSysName
LLDP_LOC_SYS_DESC = '1.0.8802.1.1.2.1.3.4.0'  # lldpLocSysDesc
LLDP_REM_TABLE = '1.0.8802.1.1.2.1.4.1'  # lldpRemTable
LLDP_REM_CHASSIS_ID = '1.0.8802.1.1.2.1.4.1.1.5'  # lldpRemChassisId
LLDP_REM_PORT_ID = '1.0.8802.1.1.2.1.4.1.1.7'  # lldpRemPortId
LLDP_REM_PORT_DESC = '1.0.8802.1.1.2.1.4.1.1.8'  # lldpRemPortDesc
LLDP_REM_SYS_NAME = '1.0.8802.1.1.2.1.4.1.1.9'  # lldpRemSysName
LLDP_REM_SYS_DESC = '1.0.8802.1.1.2.1.4.1.1.10'  # lldpRemSysDesc
LLDP_LOC_PORT_DESC = '1.0.8802.1.1.2.1.3.7.1.4'  # lldpLocPortDesc

class LLDPCollector:
    def __init__(self):
        self.db_conn = None
        self.community = os.getenv('SNMP_COMMUNITY', 'public')
        self.topology = {}  # Global topology graph
        
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
                return str(varBinds[0][1])
            return None
        except Exception as e:
            logger.error(f"SNMP GET failed for {device_ip}: {e}")
            return None
    
    def snmp_walk(self, device_ip, oid):
        """Perform SNMP walk"""
        results = []
        try:
            for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
                SnmpEngine(),
                CommunityData(self.community, mpModel=1),
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
    
    def collect_lldp_local_info(self, device):
        """Collect local device LLDP information"""
        device_ip = device['device_ip']
        hostname = device.get('hostname', device_ip)
        
        logger.info(f"Collecting LLDP local info from {hostname} ({device_ip})")
        
        chassis_id = self.snmp_get(device_ip, LLDP_LOC_CHASSIS_ID)
        sys_name = self.snmp_get(device_ip, LLDP_LOC_SYS_NAME)
        sys_desc = self.snmp_get(device_ip, LLDP_LOC_SYS_DESC)
        
        local_info = {
            'device_ip': device_ip,
            'hostname': hostname,
            'chassis_id': chassis_id,
            'system_name': sys_name or hostname,
            'system_description': sys_desc
        }
        
        return local_info
    
    def collect_lldp_neighbors(self, device):
        """Collect LLDP neighbor information"""
        device_ip = device['device_ip']
        hostname = device.get('hostname', device_ip)
        
        logger.info(f"Collecting LLDP neighbors from {hostname} ({device_ip})")
        
        neighbors = []
        
        # Get remote system names
        rem_sys_names = self.snmp_walk(device_ip, LLDP_REM_SYS_NAME)
        
        for neighbor in rem_sys_names:
            oid_parts = str(neighbor[0]).split('.')
            # LLDP index format: timeMark.localPortNum.remIndex
            if len(oid_parts) >= 3:
                local_port = oid_parts[-2]
                rem_index = oid_parts[-1]
                
                # Get additional neighbor details
                rem_chassis = self.snmp_get(device_ip, f"{LLDP_REM_CHASSIS_ID}.{local_port}.{rem_index}")
                rem_port_id = self.snmp_get(device_ip, f"{LLDP_REM_PORT_ID}.{local_port}.{rem_index}")
                rem_port_desc = self.snmp_get(device_ip, f"{LLDP_REM_PORT_DESC}.{local_port}.{rem_index}")
                rem_sys_desc = self.snmp_get(device_ip, f"{LLDP_REM_SYS_DESC}.{local_port}.{rem_index}")
                local_port_desc = self.snmp_get(device_ip, f"{LLDP_LOC_PORT_DESC}.{local_port}")
                
                neighbor_info = {
                    'local_device_ip': device_ip,
                    'local_hostname': hostname,
                    'local_port': local_port,
                    'local_port_desc': local_port_desc,
                    'remote_chassis_id': rem_chassis,
                    'remote_port_id': rem_port_id,
                    'remote_port_desc': rem_port_desc,
                    'remote_system_name': str(neighbor[1]),
                    'remote_system_desc': rem_sys_desc
                }
                
                neighbors.append(neighbor_info)
                logger.debug(f"LLDP neighbor: {hostname} port {local_port} -> {neighbor_info['remote_system_name']}")
        
        return neighbors
    
    def store_topology(self, local_info, neighbors):
        """Store topology information in database"""
        if not self.db_conn:
            self.connect_db()
        
        cursor = self.db_conn.cursor()
        try:
            # Store local device info
            cursor.execute("""
                INSERT INTO lldp_devices (device_ip, hostname, chassis_id, system_name, system_description, last_seen)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (device_ip) DO UPDATE SET
                    hostname = EXCLUDED.hostname,
                    chassis_id = EXCLUDED.chassis_id,
                    system_name = EXCLUDED.system_name,
                    system_description = EXCLUDED.system_description,
                    last_seen = NOW()
            """, (
                local_info['device_ip'],
                local_info['hostname'],
                local_info['chassis_id'],
                local_info['system_name'],
                local_info['system_description']
            ))
            
            # Store neighbor relationships
            for neighbor in neighbors:
                cursor.execute("""
                    INSERT INTO lldp_neighbors (
                        local_device_ip, local_hostname, local_port, local_port_desc,
                        remote_chassis_id, remote_port_id, remote_port_desc,
                        remote_system_name, remote_system_desc, last_seen
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (local_device_ip, local_port, remote_system_name) DO UPDATE SET
                        local_hostname = EXCLUDED.local_hostname,
                        local_port_desc = EXCLUDED.local_port_desc,
                        remote_chassis_id = EXCLUDED.remote_chassis_id,
                        remote_port_id = EXCLUDED.remote_port_id,
                        remote_port_desc = EXCLUDED.remote_port_desc,
                        remote_system_desc = EXCLUDED.remote_system_desc,
                        last_seen = NOW()
                """, (
                    neighbor['local_device_ip'],
                    neighbor['local_hostname'],
                    neighbor['local_port'],
                    neighbor['local_port_desc'],
                    neighbor['remote_chassis_id'],
                    neighbor['remote_port_id'],
                    neighbor['remote_port_desc'],
                    neighbor['remote_system_name'],
                    neighbor['remote_system_desc']
                ))
            
            self.db_conn.commit()
            logger.info(f"Stored topology: {local_info['hostname']} with {len(neighbors)} neighbors")
        except Exception as e:
            logger.error(f"Failed to store topology: {e}")
            self.db_conn.rollback()
        finally:
            cursor.close()
    
    def build_topology_graph(self):
        """Build topology graph from database"""
        if not self.db_conn:
            self.connect_db()
        
        cursor = self.db_conn.cursor()
        cursor.execute("""
            SELECT local_hostname, local_port, remote_system_name, remote_port_id
            FROM lldp_neighbors
            WHERE last_seen > NOW() - INTERVAL '1 hour'
        """)
        
        topology = {'nodes': set(), 'edges': []}
        for row in cursor.fetchall():
            local_host, local_port, remote_host, remote_port = row
            topology['nodes'].add(local_host)
            topology['nodes'].add(remote_host)
            topology['edges'].append({
                'source': local_host,
                'source_port': local_port,
                'target': remote_host,
                'target_port': remote_port
            })
        
        cursor.close()
        topology['nodes'] = list(topology['nodes'])
        return topology
    
    def get_devices(self):
        """Get list of devices from database"""
        if not self.db_conn:
            self.connect_db()
        
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT device_ip, hostname FROM devices WHERE status = 'active'")
        devices = [{'device_ip': row[0], 'hostname': row[1]} for row in cursor.fetchall()]
        cursor.close()
        return devices
    
    def run(self, interval=600):
        """Main collection loop"""
        logger.info(f"Starting LLDP topology collector (interval: {interval}s)")
        
        while True:
            try:
                devices = self.get_devices()
                logger.info(f"Discovering topology from {len(devices)} devices")
                
                for device in devices:
                    try:
                        local_info = self.collect_lldp_local_info(device)
                        neighbors = self.collect_lldp_neighbors(device)
                        if local_info:
                            self.store_topology(local_info, neighbors)
                    except Exception as e:
                        logger.error(f"Failed to collect from {device['hostname']}: {e}")
                        continue
                
                # Build and log topology graph
                topology = self.build_topology_graph()
                logger.info(f"Topology: {len(topology['nodes'])} nodes, {len(topology['edges'])} edges")
                
                logger.info(f"LLDP collection complete. Sleeping {interval}s")
                time.sleep(interval)
                
            except KeyboardInterrupt:
                logger.info("Stopping LLDP collector")
                break
            except Exception as e:
                logger.error(f"Collection error: {e}")
                time.sleep(60)

if __name__ == '__main__':
    collector = LLDPCollector()
    collector.run(interval=int(os.getenv('LLDP_POLL_INTERVAL', 600)))

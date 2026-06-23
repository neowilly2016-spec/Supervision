#!/usr/bin/env python3
"""
VRF Detection Collector for IPAM Integration

Discovers VRFs (Virtual Routing and Forwarding instances) on network devices
and maps them to VLANs for complete L3 topology visibility.

Supported Devices:
- Juniper MX/EX series: MPLS-L3VPN-STD-MIB, Juniper routing-instances
- Huawei NE series: HUAWEI-L3VPN-MIB

Workflow:
1. Fetch active devices from DB
2. Query VRF instances via SNMP (vendor-specific MIBs)
3. Map VRFs to interfaces
4. Cross-reference with VLAN assignments
5. Upsert to vrfs table with VLAN mappings
"""

import asyncio
import asyncpg
import logging
from typing import Dict, List, Set, Optional
from pysnmp.hlapi.asyncio import *
from datetime import datetime
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SNMP OIDs for VRF detection
SNMP_OIDS = {
    'juniper': {
        'vrf_name': '1.3.6.1.2.1.10.166.11.1.2.2.1.1',  # mplsL3VpnVrfName
        'vrf_descr': '1.3.6.1.2.1.10.166.11.1.2.2.1.3',  # mplsL3VpnVrfDescription
        'vrf_rd': '1.3.6.1.2.1.10.166.11.1.2.2.1.4',     # mplsL3VpnVrfRD
        'if_vrf': '1.3.6.1.2.1.10.166.11.1.2.1.1.3',     # mplsL3VpnIfConfRowStatus
    },
    'huawei': {
        'vrf_name': '1.3.6.1.4.1.2011.5.25.177.1.1.1.1.2',  # hwL3vpnVrfName
        'vrf_descr': '1.3.6.1.4.1.2011.5.25.177.1.1.1.1.3', # hwL3vpnVrfDescription
        'vrf_rd': '1.3.6.1.4.1.2011.5.25.177.1.1.1.1.4',    # hwL3vpnVrfRD
    }
}

class VRFCollector:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.community = os.getenv('SNMP_COMMUNITY', 'public')
    
    async def collect_vrfs(self, device: dict) -> List[Dict]:
        """
        Collect VRF information from a single device
        """
        vrfs = []
        vendor = device['vendor'].lower()
        hostname = device['hostname']
        ip = device['management_ip']
        
        logger.info(f"Discovering VRFs on {hostname} ({vendor})")
        
        if vendor not in SNMP_OIDS:
            logger.warning(f"VRF detection not supported for vendor: {vendor}")
            return vrfs
        
        try:
            # Get VRF names
            vrf_oid = SNMP_OIDS[vendor]['vrf_name']
            async for (errorIndication, errorStatus, errorIndex, varBinds) in bulkCmd(
                SnmpEngine(),
                CommunityData(self.community),
                UdpTransportTarget((ip, 161), timeout=5, retries=2),
                ContextData(),
                0, 25,
                ObjectType(ObjectIdentity(vrf_oid)),
                lexicographicMode=False
            ):
                if errorIndication:
                    logger.error(f"SNMP error on {hostname}: {errorIndication}")
                    break
                elif errorStatus:
                    logger.error(f"SNMP error on {hostname}: {errorStatus.prettyPrint()}")
                    break
                
                for varBind in varBinds:
                    oid, value = varBind
                    if not value:
                        continue
                    
                    vrf_name = str(value)
                    # Extract VRF index from OID
                    vrf_index = str(oid).split('.')[-1]
                    
                    # Get VRF description and RD
                    vrf_info = await self._get_vrf_details(
                        ip, vendor, vrf_index, vrf_name
                    )
                    
                    vrfs.append({
                        'device_id': device['id'],
                        'name': vrf_name,
                        'description': vrf_info.get('description', ''),
                        'rd': vrf_info.get('rd', ''),
                        'vrf_index': vrf_index
                    })
            
            logger.info(f"Found {len(vrfs)} VRFs on {hostname}")
            
        except Exception as e:
            logger.error(f"Failed to collect VRFs from {hostname}: {e}")
        
        return vrfs
    
    async def _get_vrf_details(self, ip: str, vendor: str, 
                               vrf_index: str, vrf_name: str) -> Dict:
        """
        Get additional VRF details (description, RD)
        """
        details = {'description': '', 'rd': ''}
        
        try:
            # Get VRF description
            descr_oid = f"{SNMP_OIDS[vendor]['vrf_descr']}.{vrf_index}"
            iterator = getCmd(
                SnmpEngine(),
                CommunityData(self.community),
                UdpTransportTarget((ip, 161), timeout=3),
                ContextData(),
                ObjectType(ObjectIdentity(descr_oid))
            )
            errorIndication, errorStatus, errorIndex, varBinds = await iterator
            
            if not errorIndication and not errorStatus:
                for varBind in varBinds:
                    details['description'] = str(varBind[1])
            
            # Get VRF RD (Route Distinguisher)
            rd_oid = f"{SNMP_OIDS[vendor]['vrf_rd']}.{vrf_index}"
            iterator = getCmd(
                SnmpEngine(),
                CommunityData(self.community),
                UdpTransportTarget((ip, 161), timeout=3),
                ContextData(),
                ObjectType(ObjectIdentity(rd_oid))
            )
            errorIndication, errorStatus, errorIndex, varBinds = await iterator
            
            if not errorIndication and not errorStatus:
                for varBind in varBinds:
                    details['rd'] = str(varBind[1])
        
        except Exception as e:
            logger.warning(f"Failed to get VRF details for {vrf_name}: {e}")
        
        return details
    
    async def map_vlans_to_vrfs(self, device_id: int) -> Dict[int, int]:
        """
        Map VLANs to VRFs for a device by querying interface assignments
        Returns dict: {vlan_id: vrf_id}
        """
        mappings = {}
        
        try:
            # Query interfaces and their VLAN/VRF assignments
            async with self.db_pool.acquire() as conn:
                # Get VRF IDs for this device
                vrfs = await conn.fetch(
                    "SELECT id, name FROM vrfs WHERE device_id = $1",
                    device_id
                )
                vrf_map = {vrf['name']: vrf['id'] for vrf in vrfs}
                
                # Get VLAN assignments from interfaces
                # This assumes interfaces table has vlan_id and vrf_name columns
                interfaces = await conn.fetch(
                    """
                    SELECT DISTINCT vlan_id, vrf_name 
                    FROM interfaces 
                    WHERE device_id = $1 
                      AND vlan_id IS NOT NULL 
                      AND vrf_name IS NOT NULL
                    """,
                    device_id
                )
                
                for iface in interfaces:
                    vlan_id = iface['vlan_id']
                    vrf_name = iface['vrf_name']
                    if vrf_name in vrf_map:
                        mappings[vlan_id] = vrf_map[vrf_name]
        
        except Exception as e:
            logger.error(f"Failed to map VLANs to VRFs for device {device_id}: {e}")
        
        return mappings
    
    async def sync_to_ipam(self, vrfs: List[Dict]) -> None:
        """
        Upsert VRF records to the vrfs table
        """
        if not vrfs:
            return
        
        async with self.db_pool.acquire() as conn:
            for vrf in vrfs:
                try:
                    await conn.execute(
                        """
                        INSERT INTO vrfs (device_id, name, description, rd, last_seen)
                        VALUES ($1, $2, $3, $4, NOW())
                        ON CONFLICT (device_id, name) 
                        DO UPDATE SET
                            description = EXCLUDED.description,
                            rd = EXCLUDED.rd,
                            last_seen = NOW()
                        """,
                        vrf['device_id'],
                        vrf['name'],
                        vrf['description'],
                        vrf['rd']
                    )
                except Exception as e:
                    logger.error(f"Failed to upsert VRF {vrf['name']}: {e}")

async def main():
    """
    Main collection loop
    """
    db_pool = await asyncpg.create_pool(
        host=os.getenv('DB_HOST', 'timescaledb'),
        port=int(os.getenv('DB_PORT', 5432)),
        user=os.getenv('DB_USER', 'supervision'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME', 'supervision'),
        min_size=2,
        max_size=10
    )
    
    collector = VRFCollector(db_pool)
    
    while True:
        try:
            logger.info("Starting VRF collection cycle")
            
            # Fetch all devices
            async with db_pool.acquire() as conn:
                devices = await conn.fetch(
                    """
                    SELECT id, hostname, management_ip, vendor 
                    FROM devices 
                    WHERE status = 'active'
                    """
                )
            
            # Collect VRFs from each device
            for device in devices:
                vrfs = await collector.collect_vrfs(dict(device))
                await collector.sync_to_ipam(vrfs)
                
                # Map VLANs to VRFs
                vlan_vrf_map = await collector.map_vlans_to_vrfs(device['id'])
                logger.info(f"Mapped {len(vlan_vrf_map)} VLAN-VRF associations for {device['hostname']}")
            
            logger.info("VRF collection cycle completed")
            await asyncio.sleep(3600)  # Run every hour
            
        except Exception as e:
            logger.error(f"Error in VRF collection loop: {e}")
            await asyncio.sleep(300)  # Retry after 5 minutes

if __name__ == "__main__":
    asyncio.run(main())

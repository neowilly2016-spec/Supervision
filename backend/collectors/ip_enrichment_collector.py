#!/usr/bin/env python3
"""
IP Enrichment Collector - IPAM Integration

Enrichit les prefixes IP avec leur contexte réseau réel:
- Associe chaque subnet à son VLAN via l'interface parente
- Associe chaque subnet à son VRF via l'interface parente
- Peuple ip_prefixes.vlan_id et ip_prefixes.vrf_id automatiquement

Logique:
1. Walk ipAddrTable (RFC 1213) → IP + masque + ifIndex
2. Résoud ifIndex → VLAN (dot1qVlanStaticTable / vendor MIB)
3. Résoud ifIndex → VRF (mplsL3VpnIfConfTable / vendor MIB)
4. UPDATE ip_prefixes SET vlan_id = ?, vrf_id = ? WHERE prefix = ?

Vendeurs supportés:
- Juniper MX/EX: mplsL3VpnIfConfTable, jnxL2aldVlanFdbId
- Huawei NE: hwL3vpnIfVrfName, hwL2VlanDescr
"""

import asyncio
import asyncpg
import logging
import ipaddress
from typing import Dict, List, Optional, Tuple
from pysnmp.hlapi.asyncio import *
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SNMP OIDs pour enrichissement IP
SNMP_OIDS = {
    # RFC 1213 - ipAddrTable (IP + ifIndex)
    'ip_addr_table': '1.3.6.1.2.1.4.20.1',  # ipAddrEntry
    'ip_addr': '1.3.6.1.2.1.4.20.1.1',       # ipAdEntAddr
    'ip_if_index': '1.3.6.1.2.1.4.20.1.2',   # ipAdEntIfIndex
    'ip_netmask': '1.3.6.1.2.1.4.20.1.3',    # ipAdEntNetMask
    
    # VLAN resolution per vendor
    'juniper': {
        'vlan_name': '1.3.6.1.4.1.2636.3.40.1.5.1.5.1.5',  # jnxL2aldVlanName
        'vlan_id': '1.3.6.1.4.1.2636.3.40.1.5.1.5.1.6',    # jnxL2aldVlanFdbId
    },
    'huawei': {
        'vlan_if_index': '1.3.6.1.2.1.17.7.1.4.5.1.1',  # dot1qVlanStaticEgressPorts
        'vlan_name': '1.3.6.1.4.1.2011.5.25.42.2.1.3.1.2',  # hwL2VlanDescr
    },
    
    # VRF resolution (standard MPLS-L3VPN-STD-MIB)
    'vrf_if_table': '1.3.6.1.2.1.10.166.11.1.2.1.1',  # mplsL3VpnIfConfEntry
    'vrf_if_name': '1.3.6.1.2.1.10.166.11.1.2.1.1.3',  # mplsL3VpnIfVpnClassification
    
    # Huawei VRF (vendor-specific)
    'huawei_vrf_if': '1.3.6.1.4.1.2011.5.25.177.1.2.1.1.2',  # hwL3vpnIfVrfName
}

class IPEnrichmentCollector:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.community = os.getenv('SNMP_COMMUNITY', 'public')
    
    async def enrich_device(self, device: dict) -> int:
        """
        Enrichit tous les prefixes d'un device avec VLAN/VRF
        Retourne le nombre de prefixes enrichis
        """
        vendor = device['vendor'].lower()
        hostname = device['hostname']
        ip = device['management_ip']
        device_id = device['id']
        
        logger.info(f"Enrichissement IP pour {hostname} ({vendor})")
        
        # Étape 1: Walk ipAddrTable → {IP: (ifIndex, netmask)}
        ip_interfaces = await self._get_ip_interfaces(ip)
        if not ip_interfaces:
            logger.warning(f"Aucune interface IP trouvée sur {hostname}")
            return 0
        
        logger.info(f"  → {len(ip_interfaces)} interfaces IP découvertes")
        
        # Étape 2: Résoudre ifIndex → VLAN ID
        vlan_map = await self._resolve_vlans(ip, vendor, ip_interfaces)
        logger.info(f"  → {len(vlan_map)} interfaces avec VLAN")
        
        # Étape 3: Résoudre ifIndex → VRF name
        vrf_map = await self._resolve_vrfs(ip, vendor, ip_interfaces)
        logger.info(f"  → {len(vrf_map)} interfaces avec VRF")
        
        # Étape 4: Enrichir ip_prefixes dans la DB
        enriched = await self._update_prefixes(
            device_id, ip_interfaces, vlan_map, vrf_map
        )
        
        logger.info(f"✓ {enriched} prefixes enrichis sur {hostname}")
        return enriched
    
    async def _get_ip_interfaces(self, device_ip: str) -> Dict[str, Tuple[int, str]]:
        """
        Walk ipAddrTable → {IP_address: (ifIndex, netmask)}
        """
        ip_map = {}
        
        try:
            async for (errorIndication, errorStatus, errorIndex, varBinds) in bulkCmd(
                SnmpEngine(),
                CommunityData(self.community),
                UdpTransportTarget((device_ip, 161), timeout=5, retries=2),
                ContextData(),
                0, 25,
                ObjectType(ObjectIdentity(SNMP_OIDS['ip_addr_table'])),
                lexicographicMode=False
            ):
                if errorIndication or errorStatus:
                    break
                
                for varBind in varBinds:
                    oid, value = varBind
                    oid_str = str(oid)
                    
                    # ipAdEntAddr: 1.3.6.1.2.1.4.20.1.1.X.X.X.X
                    if '1.3.6.1.2.1.4.20.1.1.' in oid_str:
                        ip_addr = str(value)
                        # Récupérer ifIndex et netmask
                        ifindex_oid = oid_str.replace('.1.1.', '.1.2.')
                        netmask_oid = oid_str.replace('.1.1.', '.1.3.')
                        
                        ifindex = await self._snmp_get(device_ip, ifindex_oid)
                        netmask = await self._snmp_get(device_ip, netmask_oid)
                        
                        if ifindex and netmask:
                            ip_map[ip_addr] = (int(ifindex), str(netmask))
        
        except Exception as e:
            logger.error(f"Erreur SNMP ipAddrTable: {e}")
        
        return ip_map
    
    async def _resolve_vlans(self, device_ip: str, vendor: str, 
                             ip_interfaces: Dict) -> Dict[int, int]:
        """
        Résoud ifIndex → VLAN ID
        Retourne {ifIndex: vlan_vid}
        """
        vlan_map = {}
        
        if vendor not in ['juniper', 'huawei']:
            return vlan_map
        
        # Pour chaque ifIndex, essayer de récupérer le VLAN
        for ip_addr, (ifindex, netmask) in ip_interfaces.items():
            vlan_id = None
            
            if vendor == 'juniper':
                # Juniper: jnxL2aldVlanFdbId indexé par ifIndex
                vlan_oid = f"{SNMP_OIDS['juniper']['vlan_id']}.{ifindex}"
                vlan_id = await self._snmp_get(device_ip, vlan_oid)
            
            elif vendor == 'huawei':
                # Huawei: dot1qVlanStaticTable ou hwL2VlanDescr
                vlan_oid = f"{SNMP_OIDS['huawei']['vlan_name']}.{ifindex}"
                vlan_id = await self._snmp_get(device_ip, vlan_oid)
            
            if vlan_id:
                try:
                    vlan_map[ifindex] = int(vlan_id)
                except ValueError:
                    pass
        
        return vlan_map
    
    async def _resolve_vrfs(self, device_ip: str, vendor: str, 
                            ip_interfaces: Dict) -> Dict[int, str]:
        """
        Résoud ifIndex → VRF name
        Retourne {ifIndex: vrf_name}
        """
        vrf_map = {}
        
        # Essayer MPLS-L3VPN-STD-MIB d'abord (standard)
        for ip_addr, (ifindex, netmask) in ip_interfaces.items():
            vrf_name = None
            
            # Standard MIB
            vrf_oid = f"{SNMP_OIDS['vrf_if_name']}.{ifindex}"
            vrf_name = await self._snmp_get(device_ip, vrf_oid)
            
            # Huawei vendor-specific si échec
            if not vrf_name and vendor == 'huawei':
                vrf_oid = f"{SNMP_OIDS['huawei_vrf_if']}.{ifindex}"
                vrf_name = await self._snmp_get(device_ip, vrf_oid)
            
            if vrf_name:
                vrf_map[ifindex] = str(vrf_name)
        
        return vrf_map
    
    async def _snmp_get(self, device_ip: str, oid: str) -> Optional[str]:
        """
        SNMP GET simple
        """
        try:
            iterator = getCmd(
                SnmpEngine(),
                CommunityData(self.community),
                UdpTransportTarget((device_ip, 161), timeout=3),
                ContextData(),
                ObjectType(ObjectIdentity(oid))
            )
            errorIndication, errorStatus, errorIndex, varBinds = await iterator
            
            if not errorIndication and not errorStatus:
                for varBind in varBinds:
                    return str(varBind[1])
        except:
            pass
        return None
    
    async def _update_prefixes(self, device_id: int, 
                               ip_interfaces: Dict,
                               vlan_map: Dict[int, int],
                               vrf_map: Dict[int, str]) -> int:
        """
        Met à jour ip_prefixes avec vlan_id et vrf_id
        """
        updated = 0
        
        async with self.db_pool.acquire() as conn:
            # Récupérer les mappings VLAN vid → id et VRF name → id
            vlan_id_map = await self._get_vlan_ids(conn)
            vrf_id_map = await self._get_vrf_ids(conn, device_id)
            
            for ip_addr, (ifindex, netmask) in ip_interfaces.items():
                try:
                    # Calculer le prefix CIDR
                    net = ipaddress.IPv4Network(f"{ip_addr}/{netmask}", strict=False)
                    prefix_str = str(net)
                    
                    # Résoudre VLAN et VRF IDs
                    vlan_vid = vlan_map.get(ifindex)
                    vrf_name = vrf_map.get(ifindex)
                    
                    vlan_id = vlan_id_map.get(vlan_vid) if vlan_vid else None
                    vrf_id = vrf_id_map.get(vrf_name) if vrf_name else None
                    
                    # Upsert prefix avec enrichissement
                    result = await conn.execute(
                        """
                        INSERT INTO ip_prefixes 
                            (prefix, prefix_length, vrf_id, vlan_id, status, is_pool)
                        VALUES ($1, $2, $3, $4, 'active', false)
                        ON CONFLICT (prefix) DO UPDATE SET
                            vrf_id = COALESCE(EXCLUDED.vrf_id, ip_prefixes.vrf_id),
                            vlan_id = COALESCE(EXCLUDED.vlan_id, ip_prefixes.vlan_id),
                            updated_at = NOW()
                        """,
                        prefix_str,
                        net.prefixlen,
                        vrf_id,
                        vlan_id
                    )
                    
                    if vlan_id or vrf_id:
                        updated += 1
                        logger.debug(
                            f"  {prefix_str} → VLAN {vlan_vid} (id={vlan_id}), "
                            f"VRF {vrf_name} (id={vrf_id})"
                        )
                
                except Exception as e:
                    logger.error(f"Erreur update prefix {ip_addr}: {e}")
        
        return updated
    
    async def _get_vlan_ids(self, conn) -> Dict[int, int]:
        """
        Retourne {vlan_vid: vlan_id}
        """
        rows = await conn.fetch("SELECT id, vid FROM vlans")
        return {row['vid']: row['id'] for row in rows}
    
    async def _get_vrf_ids(self, conn, device_id: int) -> Dict[str, int]:
        """
        Retourne {vrf_name: vrf_id} pour ce device
        """
        rows = await conn.fetch(
            "SELECT id, name FROM vrfs WHERE device_id = $1",
            device_id
        )
        return {row['name']: row['id'] for row in rows}

async def main():
    """
    Main loop
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
    
    collector = IPEnrichmentCollector(db_pool)
    
    while True:
        try:
            logger.info("=" * 60)
            logger.info("Démarrage cycle d'enrichissement IP → VLAN/VRF")
            logger.info("=" * 60)
            
            async with db_pool.acquire() as conn:
                devices = await conn.fetch(
                    "SELECT id, hostname, management_ip, vendor FROM devices WHERE status = 'active'"
                )
            
            total_enriched = 0
            for device in devices:
                count = await collector.enrich_device(dict(device))
                total_enriched += count
            
            logger.info("=" * 60)
            logger.info(f"✓ Cycle terminé: {total_enriched} prefixes enrichis au total")
            logger.info("=" * 60)
            
            await asyncio.sleep(3600)  # Toutes les heures
        
        except Exception as e:
            logger.error(f"Erreur dans le loop d'enrichissement: {e}")
            await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main())

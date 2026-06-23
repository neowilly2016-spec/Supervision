#!/usr/bin/env python3
"""
IP Discovery Collector for IPAM
Discovers IP addresses configured on network devices via SNMP
Supports: Juniper (MX series) and Huawei (NE series)
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional
import asyncpg
from pysnmp.hlapi.asyncio import *
from ipaddress import ip_address, ip_network, IPv4Address, IPv4Network

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IPDiscoveryCollector:
    """
    Collecte les adresses IP configurées sur les équipements réseaux
    et les synchronise dans la base IPAM
    """
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        
        # OIDs SNMP pour découverte IP
        self.oid_ip_addr_table = '1.3.6.1.2.1.4.20.1.1'  # IP-MIB::ipAdEntAddr
        self.oid_ip_addr_netmask = '1.3.6.1.2.1.4.20.1.3'  # IP-MIB::ipAdEntNetMask
        self.oid_ip_addr_ifindex = '1.3.6.1.2.1.4.20.1.2'  # IP-MIB::ipAdEntIfIndex
        
        # OIDs pour récupérer le nom d'interface
        self.oid_if_descr = '1.3.6.1.2.1.2.2.1.2'  # IF-MIB::ifDescr
        self.oid_if_name = '1.3.6.1.2.1.31.1.1.1.1'  # IF-MIB::ifName
        
    async def discover_all_devices(self):
        """
        Lance la découverte IP sur tous les devices actifs
        """
        async with self.db_pool.acquire() as conn:
            devices = await conn.fetch(
                "SELECT id, hostname, ip_address, snmp_community, vendor "
                "FROM devices WHERE status = 'active'"
            )
        
        logger.info(f"Starting IP discovery on {len(devices)} devices")
        
        tasks = [self.discover_device_ips(device) for device in devices]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success = sum(1 for r in results if not isinstance(r, Exception))
        logger.info(f"IP discovery completed: {success}/{len(devices)} devices successful")
        
        return results
    
    async def discover_device_ips(self, device: Dict) -> List[Dict]:
        """
        Découvre toutes les IPs configurées sur un device
        """
        device_id = device['id']
        hostname = device['hostname']
        ip_address = device['ip_address']
        community = device['snmp_community']
        vendor = device['vendor']
        
        logger.info(f"Discovering IPs on {hostname} ({ip_address})")
        
        try:
            # Récupérer les IPs via SNMP
            ip_data = await self._snmp_get_ip_addresses(ip_address, community)
            
            if not ip_data:
                logger.warning(f"No IPs found on {hostname}")
                return []
            
            # Enrichir avec les noms d'interfaces
            ip_data = await self._enrich_with_interface_names(
                ip_address, community, ip_data, vendor
            )
            
            # Détecter les VRFs (si multi-VRF)
            for ip_info in ip_data:
                vrf_name = await self._detect_vrf(
                    device_id, ip_info['interface'], vendor
                )
                ip_info['vrf_name'] = vrf_name
            
            # Synchroniser avec la base IPAM
            await self._sync_to_ipam(device_id, hostname, ip_data)
            
            logger.info(
                f"Discovered {len(ip_data)} IPs on {hostname}"
            )
            
            return ip_data
            
        except Exception as e:
            logger.error(f"Error discovering IPs on {hostname}: {e}")
            raise
    
    async def _snmp_get_ip_addresses(self, target: str, community: str) -> List[Dict]:
        """
        Récupère les adresses IP via SNMP ipAddrTable
        """
        ip_list = []
        
        # SNMP Walk sur ipAddrTable
        iterator = nextCmd(
            SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((target, 161), timeout=5, retries=2),
            ContextData(),
            ObjectType(ObjectIdentity(self.oid_ip_addr_table)),
            ObjectType(ObjectIdentity(self.oid_ip_addr_netmask)),
            ObjectType(ObjectIdentity(self.oid_ip_addr_ifindex)),
            lexicographicMode=False
        )
        
        async for (errorIndication, errorStatus, errorIndex, varBinds) in iterator:
            if errorIndication:
                logger.error(f"SNMP error: {errorIndication}")
                break
            elif errorStatus:
                logger.error(f"SNMP error: {errorStatus.prettyPrint()}")
                break
            else:
                if len(varBinds) >= 3:
                    ip_addr = str(varBinds[0][1])
                    netmask = str(varBinds[1][1])
                    ifindex = int(varBinds[2][1])
                    
                    # Calculer le préfixe CIDR
                    prefix_length = self._netmask_to_cidr(netmask)
                    prefix = f"{ip_addr}/{prefix_length}"
                    
                    ip_list.append({
                        'address': ip_addr,
                        'netmask': netmask,
                        'prefix': prefix,
                        'prefix_length': prefix_length,
                        'ifindex': ifindex,
                        'interface': f"ifIndex-{ifindex}"  # Temporaire
                    })
        
        return ip_list
    
    async def _enrich_with_interface_names(
        self, 
        target: str, 
        community: str, 
        ip_data: List[Dict],
        vendor: str
    ) -> List[Dict]:
        """
        Enrichit les données IP avec les vrais noms d'interfaces
        """
        # Récupérer le mapping ifIndex -> ifName
        ifindex_map = await self._get_interface_names(target, community, vendor)
        
        for ip_info in ip_data:
            ifindex = ip_info['ifindex']
            ip_info['interface'] = ifindex_map.get(
                ifindex, 
                f"Unknown-{ifindex}"
            )
        
        return ip_data
    
    async def _get_interface_names(
        self, 
        target: str, 
        community: str,
        vendor: str
    ) -> Dict[int, str]:
        """
        Récupère le mapping ifIndex -> interface name
        """
        ifindex_map = {}
        
        # Utiliser ifName (préféré) ou ifDescr
        oid = self.oid_if_name if vendor in ['juniper', 'huawei'] else self.oid_if_descr
        
        iterator = nextCmd(
            SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((target, 161), timeout=5, retries=2),
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False
        )
        
        async for (errorIndication, errorStatus, errorIndex, varBinds) in iterator:
            if not errorIndication and not errorStatus:
                for varBind in varBinds:
                    oid_str, value = varBind
                    # Extraire l'ifIndex de l'OID
                    ifindex = int(str(oid_str).split('.')[-1])
                    ifname = str(value)
                    ifindex_map[ifindex] = ifname
        
        return ifindex_map
    
    async def _detect_vrf(
        self, 
        device_id: int, 
        interface: str, 
        vendor: str
    ) -> Optional[str]:
        """
        Détecte le VRF associé à une interface
        Pour Juniper: utiliser MPLS-VPN-MIB
        Pour Huawei: utiliser HUAWEI-L3VPN-MIB
        """
        # Pour l'instant, retourne 'Global' par défaut
        # TODO: Implémenter détection VRF via SNMP
        return 'Global'
    
    async def _sync_to_ipam(
        self, 
        device_id: int, 
        hostname: str, 
        ip_data: List[Dict]
    ):
        """
        Synchronise les IPs découvertes dans la base IPAM
        """
        async with self.db_pool.acquire() as conn:
            for ip_info in ip_data:
                try:
                    # Récupérer ou créer le VRF
                    vrf_id = await self._get_or_create_vrf(
                        conn, 
                        ip_info['vrf_name']
                    )
                    
                    # Récupérer ou créer le préfixe parent
                    prefix_id = await self._get_or_create_prefix(
                        conn,
                        ip_info['prefix'],
                        vrf_id
                    )
                    
                    # Insérer ou mettre à jour l'IP
                    await conn.execute(
                        """
                        INSERT INTO ip_addresses (
                            address, prefix_id, vrf_id, device_id, 
                            interface_name, discovered_at, status
                        )
                        VALUES ($1, $2, $3, $4, $5, NOW(), 'active')
                        ON CONFLICT (address, vrf_id) 
                        DO UPDATE SET
                            prefix_id = EXCLUDED.prefix_id,
                            device_id = EXCLUDED.device_id,
                            interface_name = EXCLUDED.interface_name,
                            discovered_at = NOW(),
                            status = 'active',
                            updated_at = NOW()
                        """,
                        ip_info['address'],
                        prefix_id,
                        vrf_id,
                        device_id,
                        ip_info['interface']
                    )
                    
                    logger.debug(
                        f"Synced IP {ip_info['address']} on {hostname} "
                        f"({ip_info['interface']})"
                    )
                    
                except Exception as e:
                    logger.error(
                        f"Error syncing IP {ip_info['address']} on {hostname}: {e}"
                    )
    
    async def _get_or_create_vrf(self, conn, vrf_name: str) -> int:
        """
        Récupère ou crée un VRF
        """
        row = await conn.fetchrow(
            "SELECT id FROM vrfs WHERE name = $1",
            vrf_name
        )
        
        if row:
            return row['id']
        
        # Créer le VRF s'il n'existe pas
        row = await conn.fetchrow(
            """
            INSERT INTO vrfs (name, description)
            VALUES ($1, $2)
            ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
            """,
            vrf_name,
            f"Auto-discovered VRF {vrf_name}"
        )
        
        return row['id']
    
    async def _get_or_create_prefix(self, conn, prefix_str: str, vrf_id: int) -> Optional[int]:
        """
        Récupère le prefix_id correspondant ou None
        """
        row = await conn.fetchrow(
            "SELECT id FROM ip_prefixes WHERE prefix = $1 AND vrf_id = $2",
            prefix_str,
            vrf_id
        )
        
        return row['id'] if row else None
    
    def _netmask_to_cidr(self, netmask: str) -> int:
        """
        Convertit un masque de sous-réseau en longueur CIDR
        Ex: 255.255.255.0 -> 24
        """
        return IPv4Address(netmask).max_prefixlen - bin(int(IPv4Address(netmask))).count('0')
    
    async def calculate_prefix_utilization(self):
        """
        Calcule l'utilisation de chaque préfixe et met à jour la DB
        """
        async with self.db_pool.acquire() as conn:
            prefixes = await conn.fetch(
                """
                SELECT id, prefix, prefix_length 
                FROM ip_prefixes 
                WHERE is_pool = true AND status = 'active'
                """
            )
            
            for prefix in prefixes:
                prefix_id = prefix['id']
                network = ip_network(prefix['prefix'])
                total_ips = network.num_addresses - 2  # Exclure network et broadcast
                
                # Compter les IPs allouées
                allocated = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM ip_addresses 
                    WHERE prefix_id = $1 AND status IN ('active', 'reserved')
                    """,
                    prefix_id
                )
                
                utilization = (allocated / total_ips * 100) if total_ips > 0 else 0
                
                # Mettre à jour l'utilisation
                await conn.execute(
                    "UPDATE ip_prefixes SET utilization = $1 WHERE id = $2",
                    round(utilization, 2),
                    prefix_id
                )
                
                # Insérer dans l'historique
                await conn.execute(
                    """
                    INSERT INTO ip_allocation_history (
                        time, prefix_id, vrf_id, site, 
                        total_ips, allocated_ips, available_ips, utilization
                    )
                    SELECT 
                        NOW(), $1, vrf_id, site,
                        $2, $3, $4, $5
                    FROM ip_prefixes WHERE id = $1
                    """,
                    prefix_id,
                    int(total_ips),
                    allocated,
                    int(total_ips - allocated),
                    round(utilization, 2)
                )
                
                # Alerte si utilisation > 80%
                if utilization > 80:
                    logger.warning(
                        f"Prefix {prefix['prefix']} utilization: {utilization:.1f}%"
                    )


async def main():
    """
    Point d'entrée principal du collector
    """
    # Connexion à la base de données
    db_pool = await asyncpg.create_pool(
        host='db',
        port=5432,
        database='supervision',
        user='supervision',
        password='supervision123',
        min_size=2,
        max_size=10
    )
    
    collector = IPDiscoveryCollector(db_pool)
    
    try:
        # Découverte IP sur tous les devices
        await collector.discover_all_devices()
        
        # Calcul de l'utilisation des préfixes
        await collector.calculate_prefix_utilization()
        
    finally:
        await db_pool.close()


if __name__ == '__main__':
    asyncio.run(main())

#!/usr/bin/env python3
"""
VLAN Discovery Collector for IPAM
Discovers VLANs configured on network devices via SNMP
Supports: Juniper (MX series) and Huawei (NE series)
"""

import asyncio
import logging
from typing import List, Dict, Optional
import asyncpg
from pysnmp.hlapi.asyncio import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VLANDiscoveryCollector:
    """
    Collecte les VLANs configurés sur les équipements réseaux
    et les synchronise dans la base IPAM
    """
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        
        # OIDs SNMP pour découverte VLAN
        # IEEE 802.1Q VLAN MIB
        self.oid_dot1q_vlan_static_name = '1.3.6.1.2.1.17.7.1.4.3.1.1'  # Q-BRIDGE-MIB::dot1qVlanStaticName
        self.oid_dot1q_vlan_current = '1.3.6.1.2.1.17.7.1.4.2.1.3'  # Q-BRIDGE-MIB::dot1qVlanCurrentEgressPorts
        
        # Cisco VLAN MIB (fallback)
        self.oid_vtp_vlan_state = '1.3.6.1.4.1.9.9.46.1.3.1.1.2'  # CISCO-VTP-MIB::vtpVlanState
        self.oid_vtp_vlan_type = '1.3.6.1.4.1.9.9.46.1.3.1.1.3'  # CISCO-VTP-MIB::vtpVlanType
        self.oid_vtp_vlan_name = '1.3.6.1.4.1.9.9.46.1.3.1.1.4'  # CISCO-VTP-MIB::vtpVlanName
        
        # Juniper specific
        self.oid_jnx_l2ald_vlan_name = '1.3.6.1.4.1.2636.3.40.1.5.1.5.1.5'  # JUNIPER-L2ALD-MIB::jnxL2aldVlanName
        
        # Huawei specific  
        self.oid_hwl2_vlan_desc = '1.3.6.1.4.1.2011.5.25.42.1.1.1.1.3'  # HUAWEI-L2VLAN-MIB::hwL2VlanDescr
        
    async def discover_all_devices(self):
        """
        Lance la découverte VLAN sur tous les devices actifs
        """
        async with self.db_pool.acquire() as conn:
            devices = await conn.fetch(
                """
                SELECT id, hostname, ip_address, snmp_community, vendor, device_type
                FROM devices 
                WHERE status = 'active'
                """
            )
        
        logger.info(f"Starting VLAN discovery on {len(devices)} devices")
        
        tasks = [self.discover_device_vlans(device) for device in devices]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success = sum(1 for r in results if not isinstance(r, Exception))
        logger.info(f"VLAN discovery completed: {success}/{len(devices)} devices successful")
        
        return results
    
    async def discover_device_vlans(self, device: Dict) -> List[Dict]:
        """
        Découvre tous les VLANs configurés sur un device
        """
        device_id = device['id']
        hostname = device['hostname']
        ip_address = device['ip_address']
        community = device['snmp_community']
        vendor = device['vendor']
        device_type = device['device_type']
        
        logger.info(f"Discovering VLANs on {hostname} ({ip_address})")
        
        try:
            # Choisir la méthode selon le vendor
            if vendor == 'juniper':
                vlan_data = await self._snmp_get_vlans_juniper(ip_address, community)
            elif vendor == 'huawei':
                vlan_data = await self._snmp_get_vlans_huawei(ip_address, community)
            else:
                # Essayer la méthode standard 802.1Q
                vlan_data = await self._snmp_get_vlans_standard(ip_address, community)
            
            if not vlan_data:
                logger.warning(f"No VLANs found on {hostname}")
                return []
            
            # Synchroniser avec la base IPAM
            await self._sync_to_ipam(device_id, hostname, device_type, vlan_data)
            
            logger.info(f"Discovered {len(vlan_data)} VLANs on {hostname}")
            
            return vlan_data
            
        except Exception as e:
            logger.error(f"Error discovering VLANs on {hostname}: {e}")
            raise
    
    async def _snmp_get_vlans_standard(self, target: str, community: str) -> List[Dict]:
        """
        Récupère les VLANs via SNMP standard 802.1Q
        """
        vlan_list = []
        
        # SNMP Walk sur dot1qVlanStaticName
        iterator = nextCmd(
            SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((target, 161), timeout=5, retries=2),
            ContextData(),
            ObjectType(ObjectIdentity(self.oid_dot1q_vlan_static_name)),
            lexicographicMode=False
        )
        
        async for (errorIndication, errorStatus, errorIndex, varBinds) in iterator:
            if errorIndication:
                logger.debug(f"SNMP error (802.1Q): {errorIndication}")
                break
            elif errorStatus:
                logger.debug(f"SNMP error (802.1Q): {errorStatus.prettyPrint()}")
                break
            else:
                for varBind in varBinds:
                    oid_str, value = varBind
                    # Extraire le VLAN ID de l'OID (dernier chiffre)
                    vid = int(str(oid_str).split('.')[-1])
                    vlan_name = str(value)
                    
                    if 1 <= vid <= 4094 and vlan_name:
                        vlan_list.append({
                            'vid': vid,
                            'name': vlan_name,
                            'status': 'active'
                        })
        
        return vlan_list
    
    async def _snmp_get_vlans_juniper(self, target: str, community: str) -> List[Dict]:
        """
        Récupère les VLANs depuis Juniper MX via SNMP
        Utilise JUNIPER-L2ALD-MIB::jnxL2aldVlanName
        """
        vlan_list = []
        
        iterator = nextCmd(
            SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((target, 161), timeout=5, retries=2),
            ContextData(),
            ObjectType(ObjectIdentity(self.oid_jnx_l2ald_vlan_name)),
            lexicographicMode=False
        )
        
        async for (errorIndication, errorStatus, errorIndex, varBinds) in iterator:
            if errorIndication:
                logger.debug(f"SNMP error (Juniper): {errorIndication}")
                # Fallback vers méthode standard
                return await self._snmp_get_vlans_standard(target, community)
            elif errorStatus:
                logger.debug(f"SNMP error (Juniper): {errorStatus.prettyPrint()}")
                return await self._snmp_get_vlans_standard(target, community)
            else:
                for varBind in varBinds:
                    oid_str, value = varBind
                    # Sur Juniper, le VLAN ID peut être dans l'OID
                    parts = str(oid_str).split('.')
                    if len(parts) >= 2:
                        try:
                            vid = int(parts[-2])  # Avant-dernier élément
                            vlan_name = str(value)
                            
                            if 1 <= vid <= 4094 and vlan_name:
                                vlan_list.append({
                                    'vid': vid,
                                    'name': vlan_name,
                                    'status': 'active'
                                })
                        except (ValueError, IndexError):
                            continue
        
        # Si aucun VLAN trouvé, essayer la méthode standard
        if not vlan_list:
            return await self._snmp_get_vlans_standard(target, community)
        
        return vlan_list
    
    async def _snmp_get_vlans_huawei(self, target: str, community: str) -> List[Dict]:
        """
        Récupère les VLANs depuis Huawei NE via SNMP
        Utilise HUAWEI-L2VLAN-MIB::hwL2VlanDescr
        """
        vlan_list = []
        
        iterator = nextCmd(
            SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((target, 161), timeout=5, retries=2),
            ContextData(),
            ObjectType(ObjectIdentity(self.oid_hwl2_vlan_desc)),
            lexicographicMode=False
        )
        
        async for (errorIndication, errorStatus, errorIndex, varBinds) in iterator:
            if errorIndication:
                logger.debug(f"SNMP error (Huawei): {errorIndication}")
                # Fallback vers méthode standard
                return await self._snmp_get_vlans_standard(target, community)
            elif errorStatus:
                logger.debug(f"SNMP error (Huawei): {errorStatus.prettyPrint()}")
                return await self._snmp_get_vlans_standard(target, community)
            else:
                for varBind in varBinds:
                    oid_str, value = varBind
                    # Sur Huawei, le VLAN ID est le dernier élément de l'OID
                    vid = int(str(oid_str).split('.')[-1])
                    vlan_name = str(value)
                    
                    if 1 <= vid <= 4094 and vlan_name:
                        vlan_list.append({
                            'vid': vid,
                            'name': vlan_name,
                            'status': 'active'
                        })
        
        # Si aucun VLAN trouvé, essayer la méthode standard
        if not vlan_list:
            return await self._snmp_get_vlans_standard(target, community)
        
        return vlan_list
    
    async def _sync_to_ipam(
        self,
        device_id: int,
        hostname: str,
        device_type: str,
        vlan_data: List[Dict]
    ):
        """
        Synchronise les VLANs découverts dans la base IPAM
        """
        async with self.db_pool.acquire() as conn:
            for vlan_info in vlan_data:
                try:
                    # Déterminer le site depuis le device_type
                    site = self._determine_site(device_type)
                    
                    # Insérer ou mettre à jour le VLAN
                    vlan_id = await conn.fetchval(
                        """
                        INSERT INTO vlans (vid, name, description, site, status)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (vid, site) 
                        DO UPDATE SET
                            name = EXCLUDED.name,
                            description = EXCLUDED.description,
                            status = EXCLUDED.status,
                            updated_at = NOW()
                        RETURNING id
                        """,
                        vlan_info['vid'],
                        vlan_info['name'],
                        f"Discovered on {hostname}",
                        site,
                        vlan_info['status']
                    )
                    
                    logger.debug(
                        f"Synced VLAN {vlan_info['vid']} ({vlan_info['name']}) "
                        f"on {hostname} (site: {site})"
                    )
                    
                except Exception as e:
                    logger.error(
                        f"Error syncing VLAN {vlan_info['vid']} on {hostname}: {e}"
                    )
    
    def _determine_site(self, device_type: str) -> str:
        """
        Détermine le site depuis le device_type
        """
        if device_type == 'backbone':
            return 'backbone'
        elif device_type in ['mbh', 'mbh_zone1']:
            return 'mbh_zone1'
        elif device_type == 'mbh_zone2':
            return 'mbh_zone2'
        else:
            return 'backbone'  # Par défaut
    
    async def map_vlans_to_vrfs(self):
        """
        Crée les associations VLAN <-> VRF <-> Device
        Note: Nécessite que les VRFs soient déjà découverts
        """
        logger.info("Mapping VLANs to VRFs")
        
        async with self.db_pool.acquire() as conn:
            # Récupérer les devices avec VLANs
            devices = await conn.fetch(
                """
                SELECT DISTINCT d.id, d.hostname, d.ip_address, d.snmp_community
                FROM devices d
                JOIN vlans v ON v.site = d.device_type
                WHERE d.status = 'active'
                """
            )
            
            for device in devices:
                # TODO: Implémenter la logique de mapping VLAN <-> VRF
                # Cela nécessite des requêtes SNMP supplémentaires
                # Pour détecter quel VLAN est dans quel VRF sur chaque device
                pass
        
        logger.info("VLAN to VRF mapping completed")


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
    
    collector = VLANDiscoveryCollector(db_pool)
    
    try:
        # Découverte VLAN sur tous les devices
        await collector.discover_all_devices()
        
        # Mapping VLAN <-> VRF (optionnel)
        await collector.map_vlans_to_vrfs()
        
    finally:
        await db_pool.close()


if __name__ == '__main__':
    asyncio.run(main())

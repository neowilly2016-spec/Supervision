#!/usr/bin/env python3
"""
Optical Metrics Collector - Surveillance TX/RX Power des interfaces optiques
Collecte les parametres optiques via SNMP pour Juniper et Huawei
"""

import os
import logging
import time
from typing import List, Dict, Optional
from pysnmp.hlapi import *
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'timescaledb'),
    'port': os.getenv('POSTGRES_PORT', 5432),
    'database': os.getenv('POSTGRES_DB', 'supervision'),
    'user': os.getenv('POSTGRES_USER', 'supervisor'),
    'password': os.getenv('POSTGRES_PASSWORD', 'supervision123')
}

# ================================================================================
# OIDs SNMP pour les transceivers optiques
# ================================================================================

# Juniper MX Series - Interface Diagnostics MIB (jnxDomCurrentTable)
JUNIPER_OIDS = {
    'ifDescr': '1.3.6.1.2.1.2.2.1.2',  # Interface Description
    'ifOperStatus': '1.3.6.1.2.1.2.2.1.8',  # Interface Operational Status
    
    # Juniper DOM (Digital Optical Monitoring)
    'jnxDomCurrentRxLaserPower': '1.3.6.1.4.1.2636.3.60.1.1.1.1.5',  # RX Power (dBm * 100)
    'jnxDomCurrentTxLaserOutputPower': '1.3.6.1.4.1.2636.3.60.1.1.1.1.7',  # TX Power (dBm * 100)
    'jnxDomCurrentModuleTemperature': '1.3.6.1.4.1.2636.3.60.1.1.1.1.8',  # Temperature (Celsius)
    'jnxDomCurrentTxLaserBiasCurrent': '1.3.6.1.4.1.2636.3.60.1.1.1.1.6',  # TX Bias Current (mA)
    
    # Alarm Thresholds
    'jnxDomCurrentRxLaserPowerHighAlarmThreshold': '1.3.6.1.4.1.2636.3.60.1.1.1.1.9',
    'jnxDomCurrentRxLaserPowerLowAlarmThreshold': '1.3.6.1.4.1.2636.3.60.1.1.1.1.10',
    'jnxDomCurrentTxLaserOutputPowerHighAlarmThreshold': '1.3.6.1.4.1.2636.3.60.1.1.1.1.13',
    'jnxDomCurrentTxLaserOutputPowerLowAlarmThreshold': '1.3.6.1.4.1.2636.3.60.1.1.1.1.14'
}

# Huawei NE Series - Entity Physical Table
HUAWEI_OIDS = {
    'ifDescr': '1.3.6.1.2.1.2.2.1.2',  # Interface Description
    'ifOperStatus': '1.3.6.1.2.1.2.2.1.8',  # Interface Operational Status
    
    # Huawei Optical Transceiver MIB
    'hwOpticsRxPower': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.5',  # RX Power (0.01 dBm)
    'hwOpticsTxPower': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.6',  # TX Power (0.01 dBm)
    'hwOpticsTemperature': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.7',  # Temperature (Celsius)
    'hwOpticsBiasCurrent': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.8',  # Bias Current (0.1 mA)
    'hwOpticsVoltage': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.9',  # Voltage (0.1 mV)
    
    # Alarm Thresholds
    'hwOpticsRxPowerHighThreshold': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.10',
    'hwOpticsRxPowerLowThreshold': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.11',
    'hwOpticsTxPowerHighThreshold': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.12',
    'hwOpticsTxPowerLowThreshold': '1.3.6.1.4.1.2011.5.25.31.1.1.3.1.13'
}


class OpticalMetricsCollector:
    """Collecteur de metriques optiques pour interfaces fibre"""
    
    def __init__(self, db_config: dict = DB_CONFIG):
        self.db_config = db_config
    
    def get_db_connection(self):
        """Creer une connexion PostgreSQL/TimescaleDB"""
        return psycopg2.connect(**self.db_config)
    
    def snmp_walk(self, target: str, community: str, oid: str) -> Dict:
        """
        Effectuer un SNMP WALK sur un OID
        """
        results = {}
        
        try:
            for (errorIndication, errorStatus, errorIndex, varBinds) in nextCmd(
                SnmpEngine(),
                CommunityData(community, mpModel=1),  # SNMPv2c
                UdpTransportTarget((target, 161), timeout=5, retries=2),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
                lexicographicMode=False
            ):
                if errorIndication:
                    logger.error(f"SNMP error for {target}: {errorIndication}")
                    break
                elif errorStatus:
                    logger.error(f"SNMP error for {target}: {errorStatus.prettyPrint()}")
                    break
                else:
                    for varBind in varBinds:
                        oid_str = varBind[0].prettyPrint()
                        value = varBind[1]
                        # Extraire l'index de l'interface depuis l'OID
                        if_index = oid_str.split('.')[-1]
                        results[if_index] = value
        
        except Exception as e:
            logger.error(f"Exception during SNMP walk for {target}: {e}")
        
        return results
    
    def snmp_get(self, target: str, community: str, oids: List[str]) -> Dict:
        """
        Effectuer un SNMP GET pour plusieurs OIDs
        """
        try:
            iterator = getCmd(
                SnmpEngine(),
                CommunityData(community, mpModel=1),
                UdpTransportTarget((target, 161), timeout=5, retries=2),
                ContextData(),
                *[ObjectType(ObjectIdentity(oid)) for oid in oids]
            )
            
            errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
            
            if errorIndication or errorStatus:
                return {}
            
            results = {}
            for i, varBind in enumerate(varBinds):
                results[oids[i]] = varBind[1]
            
            return results
        
        except Exception as e:
            logger.error(f"SNMP GET error for {target}: {e}")
            return {}
    
    def collect_juniper_optical_metrics(self, device_id: int, ip: str, community: str) -> List[Dict]:
        """
        Collecter les metriques optiques pour un equipement Juniper
        """
        metrics = []
        
        # Recuperer les noms d'interfaces
        if_descr_table = self.snmp_walk(ip, community, JUNIPER_OIDS['ifDescr'])
        
        # Recuperer les statistuts operationnels
        if_oper_status_table = self.snmp_walk(ip, community, JUNIPER_OIDS['ifOperStatus'])
        
        # Recuperer les metriques optiques
        rx_power_table = self.snmp_walk(ip, community, JUNIPER_OIDS['jnxDomCurrentRxLaserPower'])
        tx_power_table = self.snmp_walk(ip, community, JUNIPER_OIDS['jnxDomCurrentTxLaserOutputPower'])
        temperature_table = self.snmp_walk(ip, community, JUNIPER_OIDS['jnxDomCurrentModuleTemperature'])
        bias_current_table = self.snmp_walk(ip, community, JUNIPER_OIDS['jnxDomCurrentTxLaserBiasCurrent'])
        
        # Recuperer les seuils d'alarme
        rx_high_alarm_table = self.snmp_walk(ip, community, JUNIPER_OIDS['jnxDomCurrentRxLaserPowerHighAlarmThreshold'])
        rx_low_alarm_table = self.snmp_walk(ip, community, JUNIPER_OIDS['jnxDomCurrentRxLaserPowerLowAlarmThreshold'])
        tx_high_alarm_table = self.snmp_walk(ip, community, JUNIPER_OIDS['jnxDomCurrentTxLaserOutputPowerHighAlarmThreshold'])
        tx_low_alarm_table = self.snmp_walk(ip, community, JUNIPER_OIDS['jnxDomCurrentTxLaserOutputPowerLowAlarmThreshold'])
        
        # Parcourir toutes les interfaces avec des metriques optiques
        for if_index in rx_power_table.keys():
            if_name = str(if_descr_table.get(if_index, f"if{if_index}"))
            if_status = int(if_oper_status_table.get(if_index, 2))  # 1=up, 2=down
            
            # Convertir les valeurs Juniper (valeur * 100 pour dBm)
            rx_power_raw = int(rx_power_table[if_index]) if if_index in rx_power_table else None
            tx_power_raw = int(tx_power_table[if_index]) if if_index in tx_power_table else None
            temperature_raw = int(temperature_table[if_index]) if if_index in temperature_table else None
            bias_current_raw = int(bias_current_table[if_index]) if if_index in bias_current_table else None
            
            rx_high_alarm_raw = int(rx_high_alarm_table[if_index]) if if_index in rx_high_alarm_table else None
            rx_low_alarm_raw = int(rx_low_alarm_table[if_index]) if if_index in rx_low_alarm_table else None
            tx_high_alarm_raw = int(tx_high_alarm_table[if_index]) if if_index in tx_high_alarm_table else None
            tx_low_alarm_raw = int(tx_low_alarm_table[if_index]) if if_index in tx_low_alarm_table else None
            
            if rx_power_raw is None and tx_power_raw is None:
                continue  # Skip interfaces sans donnees optiques
            
            # Conversion en dBm (diviser par 100)
            rx_power_dbm = rx_power_raw / 100.0 if rx_power_raw is not None else None
            tx_power_dbm = tx_power_raw / 100.0 if tx_power_raw is not None else None
            temperature_c = temperature_raw / 1.0 if temperature_raw is not None else None
            bias_current_ma = bias_current_raw / 1.0 if bias_current_raw is not None else None
            
            rx_high_alarm_dbm = rx_high_alarm_raw / 100.0 if rx_high_alarm_raw is not None else None
            rx_low_alarm_dbm = rx_low_alarm_raw / 100.0 if rx_low_alarm_raw is not None else None
            tx_high_alarm_dbm = tx_high_alarm_raw / 100.0 if tx_high_alarm_raw is not None else None
            tx_low_alarm_dbm = tx_low_alarm_raw / 100.0 if tx_low_alarm_raw is not None else None
            
            metric = {
                'device_id': device_id,
                'interface_name': if_name,
                'interface_status': 'up' if if_status == 1 else 'down',
                'rx_power_dbm': rx_power_dbm,
                'tx_power_dbm': tx_power_dbm,
                'temperature_celsius': temperature_c,
                'bias_current_ma': bias_current_ma,
                'voltage_v': None,  # Juniper ne fournit pas cette valeur via SNMP
                'rx_power_high_alarm_dbm': rx_high_alarm_dbm,
                'rx_power_low_alarm_dbm': rx_low_alarm_dbm,
                'tx_power_high_alarm_dbm': tx_high_alarm_dbm,
                'tx_power_low_alarm_dbm': tx_low_alarm_dbm,
                'timestamp': datetime.now()
            }
            
            metrics.append(metric)
            
            logger.info(f"Juniper {ip} {if_name}: RX={rx_power_dbm}dBm TX={tx_power_dbm}dBm Temp={temperature_c}°C")
        
        return metrics
    
    def collect_huawei_optical_metrics(self, device_id: int, ip: str, community: str) -> List[Dict]:
        """
        Collecter les metriques optiques pour un equipement Huawei
        """
        metrics = []
        
        # Recuperer les noms d'interfaces
        if_descr_table = self.snmp_walk(ip, community, HUAWEI_OIDS['ifDescr'])
        
        # Recuperer les status operationnels
        if_oper_status_table = self.snmp_walk(ip, community, HUAWEI_OIDS['ifOperStatus'])
        
        # Recuperer les metriques optiques
        rx_power_table = self.snmp_walk(ip, community, HUAWEI_OIDS['hwOpticsRxPower'])
        tx_power_table = self.snmp_walk(ip, community, HUAWEI_OIDS['hwOpticsTxPower'])
        temperature_table = self.snmp_walk(ip, community, HUAWEI_OIDS['hwOpticsTemperature'])
        bias_current_table = self.snmp_walk(ip, community, HUAWEI_OIDS['hwOpticsBiasCurrent'])
        voltage_table = self.snmp_walk(ip, community, HUAWEI_OIDS['hwOpticsVoltage'])
        
        # Recuperer les seuils d'alarme
        rx_high_alarm_table = self.snmp_walk(ip, community, HUAWEI_OIDS['hwOpticsRxPowerHighThreshold'])
        rx_low_alarm_table = self.snmp_walk(ip, community, HUAWEI_OIDS['hwOpticsRxPowerLowThreshold'])
        tx_high_alarm_table = self.snmp_walk(ip, community, HUAWEI_OIDS['hwOpticsTxPowerHighThreshold'])
        tx_low_alarm_table = self.snmp_walk(ip, community, HUAWEI_OIDS['hwOpticsTxPowerLowThreshold'])
        
        # Parcourir toutes les interfaces avec des metriques optiques
        for if_index in rx_power_table.keys():
            if_name = str(if_descr_table.get(if_index, f"if{if_index}"))
            if_status = int(if_oper_status_table.get(if_index, 2))  # 1=up, 2=down
            
            # Convertir les valeurs Huawei (0.01 dBm)
            rx_power_raw = int(rx_power_table[if_index]) if if_index in rx_power_table else None
            tx_power_raw = int(tx_power_table[if_index]) if if_index in tx_power_table else None
            temperature_raw = int(temperature_table[if_index]) if if_index in temperature_table else None
            bias_current_raw = int(bias_current_table[if_index]) if if_index in bias_current_table else None
            voltage_raw = int(voltage_table[if_index]) if if_index in voltage_table else None
            
            rx_high_alarm_raw = int(rx_high_alarm_table[if_index]) if if_index in rx_high_alarm_table else None
            rx_low_alarm_raw = int(rx_low_alarm_table[if_index]) if if_index in rx_low_alarm_table else None
            tx_high_alarm_raw = int(tx_high_alarm_table[if_index]) if if_index in tx_high_alarm_table else None
            tx_low_alarm_raw = int(tx_low_alarm_table[if_index]) if if_index in tx_low_alarm_table else None
            
            if rx_power_raw is None and tx_power_raw is None:
                continue  # Skip interfaces sans donnees optiques
            
            # Conversion en dBm (diviser par 100 pour Huawei)
            rx_power_dbm = rx_power_raw / 100.0 if rx_power_raw is not None else None
            tx_power_dbm = tx_power_raw / 100.0 if tx_power_raw is not None else None
            temperature_c = temperature_raw / 1.0 if temperature_raw is not None else None
            bias_current_ma = bias_current_raw / 10.0 if bias_current_raw is not None else None  # 0.1 mA
            voltage_v = voltage_raw / 10000.0 if voltage_raw is not None else None  # 0.1 mV -> V
            
            rx_high_alarm_dbm = rx_high_alarm_raw / 100.0 if rx_high_alarm_raw is not None else None
            rx_low_alarm_dbm = rx_low_alarm_raw / 100.0 if rx_low_alarm_raw is not None else None
            tx_high_alarm_dbm = tx_high_alarm_raw / 100.0 if tx_high_alarm_raw is not None else None
            tx_low_alarm_dbm = tx_low_alarm_raw / 100.0 if tx_low_alarm_raw is not None else None
            
            metric = {
                'device_id': device_id,
                'interface_name': if_name,
                'interface_status': 'up' if if_status == 1 else 'down',
                'rx_power_dbm': rx_power_dbm,
                'tx_power_dbm': tx_power_dbm,
                'temperature_celsius': temperature_c,
                'bias_current_ma': bias_current_ma,
                'voltage_v': voltage_v,
                'rx_power_high_alarm_dbm': rx_high_alarm_dbm,
                'rx_power_low_alarm_dbm': rx_low_alarm_dbm,
                'tx_power_high_alarm_dbm': tx_high_alarm_dbm,
                'tx_power_low_alarm_dbm': tx_low_alarm_dbm,
                'timestamp': datetime.now()
            }
            
            metrics.append(metric)
            
            logger.info(f"Huawei {ip} {if_name}: RX={rx_power_dbm}dBm TX={tx_power_dbm}dBm Temp={temperature_c}°C")
        
        return metrics
    
    def save_optical_metrics(self, metrics: List[Dict]):
        """
        Sauvegarder les metriques optiques dans TimescaleDB
        """
        if not metrics:
            return
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            for metric in metrics:
                cursor.execute("""
                    INSERT INTO optical_metrics (
                        device_id, interface_name, interface_status,
                        rx_power_dbm, tx_power_dbm, 
                        temperature_celsius, bias_current_ma, voltage_v,
                        rx_power_high_alarm_dbm, rx_power_low_alarm_dbm,
                        tx_power_high_alarm_dbm, tx_power_low_alarm_dbm,
                        timestamp
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    metric['device_id'],
                    metric['interface_name'],
                    metric['interface_status'],
                    metric['rx_power_dbm'],
                    metric['tx_power_dbm'],
                    metric['temperature_celsius'],
                    metric['bias_current_ma'],
                    metric['voltage_v'],
                    metric['rx_power_high_alarm_dbm'],
                    metric['rx_power_low_alarm_dbm'],
                    metric['tx_power_high_alarm_dbm'],
                    metric['tx_power_low_alarm_dbm'],
                    metric['timestamp']
                ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Saved {len(metrics)} optical metrics to database")
        
        except Exception as e:
            logger.error(f"Error saving optical metrics: {e}")
    
    def collect_all_devices(self):
        """
        Collecter les metriques optiques pour tous les devices actifs
        """
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Recuperer tous les devices actifs (vus dans les dernieres 24h)
            cursor.execute("""
                SELECT id, hostname, ip, vendor
                FROM devices
                WHERE last_seen > NOW() - INTERVAL '24 hours'
                ORDER BY hostname
            """)
            
            devices = cursor.fetchall()
            cursor.close()
            conn.close()
            
            logger.info(f"Collecting optical metrics for {len(devices)} devices")
            
            # Collecter pour chaque device
            for device in devices:
                device_id = device['id']
                ip = device['ip']
                vendor = device['vendor'].lower()
                hostname = device['hostname']
                
                # SNMPv2c community (a parametrer)
                community = os.getenv('SNMP_DEFAULT_COMMUNITY', 'public')
                
                logger.info(f"Collecting optical metrics for {hostname} ({ip}) - {vendor}")
                
                metrics = []
                
                if 'juniper' in vendor or 'junos' in vendor:
                    metrics = self.collect_juniper_optical_metrics(device_id, ip, community)
                elif 'huawei' in vendor:
                    metrics = self.collect_huawei_optical_metrics(device_id, ip, community)
                else:
                    logger.warning(f"Unknown vendor for {hostname}: {vendor}")
                    continue
                
                # Sauvegarder les metriques
                if metrics:
                    self.save_optical_metrics(metrics)
                
                # Pause courte entre devices pour eviter de surcharger
                time.sleep(1)
        
        except Exception as e:
            logger.error(f"Error in collect_all_devices: {e}")


if __name__ == '__main__':
    collector = OpticalMetricsCollector()
    
    logger.info("Starting optical metrics collection...")
    
    while True:
        try:
            collector.collect_all_devices()
            logger.info("Optical metrics collection completed. Sleeping for 300 seconds...")
            time.sleep(300)  # Collecter toutes les 5 minutes
        
        except KeyboardInterrupt:
            logger.info("Optical collector stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(60)

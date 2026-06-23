#!/usr/bin/env python3
"""
Reports Module - Interface Traffic Reports Generator
Genere des rapports de trafic pour interfaces selectionnees avec graphiques et tableaux
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from pydantic import BaseModel

router = APIRouter(prefix="/api/reports", tags=["reports"])

# Database configuration
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'timescaledb'),
    'port': os.getenv('POSTGRES_PORT', 5432),
    'database': os.getenv('POSTGRES_DB', 'supervision'),
    'user': os.getenv('POSTGRES_USER', 'supervisor'),
    'password': os.getenv('POSTGRES_PASSWORD', 'supervision123')
}


class InterfaceTrafficRequest(BaseModel):
    """Request model pour rapport de trafic"""
    device_ids: List[int]
    interface_names: List[str]
    start_time: datetime
    end_time: datetime
    interval: str = '5min'  # 5min, 15min, 1hour, 1day


class InterfaceTrafficStats(BaseModel):
    """Statistiques de trafic pour une interface"""
    device_id: int
    device_hostname: str
    interface_name: str
    # Traffic totaux
    total_in_bytes: int
    total_out_bytes: int
    total_in_gbytes: float
    total_out_gbytes: float
    # Moyennes
    avg_in_bps: float
    avg_out_bps: float
    avg_in_mbps: float
    avg_out_mbps: float
    # Pics
    peak_in_bps: float
    peak_out_bps: float
    peak_in_mbps: float
    peak_out_mbps: float
    # Utilisation
    interface_speed_mbps: Optional[int]
    avg_utilization_in_pct: Optional[float]
    avg_utilization_out_pct: Optional[float]
    peak_utilization_in_pct: Optional[float]
    peak_utilization_out_pct: Optional[float]


class InterfaceTrafficTimeSeries(BaseModel):
    """Serie temporelle de trafic"""
    timestamp: datetime
    in_bps: float
    out_bps: float
    in_mbps: float
    out_mbps: float
    utilization_in_pct: Optional[float]
    utilization_out_pct: Optional[float]


class InterfaceTrafficReport(BaseModel):
    """Rapport complet de trafic interface"""
    device_id: int
    device_hostname: str
    interface_name: str
    stats: InterfaceTrafficStats
    timeseries: List[InterfaceTrafficTimeSeries]


def get_db_connection():
    """Creer une connexion PostgreSQL/TimescaleDB"""
    return psycopg2.connect(**DB_CONFIG)


def get_interface_speed(cursor, device_id: int, interface_name: str) -> Optional[int]:
    """
    Recuperer la vitesse de l'interface en Mbps
    """
    cursor.execute("""
        SELECT if_speed_mbps 
        FROM interfaces 
        WHERE device_id = %s AND if_name = %s
        LIMIT 1
    """, (device_id, interface_name))
    
    result = cursor.fetchone()
    return result['if_speed_mbps'] if result else None


def calculate_statistics(
    cursor, 
    device_id: int, 
    interface_name: str, 
    start_time: datetime, 
    end_time: datetime
) -> dict:
    """
    Calculer les statistiques de trafic pour une interface
    """
    # Recuperer la vitesse de l'interface
    if_speed_mbps = get_interface_speed(cursor, device_id, interface_name)
    
    # Requete pour calculer les statistiques
    cursor.execute("""
        WITH traffic_data AS (
            SELECT 
                in_octets,
                out_octets,
                in_bps,
                out_bps,
                timestamp
            FROM interface_metrics
            WHERE device_id = %s 
                AND interface_name = %s
                AND timestamp BETWEEN %s AND %s
            ORDER BY timestamp
        )
        SELECT 
            -- Traffic totaux (difference entre dernier et premier)
            MAX(in_octets) - MIN(in_octets) as total_in_bytes,
            MAX(out_octets) - MIN(out_octets) as total_out_bytes,
            
            -- Moyennes
            AVG(in_bps) as avg_in_bps,
            AVG(out_bps) as avg_out_bps,
            
            -- Pics
            MAX(in_bps) as peak_in_bps,
            MAX(out_bps) as peak_out_bps
        FROM traffic_data
    """, (device_id, interface_name, start_time, end_time))
    
    stats = cursor.fetchone()
    
    if not stats or stats['total_in_bytes'] is None:
        return None
    
    # Convertir en unites lisibles
    total_in_gbytes = stats['total_in_bytes'] / (1024**3)
    total_out_gbytes = stats['total_out_bytes'] / (1024**3)
    avg_in_mbps = stats['avg_in_bps'] / (1000**2)
    avg_out_mbps = stats['avg_out_bps'] / (1000**2)
    peak_in_mbps = stats['peak_in_bps'] / (1000**2)
    peak_out_mbps = stats['peak_out_bps'] / (1000**2)
    
    # Calculer les pourcentages d'utilisation si vitesse connue
    avg_util_in_pct = None
    avg_util_out_pct = None
    peak_util_in_pct = None
    peak_util_out_pct = None
    
    if if_speed_mbps:
        avg_util_in_pct = (avg_in_mbps / if_speed_mbps) * 100
        avg_util_out_pct = (avg_out_mbps / if_speed_mbps) * 100
        peak_util_in_pct = (peak_in_mbps / if_speed_mbps) * 100
        peak_util_out_pct = (peak_out_mbps / if_speed_mbps) * 100
    
    return {
        'total_in_bytes': stats['total_in_bytes'],
        'total_out_bytes': stats['total_out_bytes'],
        'total_in_gbytes': round(total_in_gbytes, 3),
        'total_out_gbytes': round(total_out_gbytes, 3),
        'avg_in_bps': stats['avg_in_bps'],
        'avg_out_bps': stats['avg_out_bps'],
        'avg_in_mbps': round(avg_in_mbps, 2),
        'avg_out_mbps': round(avg_out_mbps, 2),
        'peak_in_bps': stats['peak_in_bps'],
        'peak_out_bps': stats['peak_out_bps'],
        'peak_in_mbps': round(peak_in_mbps, 2),
        'peak_out_mbps': round(peak_out_mbps, 2),
        'interface_speed_mbps': if_speed_mbps,
        'avg_utilization_in_pct': round(avg_util_in_pct, 2) if avg_util_in_pct else None,
        'avg_utilization_out_pct': round(avg_util_out_pct, 2) if avg_util_out_pct else None,
        'peak_utilization_in_pct': round(peak_util_in_pct, 2) if peak_util_in_pct else None,
        'peak_utilization_out_pct': round(peak_util_out_pct, 2) if peak_util_out_pct else None
    }


def get_timeseries_data(
    cursor,
    device_id: int,
    interface_name: str,
    start_time: datetime,
    end_time: datetime,
    interval: str = '5min'
) -> List[dict]:
    """
    Recuperer les donnees de serie temporelle avec agregation
    """
    # Mapper interval vers time_bucket TimescaleDB
    interval_map = {
        '1min': '1 minute',
        '5min': '5 minutes',
        '15min': '15 minutes',
        '1hour': '1 hour',
        '1day': '1 day'
    }
    
    bucket_interval = interval_map.get(interval, '5 minutes')
    if_speed_mbps = get_interface_speed(cursor, device_id, interface_name)
    
    cursor.execute(f"""
        SELECT 
            time_bucket(%s, timestamp) as bucket,
            AVG(in_bps) as avg_in_bps,
            AVG(out_bps) as avg_out_bps
        FROM interface_metrics
        WHERE device_id = %s 
            AND interface_name = %s
            AND timestamp BETWEEN %s AND %s
        GROUP BY bucket
        ORDER BY bucket
    """, (bucket_interval, device_id, interface_name, start_time, end_time))
    
    results = []
    for row in cursor.fetchall():
        in_mbps = row['avg_in_bps'] / (1000**2)
        out_mbps = row['avg_out_bps'] / (1000**2)
        
        util_in_pct = None
        util_out_pct = None
        if if_speed_mbps:
            util_in_pct = (in_mbps / if_speed_mbps) * 100
            util_out_pct = (out_mbps / if_speed_mbps) * 100
        
        results.append({
            'timestamp': row['bucket'],
            'in_bps': row['avg_in_bps'],
            'out_bps': row['avg_out_bps'],
            'in_mbps': round(in_mbps, 2),
            'out_mbps': round(out_mbps, 2),
            'utilization_in_pct': round(util_in_pct, 2) if util_in_pct else None,
            'utilization_out_pct': round(util_out_pct, 2) if util_out_pct else None
        })
    
    return results


@router.post("/interface-traffic", response_model=List[InterfaceTrafficReport])
async def generate_interface_traffic_report(request: InterfaceTrafficRequest):
    """
    Generer un rapport de trafic pour les interfaces selectionnees
    
    Returns:
        Liste de rapports avec statistiques et series temporelles
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        reports = []
        
        # Pour chaque combinaison device/interface
        for device_id in request.device_ids:
            # Recuperer le hostname du device
            cursor.execute(
                "SELECT hostname FROM devices WHERE id = %s",
                (device_id,)
            )
            device = cursor.fetchone()
            if not device:
                continue
            
            device_hostname = device['hostname']
            
            for interface_name in request.interface_names:
                # Calculer les statistiques
                stats = calculate_statistics(
                    cursor,
                    device_id,
                    interface_name,
                    request.start_time,
                    request.end_time
                )
                
                if not stats:
                    continue
                
                # Recuperer les series temporelles
                timeseries = get_timeseries_data(
                    cursor,
                    device_id,
                    interface_name,
                    request.start_time,
                    request.end_time,
                    request.interval
                )
                
                # Construire le rapport
                report = {
                    'device_id': device_id,
                    'device_hostname': device_hostname,
                    'interface_name': interface_name,
                    'stats': {
                        'device_id': device_id,
                        'device_hostname': device_hostname,
                        'interface_name': interface_name,
                        **stats
                    },
                    'timeseries': timeseries
                }
                
                reports.append(report)
        
        cursor.close()
        conn.close()
        
        return reports
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")


@router.get("/devices")
async def get_devices():
    """
    Recuperer la liste des devices disponibles
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT id, hostname, ip, vendor, model, zone, role
            FROM devices
            WHERE last_seen > NOW() - INTERVAL '24 hours'
            ORDER BY hostname
        """)
        
        devices = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return devices
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching devices: {str(e)}")


@router.get("/devices/{device_id}/interfaces")
async def get_device_interfaces(device_id: int):
    """
    Recuperer la liste des interfaces pour un device
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT 
                if_name as name,
                if_descr as description,
                if_speed_mbps as speed_mbps,
                if_oper_status as status,
                if_admin_status as admin_status
            FROM interfaces
            WHERE device_id = %s
            ORDER BY if_name
        """, (device_id,))
        
        interfaces = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return interfaces
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching interfaces: {str(e)}")

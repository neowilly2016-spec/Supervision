#!/usr/bin/env python3
"""
Backbone & MBH Network Monitoring - Main Application
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import yaml
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='../frontend')
CORS(app)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', 5432),
    'database': os.getenv('DB_NAME', 'supervision'),
    'user': os.getenv('DB_USER', 'admin'),
    'password': os.getenv('DB_PASSWORD', 'admin123')
}

def get_db_connection():
    """Create database connection"""
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

@app.route('/')
def index():
    """Serve frontend"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/devices')
def get_devices():
    """Get all monitored devices"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT d.*, 
                   CASE WHEN d.last_seen > NOW() - INTERVAL '5 minutes' 
                        THEN 'online' ELSE 'offline' END as status
            FROM devices d
            ORDER BY d.hostname
        """)
        devices = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(devices)
    except Exception as e:
        logger.error(f"Error fetching devices: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/devices/<int:device_id>')
def get_device(device_id):
    """Get specific device details"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT d.*, 
                   CASE WHEN d.last_seen > NOW() - INTERVAL '5 minutes' 
                        THEN 'online' ELSE 'offline' END as status
            FROM devices d WHERE d.id = %s
        """, (device_id,))
        device = cur.fetchone()
        cur.close()
        conn.close()
        if device:
            return jsonify(device)
        return jsonify({'error': 'Device not found'}), 404
    except Exception as e:
        logger.error(f"Error fetching device: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/metrics/<int:device_id>')
def get_metrics(device_id):
    """Get device metrics"""
    timerange = request.args.get('timerange', '1h')
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT timestamp, metric_name, value, unit
            FROM metrics
            WHERE device_id = %s
            AND timestamp > NOW() - INTERVAL %s
            ORDER BY timestamp DESC
        """, (device_id, timerange))
        metrics = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/topology')
def get_topology():
    """Get network topology"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get devices
        cur.execute("""
            SELECT id, hostname, type, vendor, site, region,
                   CASE WHEN last_seen > NOW() - INTERVAL '5 minutes' 
                        THEN 'online' ELSE 'offline' END as status
            FROM devices
        """)
        devices = cur.fetchall()
        
        # Get links
        cur.execute("""
            SELECT l.*, 
                   d1.hostname as source_name, 
                   d2.hostname as target_name
            FROM links l
            JOIN devices d1 ON l.source_device_id = d1.id
            JOIN devices d2 ON l.target_device_id = d2.id
        """)
        links = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'nodes': devices,
            'links': links
        })
    except Exception as e:
        logger.error(f"Error fetching topology: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/alerts')
def get_alerts():
    """Get active alerts"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT a.*, d.hostname
            FROM alerts a
            JOIN devices d ON a.device_id = d.id
            WHERE a.status = 'active'
            ORDER BY a.severity DESC, a.timestamp DESC
        """)
        alerts = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(alerts)
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Get dashboard statistics"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        stats = {}
        
        # Total devices
        cur.execute("SELECT COUNT(*) as total FROM devices")
        stats['total_devices'] = cur.fetchone()['total']
        
        # Online devices
        cur.execute("""
            SELECT COUNT(*) as online 
            FROM devices 
            WHERE last_seen > NOW() - INTERVAL '5 minutes'
        """)
        stats['online_devices'] = cur.fetchone()['online']
        
        # Active alerts
        cur.execute("""
            SELECT COUNT(*) as active 
            FROM alerts 
            WHERE status = 'active'
        """)
        stats['active_alerts'] = cur.fetchone()['active']
        
        # Alerts by severity
        cur.execute("""
            SELECT severity, COUNT(*) as count 
            FROM alerts 
            WHERE status = 'active'
            GROUP BY severity
        """)
        stats['alerts_by_severity'] = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# Optical Metrics API Endpoints
# ============================================================

@app.route('/api/optical/devices/<device_id>')
def get_device_optical_metrics(device_id):
    """Get optical metrics for a specific device"""
    timerange = request.args.get('timerange', '24h')
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                time,
                if_index,
                if_name,
                rx_power_dbm,
                tx_power_dbm,
                temperature_celsius,
                bias_current_ma,
                voltage_v
            FROM optical_metrics
            WHERE device_id = %s
              AND time > NOW() - INTERVAL %s
            ORDER BY time DESC, if_index
        """, (device_id, timerange))
        metrics = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"Error fetching optical metrics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/optical/interface/<device_id>/<int:if_index>')
def get_interface_optical_metrics(device_id, if_index):
    """Get optical metrics for a specific interface"""
    timerange = request.args.get('timerange', '24h')
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                time,
                if_name,
                rx_power_dbm,
                tx_power_dbm,
                temperature_celsius,
                bias_current_ma,
                voltage_v
            FROM optical_metrics
            WHERE device_id = %s
              AND if_index = %s
              AND time > NOW() - INTERVAL %s
            ORDER BY time DESC
        """, (device_id, if_index, timerange))
        metrics = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"Error fetching interface optical metrics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/optical/summary/<device_id>')
def get_optical_summary(device_id):
    """Get latest optical metrics summary for all interfaces of a device"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT ON (if_index)
                if_index,
                if_name,
                rx_power_dbm,
                tx_power_dbm,
                temperature_celsius,
                time
            FROM optical_metrics
            WHERE device_id = %s
            ORDER BY if_index, time DESC
        """, (device_id,))
        summary = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(summary)
    except Exception as e:
        logger.error(f"Error fetching optical summary: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================
# IPAM Endpoints - VLANs
# =============================================================

@app.route('/api/ipam/vlans', methods=['GET'])
def get_vlans():
    """List all VLANs with optional filtering by site or status"""
    site = request.args.get('site')
    status = request.args.get('status', 'active')
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        query = "SELECT * FROM vlans WHERE status = %s"
        params = [status]
        if site:
            query += " AND site = %s"
            params.append(site)
        query += " ORDER BY vid ASC"
        cur.execute(query, params)
        vlans = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(vlans)
    except Exception as e:
        logger.error(f"Error fetching VLANs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/ipam/vlans/<int:vlan_id>', methods=['GET'])
def get_vlan(vlan_id):
    """Get a single VLAN by ID"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM vlans WHERE id = %s", (vlan_id,))
        vlan = cur.fetchone()
        cur.close()
        conn.close()
        if not vlan:
            return jsonify({'error': 'VLAN not found'}), 404
        return jsonify(vlan)
    except Exception as e:
        logger.error(f"Error fetching VLAN {vlan_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/ipam/vlans', methods=['POST'])
def create_vlan():
    """Create or update a VLAN entry"""
    data = request.get_json()
    if not data or 'vid' not in data or 'name' not in data:
        return jsonify({'error': 'vid and name are required'}), 400
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO vlans (vid, name, description, site, group_name, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (vid, site) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                group_name = EXCLUDED.group_name,
                status = EXCLUDED.status,
                last_seen = NOW()
            RETURNING *
        """, (
            data['vid'],
            data['name'],
            data.get('description', ''),
            data.get('site', ''),
            data.get('group_name', ''),
            data.get('status', 'active')
        ))
        vlan = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return jsonify(vlan), 201
    except Exception as e:
        logger.error(f"Error creating VLAN: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================================
# IPAM Endpoints - VRFs
# =============================================================

@app.route('/api/ipam/vrfs', methods=['GET'])
def get_vrfs():
    """List all VRFs, optionally filtered by device_id"""
    device_id = request.args.get('device_id')
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if device_id:
            cur.execute(
                "SELECT v.*, d.hostname FROM vrfs v "
                "JOIN devices d ON v.device_id = d.id "
                "WHERE v.device_id = %s ORDER BY v.name",
                (device_id,)
            )
        else:
            cur.execute(
                "SELECT v.*, d.hostname FROM vrfs v "
                "JOIN devices d ON v.device_id = d.id "
                "ORDER BY d.hostname, v.name"
            )
        vrfs = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(vrfs)
    except Exception as e:
        logger.error(f"Error fetching VRFs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/ipam/vrfs/<int:vrf_id>', methods=['GET'])
def get_vrf(vrf_id):
    """Get a single VRF with its VLAN mappings"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT v.*, d.hostname FROM vrfs v "
            "JOIN devices d ON v.device_id = d.id "
            "WHERE v.id = %s",
            (vrf_id,)
        )
        vrf = cur.fetchone()
        if not vrf:
            cur.close()
            conn.close()
            return jsonify({'error': 'VRF not found'}), 404
        # Get associated VLANs
        cur.execute("""
            SELECT vl.* FROM vlans vl
            JOIN vlan_vrf_mapping m ON vl.id = m.vlan_id
            WHERE m.vrf_id = %s
        """, (vrf_id,))
        vrf['vlans'] = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(vrf)
    except Exception as e:
        logger.error(f"Error fetching VRF {vrf_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/ipam/vlan-vrf-mapping', methods=['GET'])
def get_vlan_vrf_mapping():
    """Get all VLAN-to-VRF mappings with device context"""
    device_id = request.args.get('device_id')
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        query = """
            SELECT m.id, m.device_id, d.hostname,
                   vl.vid, vl.name AS vlan_name, vl.site,
                   vr.name AS vrf_name, vr.rd
            FROM vlan_vrf_mapping m
            JOIN devices d ON m.device_id = d.id
            JOIN vlans vl ON m.vlan_id = vl.id
            JOIN vrfs vr ON m.vrf_id = vr.id
        """
        params = []
        if device_id:
            query += " WHERE m.device_id = %s"
            params.append(device_id)
        query += " ORDER BY d.hostname, vr.name, vl.vid"
        cur.execute(query, params)
        mappings = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(mappings)
    except Exception as e:


# =============================================================
# IPAM Endpoints - IP Prefixes
# =============================================================

@app.route('/api/ipam/prefixes', methods=['GET'])
def get_prefixes():
    """List IP prefixes with optional filters (vlan_id, vrf_id, status)"""
    vlan_id = request.args.get('vlan_id')
    vrf_id = request.args.get('vrf_id')
    status = request.args.get('status', 'active')
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        query = """
            SELECT p.*, 
                   vl.vid, vl.name AS vlan_name,
                   vr.name AS vrf_name, vr.rd
            FROM ip_prefixes p
            LEFT JOIN vlans vl ON p.vlan_id = vl.id
            LEFT JOIN vrfs vr ON p.vrf_id = vr.id
            WHERE p.status = %s
        """
        params = [status]
        if vlan_id:
            query += " AND p.vlan_id = %s"
            params.append(vlan_id)
        if vrf_id:
            query += " AND p.vrf_id = %s"
            params.append(vrf_id)
        query += " ORDER BY p.prefix"
        cur.execute(query, params)
        prefixes = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(prefixes)
    except Exception as e:
        logger.error(f"Error fetching prefixes: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/ipam/prefixes/<int:prefix_id>', methods=['GET'])
def get_prefix(prefix_id):
    """Get a single prefix with full enrichment (VLAN + VRF)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT p.*, 
                   vl.vid, vl.name AS vlan_name, vl.site,
                   vr.name AS vrf_name, vr.rd, vr.description AS vrf_description
            FROM ip_prefixes p
            LEFT JOIN vlans vl ON p.vlan_id = vl.id
            LEFT JOIN vrfs vr ON p.vrf_id = vr.id
            WHERE p.id = %s
        """, (prefix_id,))
        prefix = cur.fetchone()
        cur.close()
        conn.close()
        if not prefix:
            return jsonify({'error': 'Prefix not found'}), 404
        return jsonify(prefix)
    except Exception as e:
        logger.error(f"Error fetching prefix {prefix_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/ipam/prefixes/utilization', methods=['GET'])
def get_prefix_utilization():
    """Get prefix utilization summary (total, used, available)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                COUNT(*) AS total_prefixes,
                SUM(CASE WHEN is_pool = true THEN 1 ELSE 0 END) AS pool_prefixes,
                AVG(utilization) AS avg_utilization,
                SUM(CASE WHEN vlan_id IS NOT NULL THEN 1 ELSE 0 END) AS enriched_with_vlan,
                SUM(CASE WHEN vrf_id IS NOT NULL THEN 1 ELSE 0 END) AS enriched_with_vrf
            FROM ip_prefixes
            WHERE status = 'active'
        """)
        stats = cur.fetchone()
        cur.close()
        conn.close()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error fetching prefix utilization: {e}")
        return jsonify({'error': str(e)}), 500
        logger.error(f"Error fetching VLAN-VRF mappings: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('APP_PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

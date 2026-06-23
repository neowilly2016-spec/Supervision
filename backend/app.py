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

if __name__ == '__main__':
    port = int(os.getenv('APP_PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

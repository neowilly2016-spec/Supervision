-- ============================================================
-- Schema PostgreSQL / TimescaleDB
-- Backbone & MBH Monitoring
-- ============================================================

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- TABLE: devices
-- ============================================================
CREATE TABLE IF NOT EXISTS devices (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    hostname        VARCHAR(128) NOT NULL UNIQUE,
    ip_address      INET NOT NULL,
    device_type     VARCHAR(32),   -- router, switch, microwave
    vendor          VARCHAR(32),   -- juniper, huawei, ericsson
    model           VARCHAR(64),
    role            VARCHAR(32),   -- PE, P, MBH-AGG, MBH-MW
    site            VARCHAR(64),
    region          VARCHAR(64),
    snmp_version    VARCHAR(4) DEFAULT '2c',
    snmp_community  VARCHAR(64) DEFAULT 'public',
    snmp_v3_user    VARCHAR(64),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABLE: interfaces
-- ============================================================
CREATE TABLE IF NOT EXISTS interfaces (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id       UUID REFERENCES devices(id) ON DELETE CASCADE,
    if_index        INTEGER NOT NULL,
    if_name         VARCHAR(128),
    if_descr        VARCHAR(256),
    if_type         INTEGER,
    if_speed        BIGINT,
    if_admin_status SMALLINT,  -- 1=up, 2=down
    if_oper_status  SMALLINT,  -- 1=up, 2=down
    ip_address      INET,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(device_id, if_index)
);

-- ============================================================
-- TABLE: interface_metrics (TimescaleDB hypertable)
-- ============================================================
CREATE TABLE IF NOT EXISTS interface_metrics (
    time            TIMESTAMPTZ NOT NULL,
    device_id       UUID NOT NULL,
    if_index        INTEGER NOT NULL,
    in_octets       BIGINT,
    out_octets      BIGINT,
    in_errors       BIGINT,
    out_errors      BIGINT,
    in_bps          DOUBLE PRECISION,
    out_bps         DOUBLE PRECISION,
    utilization_in  DOUBLE PRECISION,
    utilization_out DOUBLE PRECISION
);

SELECT create_hypertable('interface_metrics', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_iface_metrics_device ON interface_metrics (device_id, time DESC);

-- ============================================================
-- TABLE: bgp_peers
-- ============================================================
CREATE TABLE IF NOT EXISTS bgp_peers (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id       UUID REFERENCES devices(id) ON DELETE CASCADE,
    peer_ip         INET NOT NULL,
    peer_as         INTEGER,
    local_as        INTEGER,
    peer_state      SMALLINT,  -- 1=idle,2=connect,3=active,4=opensent,5=openconfirm,6=established
    admin_status    SMALLINT,
    in_updates      BIGINT,
    out_updates     BIGINT,
    uptime_secs     INTEGER,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(device_id, peer_ip)
);

-- ============================================================
-- TABLE: bgp_metrics (TimescaleDB hypertable)
-- ============================================================
CREATE TABLE IF NOT EXISTS bgp_metrics (
    time            TIMESTAMPTZ NOT NULL,
    device_id       UUID NOT NULL,
    peer_ip         INET NOT NULL,
    peer_state      SMALLINT,
    in_updates      BIGINT,
    out_updates     BIGINT,
    uptime_secs     INTEGER
);

SELECT create_hypertable('bgp_metrics', 'time', if_not_exists => TRUE);

-- ============================================================
-- TABLE: mpls_tunnels
-- ============================================================
CREATE TABLE IF NOT EXISTS mpls_tunnels (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id       UUID REFERENCES devices(id) ON DELETE CASCADE,
    tunnel_name     VARCHAR(128),
    tunnel_index    INTEGER,
    ingress_lsr     INET,
    egress_lsr      INET,
    tunnel_state    SMALLINT,   -- 1=up, 0=down
    bandwidth_bps   BIGINT,
    lsp_type        VARCHAR(16), -- rsvp, ldp, sr
    transitions     INTEGER DEFAULT 0,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(device_id, tunnel_index)
);

-- ============================================================
-- TABLE: mpls_metrics (TimescaleDB hypertable)
-- ============================================================
CREATE TABLE IF NOT EXISTS mpls_metrics (
    time            TIMESTAMPTZ NOT NULL,
    device_id       UUID NOT NULL,
    tunnel_index    INTEGER NOT NULL,
    tunnel_state    SMALLINT,
    in_octets       BIGINT,
    out_octets      BIGINT,
    transitions     INTEGER
);

SELECT create_hypertable('mpls_metrics', 'time', if_not_exists => TRUE);

-- ============================================================
-- TABLE: mbh_links (liens microwave MBH)
-- ============================================================
CREATE TABLE IF NOT EXISTS mbh_links (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id       UUID REFERENCES devices(id) ON DELETE CASCADE,
    link_name       VARCHAR(128),
    far_end_device  UUID REFERENCES devices(id),
    frequency_ghz   NUMERIC(6,3),
    modulation      VARCHAR(16),
    capacity_mbps   INTEGER,
    link_status     SMALLINT DEFAULT 0, -- 1=up, 0=down
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABLE: mbh_metrics (TimescaleDB hypertable)
-- ============================================================
CREATE TABLE IF NOT EXISTS mbh_metrics (
    time            TIMESTAMPTZ NOT NULL,
    device_id       UUID NOT NULL,
    link_name       VARCHAR(128),
    rx_level_dbm    NUMERIC(6,2),   -- RSSI
    tx_level_dbm    NUMERIC(6,2),
    ber             DOUBLE PRECISION,  -- Bit Error Rate
    modulation      VARCHAR(16),
    capacity_mbps   INTEGER,
    link_status     SMALLINT,
    in_bps          DOUBLE PRECISION,
    out_bps         DOUBLE PRECISION,
    utilization     DOUBLE PRECISION
);

SELECT create_hypertable('mbh_metrics', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_mbh_metrics_device ON mbh_metrics (device_id, time DESC);

-- ============================================================
-- TABLE: topology_links (liens decouverts via LLDP)
-- ============================================================
CREATE TABLE IF NOT EXISTS topology_links (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    local_device_id UUID REFERENCES devices(id) ON DELETE CASCADE,
    local_port      VARCHAR(128),
    remote_device_id UUID REFERENCES devices(id),
    remote_hostname VARCHAR(128),
    remote_port     VARCHAR(128),
    link_type       VARCHAR(16) DEFAULT 'lldp',
    discovered_at   TIMESTAMPTZ DEFAULT NOW(),
    last_seen       TIMESTAMPTZ DEFAULT NOW(),
    is_active       BOOLEAN DEFAULT TRUE
);

-- ============================================================
-- TABLE: alerts
-- ============================================================
CREATE TABLE IF NOT EXISTS alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id       UUID REFERENCES devices(id) ON DELETE CASCADE,
    alert_type      VARCHAR(64),  -- interface_down, bgp_down, mpls_lsp_down, mbh_low_rssi
    severity        VARCHAR(16),  -- critical, major, minor, warning
    source          VARCHAR(128), -- interface name, peer IP, tunnel name
    message         TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    triggered_at    TIMESTAMPTZ DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    ack_at          TIMESTAMPTZ,
    ack_by          VARCHAR(64)
);

CREATE INDEX IF NOT EXISTS idx_alerts_device ON alerts (device_id, triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts (is_active, severity);

-- ============================================================
-- TABLE: device_metrics (CPU, RAM, uptime)
-- ============================================================
CREATE TABLE IF NOT EXISTS device_metrics (
    time            TIMESTAMPTZ NOT NULL,
    device_id       UUID NOT NULL,
    cpu_percent     DOUBLE PRECISION,
    mem_percent     DOUBLE PRECISION,
    uptime_secs     BIGINT,
    temperature     DOUBLE PRECISION
);

SELECT create_hypertable('device_metrics', 'time', if_not_exists => TRUE);

-- ============================================================
-- TABLE: optical_metrics (TimescaleDB hypertable)
-- ============================================================
CREATE TABLE IF NOT EXISTS optical_metrics (
    time TIMESTAMPTZ NOT NULL,
    device_id UUID NOT NULL,
    if_index INTEGER NOT NULL,
    if_name VARCHAR(128),
    rx_power_dbm NUMERIC(8,3),      -- Optical RX power in dBm
    tx_power_dbm NUMERIC(8,3),      -- Optical TX power in dBm
    temperature_celsius NUMERIC(6,2), -- Module temperature in °C
    bias_current_ma NUMERIC(6,2),   -- Laser bias current in mA
    voltage_v NUMERIC(5,2)          -- Supply voltage in V
);

SELECT create_hypertable('optical_metrics', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_optical_metrics_device ON optical_metrics (device_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_optical_metrics_interface ON optical_metrics (device_id, if_index, time DESC);

-- ============================================================
-- Vues utiles
-- ============================================================

-- Vue: etat actuel des interfaces
CREATE OR REPLACE VIEW v_interfaces_status AS
SELECT
    d.hostname,
    d.site,
    d.region,
    i.if_name,
    i.if_descr,
    CASE i.if_oper_status WHEN 1 THEN 'up' WHEN 2 THEN 'down' ELSE 'unknown' END AS oper_status,
    CASE i.if_admin_status WHEN 1 THEN 'up' WHEN 2 THEN 'down' ELSE 'unknown' END AS admin_status,
    i.if_speed,
    i.updated_at
FROM interfaces i
JOIN devices d ON d.id = i.device_id
WHERE d.is_active = TRUE;

-- Vue: sessions BGP down
CREATE OR REPLACE VIEW v_bgp_down AS
SELECT
    d.hostname,
    d.site,
    b.peer_ip,
    b.peer_as,
    CASE b.peer_state
        WHEN 1 THEN 'idle'
        WHEN 2 THEN 'connect'
        WHEN 3 THEN 'active'
        WHEN 4 THEN 'opensent'
        WHEN 5 THEN 'openconfirm'
        WHEN 6 THEN 'established'
        ELSE 'unknown'
    END AS state,
    b.updated_at
FROM bgp_peers b
JOIN devices d ON d.id = b.device_id
WHERE b.peer_state != 6
  AND d.is_active = TRUE;

-- Vue: alertes actives
CREATE OR REPLACE VIEW v_active_alerts AS
SELECT
    a.id,
    d.hostname,
    d.site,
    a.alert_type,
    a.severity,
    a.source,
    a.message,
    a.triggered_at
FROM alerts a
JOIN devices d ON d.id = a.device_id
WHERE a.is_active = TRUE
ORDER BY
    CASE a.severity
        WHEN 'critical' THEN 1
        WHEN 'major' THEN 2
        WHEN 'minor' THEN 3
        WHEN 'warning' THEN 4
        ELSE 5
    END,
    a.triggered_at DESC;

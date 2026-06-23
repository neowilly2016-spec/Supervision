-- ============================================
-- IPAM (IP Address Management) Schema
-- Custom integrated solution for Supervision
-- ============================================

-- ============ VRFs (Virtual Routing and Forwarding) ============
CREATE TABLE IF NOT EXISTS vrfs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL
    device_id INTEGER REFERENCES devices(id) ON DELETE CASCADE,
    rd VARCHAR(50),  -- Route Distinguisher (ex: 65000:100)
    description TEXT,
    import_targets TEXT[],  -- RT import ["65000:100", "65000:200"]
    export_targets TEXT[],  -- RT export ["65000:100"]
    enforce_unique BOOLEAN DEFAULT true,  -- Enforce unique IPs across this VRF
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
    UNIQUE(device_id, name)
);

CREATE INDEX idx_vrfs_name ON vrfs(name);
CREATE INDEX idx_vrfs_rd ON vrfs(rd);

-- ============ VLANs ============
CREATE TABLE IF NOT EXISTS vlans (
    id SERIAL PRIMARY KEY,
    vid INTEGER NOT NULL CHECK (vid >= 1 AND vid <= 4094),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    site VARCHAR(100),  -- backbone, mbh_zone1, mbh_zone2
    group_name VARCHAR(100),  -- VLAN group (ex: backbone, mbh, management)
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'reserved', 'deprecated')),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(vid, site)
);

CREATE INDEX idx_vlans_vid ON vlans(vid);
CREATE INDEX idx_vlans_site ON vlans(site);
CREATE INDEX idx_vlans_status ON vlans(status);

-- ============ VLAN to VRF Mapping ============
CREATE TABLE IF NOT EXISTS vlan_vrf_mapping (
    id SERIAL PRIMARY KEY,
    vlan_id INTEGER NOT NULL REFERENCES vlans(id) ON DELETE CASCADE,
    vrf_id INTEGER NOT NULL REFERENCES vrfs(id) ON DELETE CASCADE,
    device_id INTEGER REFERENCES devices(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(vlan_id, vrf_id, device_id)
);

CREATE INDEX idx_vlan_vrf_vlan ON vlan_vrf_mapping(vlan_id);
CREATE INDEX idx_vlan_vrf_vrf ON vlan_vrf_mapping(vrf_id);
CREATE INDEX idx_vlan_vrf_device ON vlan_vrf_mapping(device_id);

-- ============ IP Prefixes (Supernets and Subnets) ============
CREATE TABLE IF NOT EXISTS ip_prefixes (
    id SERIAL PRIMARY KEY,
    prefix CIDR NOT NULL,
    prefix_length INTEGER NOT NULL,
    description TEXT,
    vrf_id INTEGER REFERENCES vrfs(id) ON DELETE SET NULL,
    vlan_id INTEGER REFERENCES vlans(id) ON DELETE SET NULL,
    site VARCHAR(100),  -- backbone, mbh_zone1, mbh_zone2
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'reserved', 'deprecated')),
    is_pool BOOLEAN DEFAULT false,  -- Utilisable pour allocation automatique
    role VARCHAR(50),  -- loopback, p2p, lan, wan, management
    utilization DECIMAL(5,2) DEFAULT 0.00,  -- % utilisation (0-100)
    parent_prefix_id INTEGER REFERENCES ip_prefixes(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(prefix, vrf_id)
);

CREATE INDEX idx_ip_prefixes_prefix ON ip_prefixes USING GIST(prefix inet_ops);
CREATE INDEX idx_ip_prefixes_vrf ON ip_prefixes(vrf_id);
CREATE INDEX idx_ip_prefixes_site ON ip_prefixes(site);
CREATE INDEX idx_ip_prefixes_status ON ip_prefixes(status);
CREATE INDEX idx_ip_prefixes_is_pool ON ip_prefixes(is_pool);
CREATE INDEX idx_ip_prefixes_parent ON ip_prefixes(parent_prefix_id);

-- ============ IP Addresses ============
CREATE TABLE IF NOT EXISTS ip_addresses (
    id SERIAL PRIMARY KEY,
    address INET NOT NULL,
    prefix_id INTEGER REFERENCES ip_prefixes(id) ON DELETE SET NULL,
    vrf_id INTEGER REFERENCES vrfs(id) ON DELETE SET NULL,
    device_id INTEGER REFERENCES devices(id) ON DELETE SET NULL,
    interface_name VARCHAR(100),
    dns_name VARCHAR(255),
    description TEXT,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'reserved', 'dhcp', 'slaac', 'deprecated')),
    role VARCHAR(50),  -- loopback, anycast, vip, hsrp, vrrp
    nat_inside_ip INET,  -- NAT inside address
    nat_outside_ip INET,  -- NAT outside address
    discovered_at TIMESTAMPTZ,  -- Quand l'IP a été découverte via SNMP
    assigned_at TIMESTAMPTZ DEFAULT NOW(),  -- Quand l'IP a été assignée
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(address, vrf_id)
);

CREATE INDEX idx_ip_addresses_address ON ip_addresses(address);
CREATE INDEX idx_ip_addresses_prefix ON ip_addresses(prefix_id);
CREATE INDEX idx_ip_addresses_vrf ON ip_addresses(vrf_id);
CREATE INDEX idx_ip_addresses_device ON ip_addresses(device_id);
CREATE INDEX idx_ip_addresses_status ON ip_addresses(status);
CREATE INDEX idx_ip_addresses_dns ON ip_addresses(dns_name);

-- ============ IPAM Audit Log ============
CREATE TABLE IF NOT EXISTS ipam_audit_log (
    id SERIAL PRIMARY KEY,
    object_type VARCHAR(50) NOT NULL CHECK (object_type IN ('ip_address', 'ip_prefix', 'vlan', 'vrf', 'vlan_vrf_mapping')),
    object_id INTEGER NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('create', 'update', 'delete')),
    old_value JSONB,
    new_value JSONB,
    changed_fields TEXT[],  -- Liste des champs modifiés
    user_id INTEGER,
    username VARCHAR(100),
    ip_source INET,  -- IP source de la modification
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ipam_audit_object ON ipam_audit_log(object_type, object_id);
CREATE INDEX idx_ipam_audit_timestamp ON ipam_audit_log(timestamp DESC);
CREATE INDEX idx_ipam_audit_user ON ipam_audit_log(user_id);

-- ============ IP Allocation History (TimescaleDB Hypertable) ============
CREATE TABLE IF NOT EXISTS ip_allocation_history (
    time TIMESTAMPTZ NOT NULL,
    prefix_id INTEGER NOT NULL REFERENCES ip_prefixes(id) ON DELETE CASCADE,
    vrf_id INTEGER REFERENCES vrfs(id),
    site VARCHAR(100),
    total_ips BIGINT,
    allocated_ips INTEGER,
    available_ips INTEGER,
    reserved_ips INTEGER,
    utilization DECIMAL(5,2),
    PRIMARY KEY (time, prefix_id)
);

-- Convertir en hypertable TimescaleDB
SELECT create_hypertable('ip_allocation_history', 'time', if_not_exists => TRUE);

-- Compression après 7 jours
ALTER TABLE ip_allocation_history SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'prefix_id,vrf_id,site'
);

SELECT add_compression_policy('ip_allocation_history', INTERVAL '7 days', if_not_exists => TRUE);

-- Rétention 365 jours
SELECT add_retention_policy('ip_allocation_history', INTERVAL '365 days', if_not_exists => TRUE);

-- ============ Functions et Triggers ============

-- Fonction: Calculer automatiquement prefix_length
CREATE OR REPLACE FUNCTION set_prefix_length()
RETURNS TRIGGER AS $$
BEGIN
    NEW.prefix_length := masklen(NEW.prefix);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_set_prefix_length
BEFORE INSERT OR UPDATE ON ip_prefixes
FOR EACH ROW EXECUTE FUNCTION set_prefix_length();

-- Fonction: Auto-assigner prefix_id à une IP
CREATE OR REPLACE FUNCTION auto_assign_prefix()
RETURNS TRIGGER AS $$
DECLARE
    matching_prefix_id INTEGER;
BEGIN
    IF NEW.prefix_id IS NULL THEN
        SELECT id INTO matching_prefix_id
        FROM ip_prefixes
        WHERE NEW.address <<= prefix  -- IP contenue dans le préfixe
          AND (vrf_id = NEW.vrf_id OR (vrf_id IS NULL AND NEW.vrf_id IS NULL))
        ORDER BY masklen(prefix) DESC  -- Plus spécifique en premier
        LIMIT 1;
        
        NEW.prefix_id := matching_prefix_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_auto_assign_prefix
BEFORE INSERT OR UPDATE ON ip_addresses
FOR EACH ROW EXECUTE FUNCTION auto_assign_prefix();

-- Fonction: Mettre à jour updated_at automatiquement
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_vrfs_updated_at BEFORE UPDATE ON vrfs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_vlans_updated_at BEFORE UPDATE ON vlans
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ip_prefixes_updated_at BEFORE UPDATE ON ip_prefixes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ip_addresses_updated_at BEFORE UPDATE ON ip_addresses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Fonction: Audit log trigger
CREATE OR REPLACE FUNCTION ipam_audit_trigger()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO ipam_audit_log (object_type, object_id, action, new_value)
        VALUES (TG_TABLE_NAME, NEW.id, 'create', row_to_json(NEW));
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO ipam_audit_log (object_type, object_id, action, old_value, new_value)
        VALUES (TG_TABLE_NAME, NEW.id, 'update', row_to_json(OLD), row_to_json(NEW));
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO ipam_audit_log (object_type, object_id, action, old_value)
        VALUES (TG_TABLE_NAME, OLD.id, 'delete', row_to_json(OLD));
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_vrfs AFTER INSERT OR UPDATE OR DELETE ON vrfs
    FOR EACH ROW EXECUTE FUNCTION ipam_audit_trigger();

CREATE TRIGGER audit_vlans AFTER INSERT OR UPDATE OR DELETE ON vlans
    FOR EACH ROW EXECUTE FUNCTION ipam_audit_trigger();

CREATE TRIGGER audit_ip_prefixes AFTER INSERT OR UPDATE OR DELETE ON ip_prefixes
    FOR EACH ROW EXECUTE FUNCTION ipam_audit_trigger();

CREATE TRIGGER audit_ip_addresses AFTER INSERT OR UPDATE OR DELETE ON ip_addresses
    FOR EACH ROW EXECUTE FUNCTION ipam_audit_trigger();

-- ============ Views utiles ============

-- Vue: Préfixes avec statistiques
CREATE OR REPLACE VIEW v_prefix_utilization AS
SELECT 
    p.id,
    p.prefix,
    p.prefix_length,
    p.description,
    p.site,
    p.status,
    v.name as vrf_name,
    vl.vid as vlan_id,
    vl.name as vlan_name,
    COALESCE(ip_stats.total_ips, 0) as total_ips,
    COALESCE(ip_stats.allocated_ips, 0) as allocated_ips,
    COALESCE(ip_stats.available_ips, 0) as available_ips,
    ROUND(
        (COALESCE(ip_stats.allocated_ips::decimal, 0) / 
         NULLIF(ip_stats.total_ips, 0)) * 100, 
        2
    ) as utilization_pct
FROM ip_prefixes p
LEFT JOIN vrfs v ON p.vrf_id = v.id
LEFT JOIN vlans vl ON p.vlan_id = vl.id
LEFT JOIN LATERAL (
    SELECT 
        COUNT(*) as allocated_ips,
        2^(32 - p.prefix_length) as total_ips,
        2^(32 - p.prefix_length) - COUNT(*) as available_ips
    FROM ip_addresses ia
    WHERE ia.prefix_id = p.id
      AND ia.status IN ('active', 'reserved')
) ip_stats ON true;

-- Vue: IP avec informations complètes
CREATE OR REPLACE VIEW v_ip_addresses_full AS
SELECT 
    ia.id,
    ia.address,
    ia.dns_name,
    ia.description,
    ia.status,
    ia.role,
    ia.interface_name,
    d.hostname as device_hostname,
    d.ip_address as device_mgmt_ip,
    d.device_type,
    p.prefix,
    v.name as vrf_name,
    vl.vid as vlan_id,
    vl.name as vlan_name,
    ia.discovered_at,
    ia.assigned_at
FROM ip_addresses ia
LEFT JOIN devices d ON ia.device_id = d.id
LEFT JOIN ip_prefixes p ON ia.prefix_id = p.id
LEFT JOIN vrfs v ON ia.vrf_id = v.id
LEFT JOIN vlans vl ON p.vlan_id = vl.id;

-- Vue: VLANs avec mapping VRF et devices
CREATE OR REPLACE VIEW v_vlans_full AS
SELECT 
    vl.id,
    vl.vid,
    vl.name,
    vl.description,
    vl.site,
    vl.status,
    v.name as vrf_name,
    v.rd as vrf_rd,
    COUNT(DISTINCT vvm.device_id) as device_count,
    ARRAY_AGG(DISTINCT d.hostname) FILTER (WHERE d.hostname IS NOT NULL) as devices
FROM vlans vl
LEFT JOIN vlan_vrf_mapping vvm ON vl.id = vvm.vlan_id
LEFT JOIN vrfs v ON vvm.vrf_id = v.id
LEFT JOIN devices d ON vvm.device_id = d.id
GROUP BY vl.id, vl.vid, vl.name, vl.description, vl.site, vl.status, v.name, v.rd;

-- ============ Données initiales ============

-- VRF Global (par défaut)
INSERT INTO vrfs (name, description, enforce_unique) 
VALUES ('Global', 'Default VRF (Global Routing Table)', true)
ON CONFLICT (name) DO NOTHING;

-- VLANs management communs
INSERT INTO vlans (vid, name, description, site, group_name) VALUES
(1, 'default', 'Default VLAN', 'backbone', 'management'),
(10, 'management', 'Management VLAN', 'backbone', 'management'),
(100, 'backbone_core', 'Backbone Core VLAN', 'backbone', 'core'),
(200, 'mbh_zone1', 'MBH Zone 1 Access', 'mbh_zone1', 'access'),
(300, 'mbh_zone2', 'MBH Zone 2 Access', 'mbh_zone2', 'access')
ON CONFLICT (vid, site) DO NOTHING;

-- Préfixes RFC1918 pour tests
INSERT INTO ip_prefixes (prefix, description, site, is_pool, role) VALUES
('10.0.0.0/8', 'Private Class A', 'backbone', false, 'wan'),
('172.16.0.0/12', 'Private Class B', 'backbone', false, 'wan'),
('192.168.0.0/16', 'Private Class C', 'backbone', false, 'lan')
ON CONFLICT (prefix, vrf_id) DO NOTHING;

COMMIT;

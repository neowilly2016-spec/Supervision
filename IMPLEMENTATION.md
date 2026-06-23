# IMPLEMENTATION GUIDE
## Supervision - Network Monitoring Platform (LibreNMS-inspired)

---

## 1. OBJECTIF ET PÉRIMÈTRE

### 1.1 Vue d'ensemble

Cette solution de monitoring réseau est conçue pour superviser l'infrastructure Backbone (Juniper MX960, Huawei NE9000) et Mobile Backhaul (Juniper MX480/MX204/MX104, Huawei NE5000E) avec une approche haute performance inspirée de LibreNMS.
### 1.2 Fonctionnalités principales

- **Auto-découverte dynamique** : SNMP, LLDP, BGP-LS pour découverte automatique des équipements
- **Classification intelligente** : Distinction automatique Backbone vs MBH basée sur sysName/IP ranges
- **Monitoring temps réel** :
  - Métriques optiques (TX/RX power)
  - BGP peers et états
  - Topologie LLDP avec visualisation
  - Performance interface (trafic, erreurs, 95th percentile)
  - MPLS-TE tunnels
  - Syslog centralisé
- **Backup configurations** : Oxidized pour versioning automatique
- **Visualisation Grafana** : Dashboards pré-configurés pour analyse temps réel
- **Haute performance** :
  - TimescaleDB pour time-series optimization
  - Redis pour cache et queuing
  - gRPC telemetry (Juniper JTI, Huawei gRPC)
  - Compression hypertables

### 1.3 Périmètre technique

- **SNMPv2c uniquement** (pas de v3 dans cette version)
- **Auto-découverte** : Pas d'inventaire statique Huawei
- **Scalabilité** : Optimisé pour 100-500 devices
- **Déploiement** : Docker Compose (dev/test) ou Kubernetes (production)

---

## 2. ARCHITECTURE

### 2.1 Diagramme d'architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                         │
│         - Configuration UI                                      │
│         - Device Management                                     │
│         - Alert Configuration                                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API Backend (Flask)                          │
│         - REST API                                              │
│         - Device CRUD                                           │
│         - Authentication                                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
    ┌─────────────┐  ┌─────────────┐  ┌──────────────┐
    │  PostgreSQL │  │    Redis    │  │   Grafana    │
    │ TimescaleDB │  │   Cache +   │  │ Dashboards   │
    │  (Metrics)  │  │   Queue     │  │              │
    └──────┬──────┘  └─────────────┘  └──────────────┘
           │
           │
┌──────────┴────────────────────────────────────────────────────┐
│                    Collectors (Python)                         │
├────────────────────────────────────────────────────────────────┤
│  - SNMP Poller (interfaces, optical, CPU, mem)                │
│  - BGP Monitor (peers, prefixes, uptime)                      │
│  - LLDP Topology Builder                                      │
│  - Syslog Receiver (UDP 514)                                  │
│  - MPLS-TE Tunnel Monitor                                     │
│  - gRPC Telemetry (Juniper JTI, Huawei)                      │
└────────────────────────────┬──────────────────────────────────┘
                             │
                             ▼
              ┌─────────────────────────────┐
              │        Oxidized             │
              │  (Config Backup & Version)  │
              └─────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              Network Devices (SNMP/gRPC/SSH)                    │
│  - Juniper MX960 (Backbone)                                     │
│  - Huawei NE9000 (Mobile Backhaul)                             │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Stack technologique

| Composant | Technologie | Rôle |
|-----------|------------|------|
| Frontend | React + Vite | Interface utilisateur configuration/admin |
| API | Flask (Python) | Backend REST API |
| Database | PostgreSQL 15 + TimescaleDB | Stockage time-series optimisé |
| Cache | Redis 7 Alpine | Cache + Job Queue |
| Visualization | Grafana 10.4.1 | Dashboards et alerting |
| Collectors | Python asyncio | Polling SNMP, gRPC, Syslog |
| Config Backup | Oxidized | Versioning configurations |
| Orchestration | Docker Compose | Déploiement conteneurs |

---

## 3. MODÈLE DE DONNÉES

### 3.1 Tables principales

#### devices
```sql
CREATE TABLE devices (
    id SERIAL PRIMARY KEY,
    hostname VARCHAR(255) UNIQUE NOT NULL,
    ip_address INET NOT NULL,
    device_type VARCHAR(50),  -- backbone, mbh, unknown
    vendor VARCHAR(50),       -- juniper, huawei
    model VARCHAR(100),
    snmp_community VARCHAR(255),
    snmp_version VARCHAR(10) DEFAULT 'v2c',
    status VARCHAR(20) DEFAULT 'active',
    last_seen TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### interface_metrics (Hypertable TimescaleDB)
```sql
CREATE TABLE interface_metrics (
    time TIMESTAMPTZ NOT NULL,
    device_id INTEGER REFERENCES devices(id),
    interface_name VARCHAR(100),
    if_in_octets BIGINT,
    if_out_octets BIGINT,
    if_in_errors BIGINT,
    if_out_errors BIGINT,
    if_in_discards BIGINT,
    if_out_discards BIGINT,
    if_speed BIGINT,
    if_admin_status INTEGER,
    if_oper_status INTEGER
);
SELECT create_hypertable('interface_metrics', 'time');
```

#### optical_metrics (Hypertable)
```sql
CREATE TABLE optical_metrics (
    time TIMESTAMPTZ NOT NULL,
    device_id INTEGER REFERENCES devices(id),
    interface_name VARCHAR(100),
    tx_power DECIMAL(10,2),    -- dBm
    rx_power DECIMAL(10,2),    -- dBm
    temperature DECIMAL(5,2),
    voltage DECIMAL(5,2),
    laser_bias DECIMAL(5,2)
);
SELECT create_hypertable('optical_metrics', 'time');
```

#### bgp_peers
```sql
CREATE TABLE bgp_peers (
    time TIMESTAMPTZ NOT NULL,
    device_id INTEGER REFERENCES devices(id),
    peer_ip INET,
    peer_as INTEGER,
    peer_state VARCHAR(20),
    prefixes_received INTEGER,
    prefixes_sent INTEGER,
    uptime BIGINT,
    flap_count INTEGER
);
SELECT create_hypertable('bgp_peers', 'time');
```

#### lldp_neighbors
```sql
CREATE TABLE lldp_neighbors (
    id SERIAL PRIMARY KEY,
    device_id INTEGER REFERENCES devices(id),
    local_port VARCHAR(100),
    neighbor_device VARCHAR(255),
    neighbor_port VARCHAR(100),
    neighbor_chassis_id VARCHAR(255),
    discovered_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### syslog_events
```sql
CREATE TABLE syslog_events (
    time TIMESTAMPTZ NOT NULL,
    device_id INTEGER,
    hostname VARCHAR(255),
    facility VARCHAR(50),
    severity VARCHAR(20),
    message TEXT,
    raw_message TEXT
);
SELECT create_hypertable('syslog_events', 'time');
```

### 3.2 Politiques de rétention

```sql
-- Compression automatique après 7 jours
ALTER TABLE interface_metrics SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'device_id,interface_name'
);

SELECT add_compression_policy('interface_metrics', INTERVAL '7 days');

-- Rétention 90 jours pour métriques détaillées
SELECT add_retention_policy('interface_metrics', INTERVAL '90 days');

-- Rétention 365 jours pour syslog
SELECT add_retention_policy('syslog_events', INTERVAL '365 days');
```

---

## 4. SERVICES DOCKER

### 4.1 Vue d'ensemble des services

Le fichier `docker-compose.yml` définit 8 services :

1. **db** : PostgreSQL + TimescaleDB
2. **redis** : Cache et queue manager
3. **collector** : SNMP/BGP/LLDP/Optical polling
4. **api** : Flask REST API
5. **frontend** : React UI
6. **grafana** : Visualisation et dashboards
7. **oxidized** : Backup configurations
8. **syslog** : Syslog collector UDP 514

### 4.2 Configuration réseau

Tous les services communiquent via le réseau `supervision_net` (bridge driver).

### 4.3 Volumes persistants

```yaml
volumes:
  postgres_data:      # Données PostgreSQL/TimescaleDB
  grafana_data:       # Dashboards et config Grafana
  oxidized_data:      # Configs Git versionnées
```

### 4.4 Variables d'environnement (.env)

```env
# PostgreSQL
POSTGRES_DB=supervision
POSTGRES_USER=supervision
POSTGRES_PASSWORD=supervision123

# Grafana
GRAFANA_ADMIN_USER=admin
GRAFANA_PASSWORD=admin123
GRAFANA_SECRET_KEY=SW2YcwTIb9zpOOhoPsMm

# SMTP (optional)
SMTP_ENABLED=false
SMTP_HOST=smtp.gmail.com:587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@supervision.local
```

---

## 5. DASHBOARDS GRAFANA

### 5.1 Dashboards pré-configurés

Les dashboards sont provisionnés automatiquement depuis `config/grafana/provisioning/dashboards/` :

#### 1. **Backbone Overview**
- Carte des devices Backbone
- CPU/Memory utilization
- Top interfaces par trafic
- BGP peers status
- Alertes actives

#### 2. **MBH Monitoring**
- Liste des sites MBH
- Performance liens radio/fiber
- Optical power trending
- Latency et jitter

#### 3. **BGP Monitoring**
- Peers status matrix
- Prefixes received/sent graphs
- Flap history
- AS path analysis

#### 4. **Optical Metrics**
- TX/RX power heatmap
- Threshold violations (< -20 dBm)
- Temperature trending
- SFP diagnostics

#### 5. **Network Topology** (LLDP)
- Graphe interactif des voisinages
- Port mapping
- Détection changements topologie

#### 6. **Syslog Viewer**
- Logs en temps réel
- Filtres par severity/facility
- Event correlation
- Top sources syslog

#### 7. **Performance - 95th Percentile**
- Calcul 95th pour billing
- Trending mensuel
- Interface burst detection

### 5.2 Datasource TimescaleDB

Datasource PostgreSQL configurée dans `config/grafana/provisioning/datasources/timescaledb.yml` :

```yaml
apiVersion: 1
datasources:
  - name: TimescaleDB
    type: postgres
    url: db:5432
    database: ${POSTGRES_DB}
    user: ${POSTGRES_USER}
    secureJsonData:
      password: ${POSTGRES_PASSWORD}
    jsonData:
      sslmode: disable
      postgresVersion: 1500
      timescaledb: true
```

---

## 6. FLUX DE DONNÉES

### 6.1 Découverte et polling

```
1. Auto-discovery (network_discovery.py)
   ├─ Scan subnet ranges définis
   ├─ SNMP sysDescr query
   ├─ Classification (Backbone si MX/MX960, MBH si NE)
   └─ INSERT dans table devices

2. SNMP Collector (collectors/snmp_poller.py)
   ├─ Récupère liste devices actifs
   ├─ asyncio pool pour polling parallèle
   ├─ OIDs : ifTable, ifXTable, entPhysicalTable
   └─ INSERT interface_metrics (batch)

3. Optical Collector (collectors/optical_collector.py)
   ├─ OIDs spécifiques Juniper/Huawei
   ├─ Parsing TX/RX power (ENTITY-SENSOR-MIB)
   └─ INSERT optical_metrics

4. BGP Collector (collectors/bgp_monitor.py)
   ├─ BGP4-MIB (peers, state, prefixes)
   ├─ Détection flaps (state changes)
   └─ INSERT bgp_peers

5. LLDP Topology (collectors/lldp_topology.py)
   ├─ LLDP-MIB neighbors
   ├─ Construction graphe relations
   └─ UPDATE lldp_neighbors
```

### 6.2 Pipeline syslog

```
Device ──(UDP 514)──▶ syslog_collector.py
                       ├─ Parse RFC5424/RFC3164
                       ├─ Extract: hostname, facility, severity
                       ├─ Device lookup (hostname → device_id)
                       └─ INSERT syslog_events
                           └─▶ Grafana Syslog Dashboard
```

### 6.3 Backup Oxidized

```
Scheduler (cron)
   └─▶ Oxidized
        ├─ SSH/Telnet vers devices
        ├─ Execute: "show configuration | no-more"
        ├─ Git commit si changement
        └─ Push vers oxidized_data volume
```

---

## 7. DÉPLOIEMENT

### 7.1 Prérequis

- Docker Engine 24.0+
- Docker Compose 2.20+
- 4 GB RAM minimum (8 GB recommandé)
- 20 GB espace disque

### 7.2 Installation locale

```bash
# 1. Cloner le repository
git clone https://github.com/neowilly2016-spec/Supervision.git
cd Supervision

# 2. Créer fichier .env
cp .env.example .env
# Éditer .env avec vos valeurs

# 3. Créer répertoires de configuration
mkdir -p config/oxidized
mkdir -p config/grafana/provisioning/{datasources,dashboards}

# 4. Lancer les services
docker-compose up -d

# 5. Vérifier les logs
docker-compose logs -f

# 6. Initialiser la base de données
docker-compose exec db psql -U supervision -d supervision -f /docker-entrypoint-initdb.d/init.sql

# 7. Accès interfaces
# - Frontend: http://localhost:80
# - Grafana: http://localhost:3000 (admin/admin123)
# - API: http://localhost:5000
# - Oxidized: http://localhost:8888
```

### 7.3 Configuration initiale

#### Ajouter devices via API

```bash
curl -X POST http://localhost:5000/api/devices \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "mx960-core-01",
    "ip_address": "10.0.1.1",
    "device_type": "backbone",
    "vendor": "juniper",
    "model": "MX960",
    "snmp_community": "public"
  }'
```

#### Configurer Oxidized

Éditer `config/oxidized/config.yml` :

```yaml
username: admin
password: password
model: junos
interval: 3600
use_syslog: false
debug: false
threads: 30
timeout: 20
retries: 3
prompt: !ruby/regexp /^([\w.@-]+[#>]\s?)$/

source:
  default: http
  http:
    url: http://api:5000/api/oxidized/devices
    map:
      name: hostname
      model: vendor
      username: oxidized_user
      password: oxidized_pass

output:
  default: git
  git:
    user: Oxidized
    email: oxidized@supervision.local
    repo: "/root/.config/oxidized/configs.git"
```

### 7.4 Health checks

```bash
# Vérifier tous les services
docker-compose ps

# Tester PostgreSQL
docker-compose exec db pg_isready -U supervision

# Tester Redis
docker-compose exec redis redis-cli ping

# Tester API
curl http://localhost:5000/health

# Tester Grafana
curl http://localhost:3000/api/health
```

---

## 8. OPÉRATIONS

### 8.1 Backup et restauration

#### Backup PostgreSQL

```bash
# Backup complet
docker-compose exec db pg_dump -U supervision supervision > backup_$(date +%Y%m%d).sql

# Backup avec compression
docker-compose exec db pg_dump -U supervision supervision | gzip > backup_$(date +%Y%m%d).sql.gz
```

#### Restauration

```bash
# Restaurer depuis backup
docker-compose exec -T db psql -U supervision -d supervision < backup_20250101.sql
```

### 8.2 Monitoring des collectors

```bash
# Logs collector SNMP
docker-compose logs -f collector

# Logs syslog
docker-compose logs -f syslog

# Stats Redis (queue depth)
docker-compose exec redis redis-cli INFO stats
```

### 8.3 Scaling

#### Augmenter workers collectors

Modifier `docker-compose.yml` :

```yaml
collector:
  deploy:
    replicas: 3  # Lancer 3 instances collector
```

#### Optimiser TimescaleDB

```sql
-- Augmenter chunk interval (par défaut 7 jours)
SELECT set_chunk_time_interval('interface_metrics', INTERVAL '1 day');

-- Activer parallel workers
ALTER DATABASE supervision SET max_parallel_workers_per_gather = 4;
```

### 8.4 Alerting

#### Configurer alertes Grafana

1. Dashboard → Panel → Alert tab
2. Définir condition (ex: `rx_power < -20`)
3. Configurer notification channel (email, Slack, etc.)
4. Tester alerte

#### Exemple: Alerte Optical Power

```sql
-- Query Grafana Alert
SELECT 
  time,
  device_id,
  interface_name,
  rx_power
FROM optical_metrics
WHERE 
  time > NOW() - INTERVAL '5 minutes'
  AND rx_power < -20
```

### 8.5 Maintenance

#### Nettoyage logs Docker

```bash
docker system prune -a --volumes
```

#### Vacuum PostgreSQL

```bash
docker-compose exec db psql -U supervision -d supervision -c "VACUUM ANALYZE;"
```

#### Redémarrage services

```bash
# Redémarrer service spécifique
docker-compose restart collector

# Redémarrer tous les services
docker-compose restart
```

---

## 9. LIMITATIONS ET ÉVOLUTIONS

### 9.1 Limitations actuelles

- **SNMPv3** : Non supporté (uniquement v2c)
- **Multi-tenancy** : Pas de support organisations multiples
- **HA/Clustering** : Configuration single-node uniquement
- **Authentification** : Basic auth uniquement (pas OAuth/LDAP)
- **Weathermap** : Pas d'interface graphique auto-générée
- **API Rate limiting** : Non implémenté

### 9.2 Roadmap

#### Phase 2 (Q2 2025)
- [ ] Support SNMPv3 avec authentification
- [ ] Weathermap automatique basé sur LLDP
- [ ] MPLS-TE tunnel monitoring complet
- [ ] API GraphQL en complément REST
- [ ] Intégration Netbox pour IPAM
- [ ] Alerting ML (anomaly detection)

#### Phase 3 (Q3 2025)
- [ ] High Availability (PostgreSQL replication, Redis Sentinel)
- [ ] Kubernetes Helm Charts
- [ ] Support SNMPv3 bulk operations
- [ ] Integration Slack/Teams pour alerting
- [ ] Mobile app (React Native)
- [ ] Export compliance rapports (PDF, Excel)

#### Phase 4 (Q4 2025)
- [ ] Support protocoles additionnels (Netflow, IPFIX)
- [ ] SD-WAN monitoring
- [ ] Network automation (Ansible playbooks intégrés)
- [ ] AI-powered capacity planning

### 9.3 Contributions

Les contributions sont bienvenues via Pull Requests sur GitHub.

**Guidelines** :
- Respecter PEP 8 pour Python
- Tests unitaires requis
- Documentation à jour
- Commit messages descriptifs

---

## 10. SUPPORT ET CONTACT

- **Repository** : https://github.com/neowilly2016-spec/Supervision
- **Issues** : https://github.com/neowilly2016-spec/Supervision/issues
- **Author** : neowilly2016-spec

---

**Dernière mise à jour** : $(date +"%d/%m/%Y")
**Version** : 1.0.0

# 🌐 Backbone & MBH Network Monitoring - Performance Edition

> Outil de supervision haute performance pour l'infrastructure Backbone (Juniper MX960, Huawei NE9000) et Mobile Backhaul (MBH)

## 🗺️ Vue d'ensemble

Solution complète de monitoring réseau optimisée pour superviser:
- **Backbone**: Juniper MX960 (BGP, ISIS, MPLS, LDP, RSVP, Segment Routing)
- **MBH Zone 1 (Juniper)**: MX480, MX204, MX104 avec ISIS/MPLS
- **MBH Zone 2 (Huawei)**: NE9000, NE5000E avec ISIS/MPLS
- **Topologie**: Découverte automatique via LLDP/CDP
- **Télémétrie**: gRPC streaming + SNMPv2
- **Intelligence**: Détection anomalies ML pour BGP/ISIS

## ⚡ Optimisations Performance

### 🚀 Nouvelles fonctionnalités

- **Cache Redis**: Stockage en mémoire des métriques récentes
- **Compression TimescaleDB**: Réduction 90% stockage données > 7 jours
- **Polling adaptatif**: Intervalles optimisés par type d'équipement
- **Télémétrie gRPC**: Streaming temps réel depuis Juniper/Huawei
- **ML Anomaly Detection**: Prédiction pannes BGP/ISIS
- **Architecture distribuée**: Support multi-instances backend

### 📊 Métriques collectées

#### Backbone (Juniper MX960 & Huawei NE9000)
- **BGP**: Sessions, prefixes, flaps, AS-path changes, peer uptime
- **ISIS**: Adjacences, SPF runs, LSP database size, hello packets
- **MPLS**: LSPs actifs, bandwidth utilization, FEC states, transitions
- **Interfaces**: Utilisation, erreurs, CRC, optical levels (dBm), FEC errors
- **Système**: CPU, mémoire, température, alimentation

#### MBH Zone 1 - Juniper (MX480/MX204/MX104)
- **ISIS**: Adjacences MBH, métriques liens, SPF events
- **MPLS**: Tunnels vers Backbone, LSP bandwidth
- **Interfaces**: Trafic agrégation, queue drops par CoS
- **Loopback**: 10.200.x.y (x = numéro wilaya)

#### MBH Zone 2 - Huawei (NE9000/NE5000E)
- **ISIS**: Adjacences MBH, métriques liens
- **MPLS**: Tunnels vers Backbone, TE tunnels
- **Segment Routing**: SID allocation, SRTE policies
- **Loopback**: 10.44.x.y

## 🏗️ Architecture haute performance

```
┌────────────────── FRONTEND ──────────────────┐
│   React + TypeScript + Recharts + Leaflet    │
│   WebSocket (updates temps réel)             │
└────────────────┬─────────────────────────────┘
                 │ REST API + WebSocket
┌────────────────▼─────────────────────────────┐
│        BACKEND (FastAPI + Celery)            │
│  ┌──────────┬──────────┬──────────────────┐  │
│  │ gRPC     │ SNMPv2   │ LLDP/CDP         │  │
│  │ Streaming│ Collector│ Discovery        │  │
│  └──────────┴──────────┴──────────────────┘  │
│  ┌──────────────────────────────────────┐    │
│  │   ML Anomaly Detection Engine        │    │
│  │   (Isolation Forest + Prophet)       │    │
│  └──────────────────────────────────────┘    │
└────────┬──────────────┬──────────────────────┘
         │              │
┌────────▼────┐  ┌──────▼───────┐
│   Redis     │  │ TimescaleDB  │
│ (Cache+Queue│  │ (Compressed) │
│  Cluster)   │  │ Partitioned  │
└─────────────┘  └──────────────┘
         │
         ▼
   SNMP/gRPC
         │
         ▼
Réseau:
| - Backbone: Juniper MX960, Huawei NE9000  |
| - MBH Zone 1 (Juniper)    10.200.x.y      |
|   * MX480 / MX204 / MX104                 |
| - MBH Zone 2 (Huawei)     10.44.x.y       |
|   * NE9000 / NE5000E                      |
```

## 🚀 Installation rapide

### Prérequis
- Docker & Docker Compose
- Accès SNMPv2 aux équipements
- gRPC activé sur Juniper/Huawei (optionnel)
- 8 GB RAM minimum, 50 GB disk (avec compression)

### 1️⃣ Cloner le repo
```bash
git clone https://github.com/neowilly2016-spec/Supervision.git
cd Supervision
```

### 2️⃣ Configuration
```bash
cp .env.example .env
```

Éditer `.env`:
```env
# Database
POSTGRES_PASSWORD=VotreMotDePasse
TIMESCALE_COMPRESSION=true
TIMESCALE_RETENTION_DAYS=365

# SNMP
SNMP_DEFAULT_COMMUNITY=votre_community
SNMP_VERSION=2c
SNMP_TIMEOUT=5

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_CACHE_TTL=300

# Télémétrie gRPC
GRPC_ENABLED=true
GRPC_PORT=32767

# ML Anomaly Detection
ML_ENABLED=true
ML_TRAINING_DAYS=30

# Alerts
SMTP_HOST=votre_smtp_host
ALERT_EMAIL=noc@example.com
SLACK_WEBHOOK=https://hooks.slack.com/...
```

### 3️⃣ Configurer les équipements

Éditer `config/devices.yaml`:
```yaml
devices:
  backbone:
    - hostname: BACKBONE-MX960-ALGER-PE1
      ip: 10.200.0.1
      vendor: juniper
      model: MX960
      role: PE
      snmp:
        version: 2c
        community: "{{ SNMP_DEFAULT_COMMUNITY }}"
      grpc:
        enabled: true
        port: 32767
      polling_interval: 30  # Critique: 30 sec
      protocols:
        bgp: true
        isis: true
        mpls: true
        rsvp: true
        segment_routing: true

  mbh_zone1:
    - hostname: MBH-Z1-W01-MX480-AGG1
      ip: 10.200.1.1
      vendor: juniper
      model: MX480
      polling_interval: 120  # MBH: 2 min
      protocols:
        isis: true
        mpls: true

  mbh_zone2:
    - hostname: MBH-Z2-W16-NE9000-AGG1
      ip: 10.44.16.1
      vendor: huawei
      model: NE9000
      polling_interval: 120
      grpc:
        enabled: true
        port: 57400
```

### 4️⃣ Activer la télémétrie gRPC

**Juniper MX960/MX480:**
```junos
set system services extension-service request-response grpc clear-text port 32767
set system services extension-service request-response grpc skip-authentication
set system services extension-service notification allow-clients address 0.0.0.0/0
```

**Huawei NE9000:**
```huawei
grpc
 grpc server
  tls-policy disable
  port 57400
telemetry
 sensor-group sensor-bgp
  sensor-path bgp/peer
 destination-group dest-supervision
  ipv4-address <VOTRE_IP> port 57400 protocol grpc no-tls
 subscription sub-bgp
  sensor-group sensor-bgp
  destination-group dest-supervision
```

### 5️⃣ Démarrer la stack
```bash
# Build et start
docker-compose up -d

# Vérifier les logs
docker-compose logs -f backend

# Activer compression TimescaleDB
docker-compose exec timescaledb psql -U supervisor -d supervision -c "SELECT add_compression_policy('metrics', INTERVAL '7 days');"
```

### 6️⃣ Accéder aux interfaces
- **Dashboard**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Grafana**: http://localhost:3001 (admin/admin)
- **Redis Commander**: http://localhost:8081

## 📁 Structure du projet

```
Supervision/
├── docker-compose.yml
├── .env.example
├── README.md
├── config/
│   ├── devices.yaml
│   ├── snmp_profiles.yaml
│   ├── grpc_profiles.yaml       # NEW
│   └── ml_config.yaml           # NEW
├── backend/
│   ├── app.py                   # FastAPI
│   ├── requirements.txt
│   ├── collectors/
│   │   ├── snmp_collector.py
│   │   ├── grpc_collector.py    # NEW
│   │   └── network_discovery.py
│   ├── ml/
│   │   ├── anomaly_detector.py  # NEW
│   │   └── forecasting.py       # NEW
│   └── cache/
│       └── redis_cache.py       # NEW
├── db/
│   ├── init.sql
│   └── compression.sql           # NEW
└── frontend/
    ├── src/
    │   ├── components/
    │   │   ├── TopologyMap.tsx   # Leaflet
    │   │   └── MLAlerts.tsx      # NEW
    │   └── websocket/
    │       └── realtime.ts       # NEW
    └── package.json
```

## 🔧 Configuration avancée

### Compression TimescaleDB

```sql
-- Activer compression automatique après 7 jours
SELECT add_compression_policy('metrics', INTERVAL '7 days');

-- Vérifier ratio compression
SELECT 
  pg_size_pretty(before_compression_total_bytes) as "Avant",
  pg_size_pretty(after_compression_total_bytes) as "Après",
  round((1 - after_compression_total_bytes::numeric / before_compression_total_bytes::numeric) * 100, 2) || '%' as "Gain"
FROM timescaledb_information.compression_settings;
```

### Politique de rétention

```sql
-- Métriques haute résolution (1 min) : 7 jours
SELECT add_retention_policy('metrics', INTERVAL '7 days');

-- Agrégats 5 min : 30 jours
SELECT add_retention_policy('metrics_5min', INTERVAL '30 days');

-- Agrégats 1h : 1 an
SELECT add_retention_policy('metrics_hourly', INTERVAL '365 days');
```

### Cache Redis

```python
# Configuration cache Redis dans backend/cache/redis_cache.py
CACHE_CONFIG = {
    'bgp_peers': {'ttl': 300},      # 5 min
    'isis_adjacency': {'ttl': 300},
    'interfaces': {'ttl': 60},       # 1 min
    'mpls_lsp': {'ttl': 120}        # 2 min
}
```

### ML Anomaly Detection

```yaml
# config/ml_config.yaml
ml:
  models:
    bgp_flap_detection:
      algorithm: isolation_forest
      training_period_days: 30
      contamination: 0.01
      threshold: 0.8
    
    isis_spf_anomaly:
      algorithm: isolation_forest
      features:
        - spf_runs_per_hour
        - adjacency_changes
        - lsp_updates
    
    traffic_forecasting:
      algorithm: prophet
      seasonality:
        daily: true
        weekly: true
      forecast_days: 7
```

## 📊 Métriques spécifiques collectées

### Via SNMPv2 (Polling)

| OID | Description | Intervalle |
|-----|-------------|------------|
| BGP4-MIB::bgpPeerState | État des peers BGP | 30s |
| ISIS-MIB::isisISAdjState | Adjacences ISIS | 60s |
| MPLS-LSR-STD-MIB::mplsLspOperStatus | État LSPs MPLS | 60s |
| IF-MIB::ifHCInOctets | Octets reçus interfaces | 30s |
| IF-MIB::ifOperStatus | État opérationnel | 30s |

### Via gRPC Streaming (Temps réel)

| Path | Description | Fréquence |
|------|-------------|-----------|
| /interfaces/interface/state | Statistiques interfaces | 5s |
| /network-instances/network-instance/protocols/protocol/bgp | BGP peers | 10s |
| /network-instances/network-instance/protocols/protocol/isis | ISIS adjacences | 10s |
| /network-instances/network-instance/mpls/lsps | LSPs MPLS | 10s |

## 🚨 Système d'alertes avancé

### Alertes traditionnelles

| Condition | Seuil | Priorité | Action |
|-----------|-------|----------|--------|
| BGP peer down | Immédiat | CRITIQUE | Slack + Email + Ticket |
| Interface down | Immédiat | CRITIQUE | Slack + Email |
| MPLS LSP down | Immédiat | HAUTE | Slack + Email |
| ISIS adjacency down | Immédiat | CRITIQUE | Slack + Email |
| Utilisation > 80% | 5 min | HAUTE | Email |
| CPU > 90% | 10 min | MOYENNE | Email |

### Alertes ML (Prédictives)

| Modèle | Détection | Horizon | Action |
|--------|-----------|---------|--------|
| BGP Flap Prediction | Instabilité peer | 1h avant | Email + Ticket |
| ISIS SPF Storm | SPF anormal | 30 min avant | Slack + Email |
| Traffic Overflow | Saturation lien | 24h avant | Email + Planning |
| Interface Degradation | CRC/FEC errors | 12h avant | Email |

## 📊 Dashboards disponibles

### 1. **Vue globale Backbone & MBH**
- Carte géographique Algérie avec wilayas
- Statut tous équipements
- Top 10 liens chargés
- Alertes actives

### 2. **BGP Monitoring**
- État global tous peers
- Prefixes reçus/envoyés par peer
- Historique flaps
- Prédictions ML instabilité

### 3. **ISIS Monitoring**
- Topologie ISIS par zone
- Adjacences actives
- SPF runs historique
- LSP database size

### 4. **MPLS Monitoring**
- LSPs actifs par type (RSVP/LDP/SR)
- Bandwidth utilization
- Transitions LSP
- TE tunnels

### 5. **Performance Interfaces**
- Utilisation bandwidth
- Erreurs/CRC/FEC
- Optical levels (si 100G+)
- Queue drops par CoS

### 6. **ML Insights**
- Anomalies détectées
- Forecasting trafic 7 jours
- Recommandations optimisation
- Historique prédictions vs réalité

## 🔌 API REST

### Endpoints disponibles

```bash
# Obtenir tous devices
GET /api/v1/devices

# Obtenir métriques device spécifique
GET /api/v1/devices/{device_id}/metrics?start=2026-06-01&end=2026-06-22

# Obtenir alertes actives
GET /api/v1/alerts/active

# Obtenir prédictions ML
GET /api/v1/ml/predictions?model=bgp_flap&device_id=123

# Obtenir topologie réseau
GET /api/v1/topology/backbone

# Lancer découverte manuelle
POST /api/v1/discovery/run

# Obtenir stats cache Redis
GET /api/v1/cache/stats
```

## 🔧 Maintenance et troubleshooting

### Vérifier santé système

```bash
# Status tous containers
docker-compose ps

# Logs backend
docker-compose logs -f backend

# Logs collecteur SNMP
docker-compose exec backend tail -f /var/log/snmp_collector.log

# Stats Redis
docker-compose exec redis redis-cli INFO stats

# Taille base TimescaleDB
docker-compose exec timescaledb psql -U supervisor -d supervision -c "SELECT pg_size_pretty(pg_database_size('supervision'));"
```

### Performance tuning

```bash
# Augmenter workers SNMP (backend/.env)
SNMP_WORKERS=50

# Augmenter pool Redis
REDIS_MAX_CONNECTIONS=500

# Activer cache aggressif
REDIS_AGGRESSIVE_CACHE=true
```

### Backup et restore

```bash
# Backup TimescaleDB
docker-compose exec timescaledb pg_dump -U supervisor supervision > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20260622.sql | docker-compose exec -T timescaledb psql -U supervisor supervision

# Backup config
tar -czf config_backup_$(date +%Y%m%d).tar.gz config/
```

## 📚 Documentation technique

### Stack technologique

- **Backend**: FastAPI 0.110+ (Python 3.11+)
- **Database**: TimescaleDB 2.14+ (PostgreSQL 15)
- **Cache**: Redis 7.2+ (Cluster mode)
- **Queue**: Celery 5.3+ avec Redis broker
- **Frontend**: React 18+ avec TypeScript
- **Monitoring**: Prometheus + Grafana
- **ML**: scikit-learn 1.4+, Prophet 1.1+
- **Télémétrie**: grpcio 1.60+, pygnmi

### Ports utilisés

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 3000 | Dashboard React |
| Backend API | 8000 | FastAPI |
| Grafana | 3001 | Dashboards |
| Prometheus | 9090 | Métriques |
| Redis | 6379 | Cache |
| Redis Commander | 8081 | UI Redis |
| TimescaleDB | 5432 | Database |
| gRPC (Juniper) | 32767 | Télémétrie |
| gRPC (Huawei) | 57400 | Télémétrie |

## 📍 Plan d'adressage

| Zone | Réseau | Loopback format | SNMP Community |
|------|---------|-----------------|----------------|
| Backbone | 10.200.0.0/16 | 10.200.0.x | mpbn |
| MBH Zone 1 (Juniper) | 10.200.0.0/16 | 10.200.wilaya.x | mpbn |
| MBH Zone 2 (Huawei) | 10.44.0.0/16 | 10.44.wilaya.x | mpbn |

## 👥 Contribution

Pour contribuer au projet:

1. Fork le repository
2. Créer une branche feature (`git checkout -b feature/AmazingFeature`)
3. Commit vos changements (`git commit -m 'Add AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## 📜 License

MIT License - voir [LICENSE](LICENSE)

## 📧 Support

Pour questions et support:
- Email: support@supervision.dz
- Slack: #network-monitoring
- Documentation: https://docs.supervision.dz

---

**Version**: 2.0.0-performance
**Dernière mise à jour**: Juin 2026
**Auteur**: Network Operations Center - Algérie

# 🌐 Backbone & MBH Network Monitoring

> Outil de supervision réseau pour l'infrastructure Backbone (Juniper MX960, Huawei NE9000) et Mobile Backhaul (MBH)

## 🗺️ Vue d'ensemble

Cette solution complète de monitoring réseau est conçue pour superviser:
- **Backbone**: Juniper MX960 (BGP, ISIS, MPLS, LDP, RSVP, Segment Routing)
- **MBH (Mobile Backhaul)**: Liens microwave (Ericsson MINI-LINK, Huawei RTN) et agrégation
- **Topologie**: Découverte automatique via LLDP/CDP
- **Alertes**: Monitoring proactif avec notifications

## ✨ Fonctionnalités principales

### 📡 Collecte SNMP multi-vendor
- **Juniper MX960**: BGP, ISIS, MPLS LSP (RSVP/LDP), interfaces 100G+, CPU/Temp
- **Juniper MX480/MX204/MX104**: BGP, ISIS, MPLS TE, Segment Routing, interfaces
- **Huawei NE9000**: BGP, ISIS, MPLS TE, Segment Routing, interfaces
- **Microwave**: RSSI, BER, modulation, capacity, link status
- **Polling configurable** par type d'équipement

### 🗺️ Découverte automatique de topologie
- LLDP/CDP pour mapping des liens
- Graph interactif avec D3.js
- Vue hiérarchique du réseau

### 📊 Métriques temps réel
- **Interfaces**: Bandwidth utilization, errors, up/down events
- **BGP**: Peer state, updates, flaps
- **MPLS**: LSP state, transitions, traffic
- **MBH**: RSSI, BER, capacity, modulation adaptive

### 🚨 Système d'alertes
- Seuils configurables par équipement/interface
- Notifications multi-canal (email, Slack, webhook)
- Corrélation d'événements
- Escalade automatique

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (D3.js + Chart.js)               │
│  Topology Map | Dashboards | Alerts | Performance History    │
└─────────────────────┬───────────────────────────────────────┘
                      │ REST API
┌─────────────────────▼───────────────────────────────────────┐
│                    BACKEND (Python Flask)                     │
│  SNMP Collector | Discovery | Alert Engine | API             │
└──────┬──────────────────────────┬──────────────────────────-┘
       │                          │
┌──────▼──────┐          ┌────────▼────────┐
│ TimescaleDB │          │      Redis       │
│  (Metrics)  │          │    (Cache/Queue) │
└─────────────┘          └─────────────────┘
       │
       ▼
    SNMP
       │
       ▼
Réseau:
| - Juniper MX960 (Backbone/PE)     |
| - Huawei NE9000 (P/PE)            |
| - MBH Zone 1 (Juniper)   | Loopback: 10.200.x.y (x=wilaya)  |
|   * MX480 / MX204 / MX104        |
| - MBH Zone 2 (Huawei)    | Loopback: 10.44.x.y              |
|   * NE9000 / NE5000E             |
| - Ericsson MINI-LINK (MW)         |
| - Huawei RTN-950A (MW)            |
```

## 🚀 Installation rapide

### Prérequis
- Docker & Docker Compose
- Accès SNMP aux équipements (v2c ou v3)
- 4 GB RAM minimum, 20 GB disk

### 1️⃣ Cloner le repo
```bash
git clone https://github.com/neowilly2016-spec/Supervision.git
cd Supervision
```

### 2️⃣ Configuration
Copier le fichier d'environnement:
```bash
cp .env.example .env
```

Éditer `.env` avec vos paramètres:
```env
POSTGRES_PASSWORD=VotreMotDePasse
SNMP_DEFAULT_COMMUNITY=votre_community
SMTP_HOST=votre_smtp_host
SMTP_PORT=587
SMTP_USER=votre_email
SMTP_PASS=votre_mot_de_passe
ALERT_EMAIL=destinataire@example.com
```

### 3️⃣ Configurer les équipements
Éditer `config/devices.yaml`:
```yaml
devices:
  backbone:
    - name: "BACKBONE-MX960-01"
      ip: "10.200.0.1"
      vendor: "juniper"
      model: "MX960"
      role: "PE"
      snmp_profile: "juniper_v2"
      location: "DC-Principal"

  mbh_zone1:
    - name: "MBH-Z1-MX480-01"
      ip: "10.200.1.1"
      vendor: "juniper"
      model: "MX480"
      role: "AGG"
      snmp_profile: "juniper_v2"
      wilaya: 1
    - name: "MBH-Z1-MX204-01"
      ip: "10.200.1.2"
      vendor: "juniper"
      model: "MX204"
      role: "AGG"
      snmp_profile: "juniper_v2"
      wilaya: 1

  mbh_zone2:
    - name: "MBH-Z2-NE9000-01"
      ip: "10.44.1.1"
      vendor: "huawei"
      model: "NE9000"
      role: "AGG"
      snmp_profile: "huawei_v2"
      wilaya: 1

  microwave:
    - name: "MW-MINILINK-01"
      ip: "192.168.100.1"
      vendor: "ericsson"
      model: "MINI-LINK"
      role: "MW"
      snmp_profile: "ericsson_mw"
    - name: "MW-RTN950A-01"
      ip: "192.168.100.2"
      vendor: "huawei"
      model: "RTN-950A"
      role: "MW"
      snmp_profile: "huawei_mw"
```

### 4️⃣ Démarrer la stack
```bash
docker-compose up -d
```

### 5️⃣ Accéder au dashboard
- **Dashboard**: http://localhost:3000
- **API**: http://localhost:5000
- **Grafana**: http://localhost:3001 (admin/admin)

## 📁 Structure du projet

```
Supervision/
├── docker-compose.yml
├── .env.example
├── README.md
├── config/
│   ├── devices.yaml          # Inventaire des équipements
│   └── snmp_profiles.yaml    # Profils SNMP par vendor
├── backend/
│   ├── app.py                # API Flask principale
│   ├── requirements.txt
│   └── collectors/
│       ├── snmp_collector.py  # Collecte SNMP multi-vendor
│       └── network_discovery.py # Découverte LLDP/CDP
├── db/
│   └── init.sql              # Schéma TimescaleDB
└── frontend/
    └── index.html            # Dashboard D3.js
```

## 🔧 Profils SNMP supportés

| Vendor    | Modèles supportés              | Protocoles monitoriés              |
|-----------|-------------------------------|------------------------------------|
| Juniper   | MX960, MX480, MX204, MX104    | BGP, ISIS, MPLS, RSVP, LDP, SR    |
| Huawei    | NE9000, NE5000E               | BGP, ISIS, MPLS TE, SR             |
| Ericsson  | MINI-LINK 6352, 6691          | RSSI, BER, modulation, capacity    |
| Huawei MW | RTN-950A, RTN-980             | RSSI, BER, modulation, capacity    |

## 📊 Métriques collectées

### Backbone (Juniper MX960 & Huawei NE9000)
- **BGP**: Sessions actives, prefixes reçus/envoyés, flaps, état peers
- **ISIS**: Adjacences, LSPs, topologie
- **MPLS**: LSPs actifs, trafic, transitions état
- **Interfaces**: Utilisation bande passante, erreurs, CRC
- **Système**: CPU, mémoire, température, alimentation

### MBH Zone 1 - Juniper (MX480/MX204/MX104)
- **ISIS**: Adjacences MBH, métriques liens
- **MPLS**: Tunnels vers Backbone
- **Interfaces**: Trafic agrégation, liens vers MW
- **Loopback**: 10.200.x.y (x = numéro wilaya)

### MBH Zone 2 - Huawei (NE9000/NE5000E)
- **ISIS**: Adjacences MBH, métriques liens
- **MPLS**: Tunnels vers Backbone
- **Interfaces**: Trafic agrégation, liens vers MW
- **Loopback**: 10.44.x.y

### Microwave (Ericsson MINI-LINK & Huawei RTN-950A)
- **Radio**: RSSI, SNR, BER, modulation courante
- **Capacité**: Throughput actuel vs nominal
- **Liens**: État up/down, dégradations

## 🚨 Alertes configurées

| Condition                    | Seuil        | Priorité |
|------------------------------|--------------|----------|
| BGP peer down                | Immédiat     | CRITIQUE |
| Interface down               | Immédiat     | CRITIQUE |
| MPLS LSP down                | Immédiat     | HAUTE    |
| Bande passante > 80%         | 5 min        | HAUTE    |
| RSSI dégradé                 | < -75 dBm    | HAUTE    |
| BER élevé                    | > 1e-6       | HAUTE    |
| CPU > 90%                    | 10 min       | MOYENNE  |
| Mémoire > 85%                | 10 min       | MOYENNE  |
| Température > 65°C           | Immédiat     | HAUTE    |

## 🗺️ Plan d'adressage

| Zone                     | Réseau          | Loopback format    |
|--------------------------|-----------------|--------------------|
| Backbone                 | 10.200.0.0/16   | 10.200.0.x         |
| MBH Zone 1 (Juniper)     | 10.200.0.0/16   | 10.200.wilaya.x    |
| MBH Zone 2 (Huawei)      | 10.44.0.0/16    | 10.44.wilaya.x     |
| Microwave Management     | 192.168.100.0/24| N/A                |

## 📜 License

MIT License - voir [LICENSE](LICENSE)

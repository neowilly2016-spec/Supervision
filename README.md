# 🔍 Backbone & MBH Network Monitoring

> Outil de supervision réseau pour l'infrastructure Backbone (Juniper MX, Huawei NE9000) et Mobile Backhaul (MBH)

## 📋 Vue d'ensemble

Cette solution complète de monitoring réseau est conçue pour superviser:
- **Backbone**: Routeurs Juniper MX et Huawei NE9000 (BGP, ISIS, MPLS, LDP, RSVP, Segment Routing)
- **MBH (Mobile Backhaul)**: Liens microwave (Ericsson MINI-LINK, Huawei RTN) et agrégation
- **Topologie**: Découverte automatique via LLDP/CDP
- **Alertes**: Monitoring proactif avec notifications

## ✨ Fonctionnalités principales

### 📡 Collecte SNMP multi-vendor
- **Juniper MX**: BGP, ISIS, MPLS LSP (RSVP/LDP), interfaces 100G+, CPU/Temp
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
- **MBH**: RSSI, BER, capacity, modulation adaptative

### 🚨 Système d'alertes
- Interface DOWN
- BGP session DOWN
- MPLS LSP DOWN
- MBH RSSI < threshold
- MBH BER > threshold
- Bandwidth > 80%

### 📈 Dashboard Web
- Carte réseau interactive
- Graphes de métriques (Chart.js)
- Historique time-series (TimescaleDB)
- Intégration Grafana optionnelle

## 🏗️ Architecture

```
┌─────────────────┐
│   Frontend      │  Nginx + HTML/CSS/JS (D3.js, Chart.js)
└────────┬────────┘
         │
┌────────▼────────┐
│   API Flask     │  REST API (devices, interfaces, alerts, topology)
└────────┬────────┘
         │
┌────────▼────────┐
│  PostgreSQL +   │  TimescaleDB (time-series metrics)
│  TimescaleDB    │
└─────────────────┘
         ▲
         │
┌────────┴────────┐
│   Collector     │  SNMP Poller + Topology Discovery
│   (Python)      │  BGP / MPLS / MBH monitors
└─────────────────┘
         │
         │ SNMP
         ▼
┌──────────────────────────────────┐
│ Réseau:                          │
│ - Juniper MX480/MX240 (PE/P)     │
│ - Huawei NE9000 (P/PE)           │
│ - Huawei CE6870 (MBH AGG)        │
| - MBH Zone 1 (Juniper)     | Loopback: 10.200.x.y (x=wilaya)           |
| - MBH Zone 2 (Huawei)      | Loopback: 10.44.x.y            |
│ - Ericsson MINI-LINK (MW)        │
│ - Huawei RTN-950A (MW)           │
└──────────────────────────────────┘
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
```bash
POSTGRES_PASSWORD=VotreMotDePasse
SNMP_DEFAULT_COMMUNITY=votre_community
SMTP_HOST=smtp.votre-domaine.dz
SMTP_TO=admin@votre-domaine.dz
```

Éditer `config/devices.yaml` avec votre inventaire réseau:
```yaml
devices:
  - hostname: MX-ALGER-PE1
    ip: 192.168.1.1
    vendor: juniper
    model: MX480
    snmp:
      version: 2c
      community: public
```

### 3️⃣ Lancer l'application

```bash
# Lancer tous les services
docker-compose up -d

# Vérifier les logs
docker-compose logs -f collector
```

### 4️⃣ Accès

- **Frontend**: http://localhost
- **API**: http://localhost:5000
- **Grafana**: http://localhost:3000 (admin/admin123)
- **PostgreSQL**: localhost:5432

## 📁 Structure du projet

```
Supervision/
├── docker-compose.yml          # Orchestration des services
├── .env.example                # Template configuration
├── README.md                   # Documentation
├── config/
│   ├── devices.yaml            # Inventaire équipements
│   └── snmp_profiles.yaml      # OIDs par vendor/modèle
├── db/
│   └── init.sql                # Schéma PostgreSQL/TimescaleDB
├── collector/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                 # Point d'entrée collector
│   ├── snmp_poller.py          # Polling SNMP générique
│   ├── topology_discovery.py   # LLDP/CDP discovery
│   ├── bgp_monitor.py          # Monitor BGP sessions
│   ├── mpls_monitor.py         # Monitor MPLS LSPs
│   └── mbh_monitor.py          # Monitor liens MBH (MW)
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py                  # Flask API
│   ├── models.py               # SQLAlchemy models
│   └── routes/
│       ├── devices.py
│       ├── interfaces.py
│       ├── alerts.py
│       └── topology.py
└── frontend/
    ├── Dockerfile
    ├── index.html
    ├── js/
    │   ├── topology.js         # D3.js network map
    │   ├── dashboard.js
    │   └── alerts.js
    └── css/
        └── style.css
```

## 🔧 Configuration avancée

### Polling intervals

Dans `.env`:
```bash
POLL_INTERVAL_INTERFACES=60     # 1 minute
POLL_INTERVAL_BGP=120           # 2 minutes
POLL_INTERVAL_MPLS=120
POLL_INTERVAL_MBH=60
POLL_INTERVAL_TOPOLOGY=300      # 5 minutes
```

### Alertes personnalisées

```bash
ALERT_INTERFACE_BW_THRESHOLD=80          # % utilisation
ALERT_BGP_DOWN=true
ALERT_MPLS_LSP_DOWN=true
ALERT_MBH_RSSI_THRESHOLD=-85             # dBm
ALERT_MBH_BER_THRESHOLD=1e-6
```

### SNMP v3

Pour SNMP v3 dans `config/devices.yaml`:
```yaml
snmp:
  version: 3
  user: snmpv3user
  auth_protocol: SHA
  auth_password: authpass
  priv_protocol: AES
  priv_password: privpass
```

## 📊 API Endpoints

### Devices
```
GET    /api/devices              # Liste tous les équipements
GET    /api/devices/{id}         # Détails d'un équipement
POST   /api/devices              # Ajouter équipement
PUT    /api/devices/{id}         # Modifier équipement
DELETE /api/devices/{id}         # Supprimer équipement
```

### Interfaces
```
GET    /api/devices/{id}/interfaces        # Interfaces d'un device
GET    /api/interfaces/{id}/metrics        # Métriques historiques
```

### BGP
```
GET    /api/devices/{id}/bgp               # Sessions BGP
GET    /api/bgp/down                       # Sessions DOWN
```

### Alerts
```
GET    /api/alerts                         # Alertes actives
POST   /api/alerts/{id}/ack               # Acquitter alerte
```

### Topology
```
GET    /api/topology                       # Graph complet
GET    /api/topology/links                 # Liens LLDP
```

## 🛠️ Développement

### Ajouter un nouveau vendor

1. Ajouter le profil SNMP dans `config/snmp_profiles.yaml`
2. Créer le parser dans `collector/parsers/`
3. Mettre à jour `collector/snmp_poller.py`

### Base de données

Accès PostgreSQL:
```bash
docker exec -it supervision_db psql -U supervision
```

Requêtes utiles:
```sql
-- Interfaces DOWN
SELECT * FROM v_interfaces_status WHERE oper_status = 'down';

-- BGP sessions DOWN
SELECT * FROM v_bgp_down;

-- Alertes actives
SELECT * FROM v_active_alerts;

-- Utilisation bandwidth top 10 (dernière heure)
SELECT d.hostname, i.if_name, 
       MAX(m.utilization_in) as max_util
FROM interface_metrics m
JOIN interfaces i ON m.if_index = i.if_index
JOIN devices d ON m.device_id = d.id
WHERE m.time > NOW() - INTERVAL '1 hour'
GROUP BY d.hostname, i.if_name
ORDER BY max_util DESC
LIMIT 10;
```

## 🐛 Dépannage

### Le collector ne récupère pas de données
```bash
# Vérifier logs
docker-compose logs collector

# Tester SNMP manuellement
docker exec -it supervision_collector snmpwalk -v2c -c public 192.168.1.1 sysDescr
```

### La base de données ne démarre pas
```bash
# Nettoyer volumes
docker-compose down -v
docker-compose up -d
```

### Frontend inaccessible
```bash
# Vérifier statut services
docker-compose ps

# Rebuild frontend
docker-compose build frontend
docker-compose restart frontend
```

## 🔐 Sécurité

- Changer tous les mots de passe par défaut dans `.env`
- Utiliser SNMP v3 en production
- Limiter accès PostgreSQL (modifier `docker-compose.yml`)
- HTTPS recommandé (ajouter reverse proxy)
- Firewall: autoriser uniquement SNMP depuis collector

## 📝 Roadmap

- [ ] Authentification utilisateurs (JWT)
- [ ] BGP-LS pour topology dynamique
- [ ] NetFlow / sFlow integration
- [ ] Weathermap automatique
- [ ] Mobile app (React Native)
- [ ] Playbooks d'automatisation (Ansible)
- [ ] Support Cisco IOS-XR
- [ ] Support Nokia SR OS

## 🤝 Contribution

Les contributions sont bienvenues!

1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit (`git commit -m 'Add AmazingFeature'`)
4. Push (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## 📄 Licence

MIT License - voir fichier `LICENSE`

## 👨‍💻 Auteur

**neowilly2016-spec**
- GitHub: [@neowilly2016-spec](https://github.com/neowilly2016-spec)

## 🙏 Remerciements

- LibreNMS pour l'inspiration sur discovery SNMP
- Juniper et Huawei pour la documentation MIBs
- Community D3.js pour les exemples de graphes réseau

---

**⚡ Fait avec ❤️ pour les Network Engineers d'Algérie 🇩🇿**

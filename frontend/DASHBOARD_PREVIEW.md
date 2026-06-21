# 📊 Dashboard Web - Aperçu Visuel

## Vue d'ensemble du Dashboard

Le dashboard web de supervision Backbone & MBH offre une interface moderne et intuitive pour monitorer votre réseau en temps réel.

## 🎨 Design & Layout

### En-tête (Header)
```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│  🔍 Backbone & MBH Monitoring  v1.0      │      🟢 Collector: Online  |  Last update: 14:23:10  │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### Sidebar Navigation
```
┌──────────────────────────┐
│  📊 Dashboard       ◀─── Actif
│  🗺️ Topologie
│  📡 Équipements
│  🔀 BGP Sessions
│  ⚡ MPLS Tunnels
│  📶 MBH Links
│  🚨 Alertes        [3]
└──────────────────────────┘
```

### Page Dashboard Principale

#### 1️⃣ Cartes de Statistiques (4 colonnes)

```
┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
│                    │  │                    │  │                    │  │                    │
│   📡   Équipements  │  │   🔀   BGP          │  │   ⚡   MPLS         │  │   🚨   Alertes      │
│                    │  │                    │  │                    │  │                    │
│        12          │  │        48          │  │        24          │  │        3           │
│                    │  │                    │  │                    │  │                    │
│   🟢 11 UP         │  │   🟢 45 Estab.    │  │   🟢 22 UP        │  │   🔴 2 Critical   │
│   🔴 1 DOWN        │  │   🔴 3 Down      │  │   🔴 2 DOWN       │  │   🟡 1 Major      │
│                    │  │                    │  │                    │  │                    │
└────────────────────┘  └────────────────────┘  └────────────────────┘  └────────────────────┘
```

#### 2️⃣ Graphiques (2 colonnes)

```
┌────────────────────────────────────────────────────────────┐
│  Bandwidth Utilization (Top 10)                              │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  MX-ALGER-PE1:et-0/0/0    ██████████████████ 85%     │
│  NE9K-ALGER-P1:100GE1/0/0 ████████████████ 78%        │
│  MX-ORAN-PE1:ae0          ██████████████ 72%           │
│  ...                                                         │
│                                                             │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│  Répartition Équipements                                   │
├────────────────────────────────────────────────────────────┤
│                                                             │
│              Graphique Pie Chart                            │
│                                                             │
│           🟦 Juniper MX  (4)                             │
│           🟧 Huawei NE   (3)                             │
│           🟪 Huawei CE   (2)                             │
│           🟨 Microwave   (3)                             │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

#### 3️⃣ Alertes Récentes

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│  🚨 Alertes Récentes                                                  [Actualiser] │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  🔴 CRITICAL | MX-ALGER-PE1 | Interface et-0/0/0 DOWN              | 14:20:15  │
│  🔴 CRITICAL | NE9K-ALGER-P1 | BGP session 10.1.1.2 DOWN            | 14:18:32  │
│  🟡 MAJOR    | MW-ALGER-002 | MBH RSSI -87 dBm (threshold -85)     | 14:15:08  │
│  🟠 MINOR    | MX-ORAN-PE1  | Interface utilization > 80%          | 14:10:45  │
│                                                                                │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🗺️ Page Topologie

Graphe interactif D3.js montrant:
- Noeuds colorés par type (🟦 PE, 🟧 P, 🟪 Switch, 🟨 MW)
- Liens entre équipements (LLDP/CDP)
- Zoom/Pan interactif
- Clic sur noeud pour détails
- Indication des liens DOWN en rouge

```
                  MX-ALGER-PE1
                      🟦
                     / |\
                    /  | \
                   /   |  \
                  /    |   \
                 /     |    \
         NE9K-P1       |     NE9K-P2
           🟧        |       🟧
                 \    |    /
                  \   |   /
                   \  |  /
                    \ | /
                     \|/
                MX-ORAN-PE1
                     🟦
```

---

## 📡 Page Équipements

Tableau avec:
- Hostname
- IP Address
- Type (Router/Switch/Microwave)
- Vendor/Model
- Site/Région
- Status (🟢 UP / 🔴 DOWN)
- CPU / Temp
- Actions

---

## 🔀 Page BGP Sessions

Tableau des sessions BGP:
- Device
- Peer IP
- Peer AS
- State (Established/Down/Idle)
- Uptime
- Prefixes In/Out
- Last Flap

---

## ⚡ Page MPLS Tunnels

Liste des LSPs:
- Tunnel Name
- Device
- Ingress LSR
- Egress LSR
- State (UP/DOWN)
- Bandwidth
- Type (RSVP/LDP/SR)
- Transitions

---

## 📶 Page MBH Links

Liens microwave avec métriques RF:
- Link Name
- Device
- Far End
- Frequency
- Modulation
- RSSI (Rx Level)
- BER
- Capacity
- Utilization
- Status

---

## 🎨 Palette de Couleurs

- **Background**: `#0d1117` (dark)
- **Cards**: `#161b22` 
- **Primary**: `#58a6ff` (blue)
- **Success**: `#3fb950` (green)
- **Warning**: `#d29922` (yellow)  
- **Danger**: `#f85149` (red)
- **Critical**: `#da3633`
- **Major**: `#f78166`
- **Minor**: `#d29922`

---

## ✨ Fonctionnalités Interactives

- **Auto-refresh**: Mise à jour automatique toutes les 30s
- **Recherche**: Filtres sur toutes les tables
- **Tri**: Colonnes triables
- **Export**: Téléchargement CSV
- **Alertes**: Notifications desktop
- **Responsive**: Compatible mobile/tablet

---

## 🚀 Accès

Après déploiement: **http://localhost** ou **http://votre-serveur**

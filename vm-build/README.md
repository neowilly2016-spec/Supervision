# 📦 VM OVA Builder - Supervision Network Monitoring

## 🎯 Vue d'ensemble

Ce dossier contient les scripts pour créer une **VM OVA prête à l'emploi** de la plateforme Supervision avec toutes les dépendances pré-installées.

## 🖥️ Spécifications de la VM

- **OS**: Ubuntu Server 22.04 LTS
- **RAM**: 16 GB
- **CPU**: 8 vCPUs
- **Disque**: 200 GB (allocation dynamique)
- **Format**: OVA (compatible VirtualBox, VMware ESXi, Hyper-V)

## 📋 Contenu pré-installé

✅ Ubuntu Server 22.04 LTS optimisé
✅ Docker Engine + Docker Compose v2
✅ Projet Supervision dans `/opt/Supervision`
✅ Images Docker pré-téléchargées (TimescaleDB, Redis, Grafana, etc.)
✅ Service systemd pour auto-démarrage
✅ Configuration réseau (Bridged)

## 🚀 Création de l'OVA - Guide Complet

### Prérequis

- **VirtualBox** 7.0+ installé sur votre machine
- **Connexion Internet** (pour télécharger Ubuntu ISO)
- **Espace disque**: ~25 GB libre
- **Système hôte**: Linux, macOS, ou Windows

### Étape 1: Créer la structure VM

```bash
cd vm-build
chmod +x build-ova.sh
./build-ova.sh
```

Le script va:
1. Créer la VM VirtualBox avec les spécifications demandées
2. Télécharger Ubuntu Server 22.04 ISO (si nécessaire)
3. Configurer le contrôleur SATA et le disque virtuel
4. Générer le script de provisioning

### Étape 2: Installer Ubuntu

```bash
# Démarrer la VM en mode graphique
VBoxManage startvm 'Supervision-NetworkMonitoring-v1.0' --type gui
```

**Configuration de l'installation**:
- **Langue**: English
- **Keyboard**: French (ou votre clavier)
- **Type d'installation**: Ubuntu Server (minimized)
- **Network**: DHCP (ou configuration manuelle)
- **Storage**: Utiliser tout le disque (200GB)
- **Profil**:
  - Hostname: `supervision-vm`
  - Username: `ubuntu`
  - Password: `ubuntu` (ou votre mot de passe)
- **SSH**: Installer OpenSSH server
- **Snaps**: Ne rien installer

### Étape 3: Provisioning automatique

Après l'installation et le redémarrage:

```bash
# Dans la VM (via SSH ou console)
sudo apt update && sudo apt install -y git

# Copier le script de provisioning
wget https://raw.githubusercontent.com/neowilly2016-spec/Supervision/main/vm-build/supervision-setup.sh
chmod +x supervision-setup.sh

# Exécuter le provisioning (durée: ~15 minutes)
sudo ./supervision-setup.sh
```

Le script va:
- ✅ Installer Docker + Docker Compose
- ✅ Cloner le repository Supervision
- ✅ Pré-télécharger toutes les images Docker
- ✅ Configurer le service systemd
- ✅ Nettoyer la VM

### Étape 4: Nettoyage final

```bash
# Dans la VM
sudo apt-get clean
sudo journalctl --vacuum-time=1d
sudo rm -rf /tmp/*
sudo rm ~/.bash_history
sudo history -c

# Remplir l'espace libre avec des zéros (optionnel, réduit la taille OVA)
sudo dd if=/dev/zero of=/EMPTY bs=1M || true
sudo rm -f /EMPTY

# Arrêter la VM
sudo shutdown -h now
```

### Étape 5: Exporter en OVA

```bash
# Sur votre machine hôte
VBoxManage export 'Supervision-NetworkMonitoring-v1.0' \
  -o vm-output/Supervision-NetworkMonitoring-v1.0.ova \
  --options manifest,iso \
  --vsys 0 \
  --product "Supervision Network Monitoring" \
  --producturl "https://github.com/neowilly2016-spec/Supervision" \
  --vendor "neowilly2016-spec" \
  --version "1.0" \
  --description "Plateforme de supervision réseau haute performance pour Backbone et MBH"
```

## 📥 Utilisation de l'OVA

### Import dans VirtualBox

```bash
VBoxManage import Supervision-NetworkMonitoring-v1.0.ova
```

Ou via l'interface graphique:
1. Fichier → Importer un appareil virtuel
2. Sélectionner le fichier `.ova`
3. Vérifier les paramètres
4. Importer

### Import dans VMware ESXi

1. Se connecter à vSphere Client
2. Clic droit sur datacenter → Deploy OVF Template
3. Sélectionner le fichier `.ova`
4. Suivre l'assistant

### Premier démarrage

```bash
# Démarrer la VM
VBoxManage startvm 'Supervision-NetworkMonitoring-v1.0' --type headless

# Se connecter via SSH
ssh ubuntu@<IP_VM>

# Vérifier les services
docker ps
systemctl status supervision
```

## ⚙️ Configuration post-import

### 1. Configuration réseau

```bash
# Identifier l'IP
ip addr show

# Configurer IP statique (optionnel)
sudo nano /etc/netplan/00-installer-config.yaml
```

### 2. Configuration Supervision

```bash
cd /opt/Supervision

# Éditer la configuration
nano .env

# Variables importantes:
# DB_HOST=db
# POSTGRES_DB=supervision
# SNMP_COMMUNITY=public
# REDIS_HOST=redis
```

### 3. Configuration des devices

```bash
# Ajouter vos équipements réseau
nano config/devices.yaml

# Exemple:
# devices:
#   - hostname: router1.example.com
#     ip: 192.168.1.1
#     vendor: juniper
#     model: MX960
```

### 4. Démarrer la supervision

```bash
# Démarrer manuellement
cd /opt/Supervision
docker-compose up -d

# Ou redémarrer le service
sudo systemctl restart supervision

# Vérifier les logs
docker-compose logs -f
```

## 🌐 Accès aux services

Une fois la VM démarrée:

- **Dashboard principal**: `http://<IP_VM>:3000`
- **API Documentation**: `http://<IP_VM>:8000/docs`
- **Grafana**: `http://<IP_VM>:3001` (admin/admin)
- **Redis Commander**: `http://<IP_VM>:8081`

## 🔧 Maintenance

### Mise à jour du projet

```bash
cd /opt/Supervision
git pull origin main
docker-compose pull
docker-compose up -d
```

### Backup de la base de données

```bash
docker-compose exec db pg_dump -U supervisor supervision > backup-$(date +%Y%m%d).sql
```

### Redimensionner la VM

```bash
# Augmenter la RAM (après arrêt)
VBoxManage modifyvm 'Supervision-NetworkMonitoring-v1.0' --memory 32768

# Augmenter les CPUs
VBoxManage modifyvm 'Supervision-NetworkMonitoring-v1.0' --cpus 16
```

## 📊 Performances attendues

Avec la configuration par défaut (16GB RAM, 8 vCPUs):

- ✅ Support jusqu'à **200 devices** simultanés
- ✅ Collecte SNMP toutes les 30 secondes
- ✅ Rétention métriques: 90 jours (avec compression)
- ✅ Dashboards Grafana temps réel (<1s latence)
- ✅ API REST: ~500 req/s

## 🛠️ Dépannage

### La VM ne démarre pas

```bash
# Vérifier les logs VirtualBox
VBoxManage showvminfo 'Supervision-NetworkMonitoring-v1.0' --details

# Vérifier la virtualisation
egrep -c '(vmx|svm)' /proc/cpuinfo  # Doit être > 0
```

### Les services Docker ne démarrent pas

```bash
# Vérifier Docker
sudo systemctl status docker

# Redémarrer Docker
sudo systemctl restart docker

# Vérifier les logs
journalctl -u docker -f
```

### Problèmes réseau

```bash
# Tester la connectivité SNMP
snmpwalk -v2c -c public <IP_DEVICE> system

# Vérifier les routes
ip route show

# Tester les ports
telnet <IP_DEVICE> 161
```

## 📦 Taille de l'OVA

- **Avec compression**: ~18-22 GB
- **Sans compression**: ~25-30 GB
- **Après premier démarrage**: ~35-40 GB (données + logs)

## 🔐 Sécurité

### Recommandations

1. ✅ Changer le mot de passe `ubuntu` après import
2. ✅ Configurer le firewall UFW
3. ✅ Utiliser des clés SSH au lieu de mots de passe
4. ✅ Limiter l'accès SNMP aux VLANs de management
5. ✅ Activer HTTPS pour Grafana (Let's Encrypt)

```bash
# Configurer le firewall
sudo ufw allow 22/tcp
sudo ufw allow 3000/tcp
sudo ufw allow 8000/tcp
sudo ufw allow 3001/tcp
sudo ufw enable
```

## 📝 Notes

- Le fichier `.ova` est portable entre VirtualBox, VMware et Hyper-V
- Les images Docker sont pré-téléchargées pour un démarrage rapide
- Le service systemd démarre automatiquement au boot
- La configuration réseau utilise DHCP par défaut
- Aucune connexion Internet requise après import

## 🆘 Support

Pour toute question ou problème:
- **Issues GitHub**: https://github.com/neowilly2016-spec/Supervision/issues
- **Documentation**: https://github.com/neowilly2016-spec/Supervision/blob/main/README.md

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier LICENSE pour plus de détails.

---

**Créé par**: neowilly2016-spec  
**Version**: 1.0  
**Date**: Juin 2026

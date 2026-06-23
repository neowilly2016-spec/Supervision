# 🚀 Guide Rapide - Créer une VM OVA Supervision

## ⚡ Démarrage Ultra-Rapide

### Sur TON PC (Windows/Linux/Mac avec VirtualBox)

```bash
# 1. Cloner le repository
git clone https://github.com/neowilly2016-spec/Supervision.git
cd Supervision/vm-build

# 2. Lancer le script automatique
chmod +x build-ova-automated.sh
./build-ova-automated.sh
```

Le script va automatiquement :
- ✅ Télécharger Ubuntu Server 22.04 ISO (~1.5 GB)
- ✅ Créer la VM VirtualBox (16GB RAM, 8 vCPUs, 200GB disk)
- ✅ Configurer le réseau et le stockage
- ✅ Générer le script de provisioning

**Durée**: ~5 minutes pour cette partie

---

## 📝 Étapes Suivantes (Semi-automatiques)

### Étape 1 : Installer Ubuntu (~30 minutes)

```bash
# Démarrer la VM en mode graphique
VBoxManage startvm 'Supervision-NetworkMonitoring-v1.0' --type gui
```

**Dans l'installeur Ubuntu** :
1. Langue : English
2. Keyboard : French (ou ton clavier)
3. Type : Ubuntu Server (minimized)
4. Network : DHCP
5. Storage : Use entire disk
6. Profile :
   - **Hostname** : `supervision-vm`
   - **Username** : `ubuntu`
   - **Password** : `ubuntu`
7. SSH : **✅ Install OpenSSH server**
8. Packages : Docker, Docker Compose
9. Installer et redémarrer

### Étape 2 : Provisioning Automatique (~45 minutes)

Après le redémarrage de la VM, se connecter en SSH ou via console :

```bash
# Dans la VM
sudo apt update && sudo apt install -y wget

# Télécharger le script de provisioning
wget https://raw.githubusercontent.com/neowilly2016-spec/Supervision/main/vm-build/provision-vm.sh
chmod +x provision-vm.sh

# Lancer le provisioning (automatique)
sudo ./provision-vm.sh
```

Le script va :
- ✅ Installer Docker & Docker Compose
- ✅ Cloner le projet Supervision dans `/opt/Supervision`
- ✅ Pré-télécharger TOUTES les images Docker
- ✅ Configurer le service systemd auto-start
- ✅ Nettoyer la VM

**Attendre la fin** (message "✓ Provisioning terminé !")

### Étape 3 : Arrêter la VM

```bash
# Dans la VM
sudo shutdown -h now
```

### Étape 4 : Exporter l'OVA (~10 minutes)

```bash
# Sur ton PC
VBoxManage export 'Supervision-NetworkMonitoring-v1.0' \
  -o vm-output/Supervision-NetworkMonitoring-v1.0.ova \
  --options manifest
```

---

## ✅ C'est Terminé !

Ton fichier OVA est prêt à :
```
vm-output/Supervision-NetworkMonitoring-v1.0.ova  (~20 GB)
```

---

## 📦 Utiliser l'OVA

### Import dans VirtualBox

```bash
VBoxManage import Supervision-NetworkMonitoring-v1.0.ova
VBoxManage startvm 'Supervision-NetworkMonitoring-v1.0' --type headless
```

### Premier démarrage

```bash
# Se connecter via SSH
ssh ubuntu@<IP_VM>

# Configurer le projet
cd /opt/Supervision
nano .env  # Éditer DB, SNMP, etc.
nano config/devices.yaml  # Ajouter tes devices

# Démarrer la supervision
sudo systemctl restart supervision

# Vérifier
docker ps
```

### Accès aux services

- **Dashboard** : http://<IP_VM>:3000
- **API** : http://<IP_VM>:8000/docs
- **Grafana** : http://<IP_VM>:3001 (admin/admin)
- **Redis Commander** : http://<IP_VM>:8081

---

## ⏱️ Durée Totale

| Étape | Durée | Type |
|-------|-------|------|
| Script automatique | 5 min | 🤖 Auto |
| Téléchargement ISO | 10-15 min | 🤖 Auto |
| Installation Ubuntu | 30 min | 👤 Manuel |
| Provisioning | 45 min | 🤖 Auto |
| Export OVA | 10 min | 🤖 Auto |
| **TOTAL** | **~2h** | **80% auto** |

---

## 🔧 Dépannage Rapide

### La VM ne démarre pas

```bash
# Vérifier VirtualBox
VBoxManage --version

# Vérifier la VM
VBoxManage list vms
```

### Provisioning échoue

```bash
# Vérifier Docker
sudo systemctl status docker

# Relancer
sudo systemctl restart docker
sudo ./provision-vm.sh
```

### Export OVA échoue

```bash
# S'assurer que la VM est arrêtée
VBoxManage list runningvms

# Arrêter si nécessaire
VBoxManage controlvm 'Supervision-NetworkMonitoring-v1.0' poweroff

# Réessayer export
VBoxManage export ...
```

---

## 💡 Astuces

### Réduire la taille de l'OVA

Avant l'export, dans la VM :

```bash
# Remplir l'espace libre de zéros
sudo dd if=/dev/zero of=/EMPTY bs=1M || true
sudo rm -f /EMPTY

# Compacter le disque (sur l'hôte)
VBoxManage modifymedium disk vm-output/Supervision-NetworkMonitoring-v1.0.vdi --compact
```

Cela peut réduire l'OVA de 20-25 GB à 15-18 GB.

### Accélérer le processus

- **SSD recommandé** : Réduit le temps de ~2h à ~1h30
- **Connexion rapide** : Pour télécharger ISO et images Docker
- **Allocation CPU/RAM** : Donner plus de ressources à VirtualBox

### Script en arrière-plan

```bash
# Lancer le provisioning en arrière-plan
nohup sudo ./provision-vm.sh > provisioning.log 2>&1 &

# Suivre les logs
tail -f provisioning.log
```

---

## 📊 Checklist Complète

- [ ] VirtualBox 7.0+ installé
- [ ] 25 GB d'espace disque libre
- [ ] Script `build-ova-automated.sh` exécuté
- [ ] ISO Ubuntu téléchargé
- [ ] VM créée et démarrée
- [ ] Ubuntu installé (hostname: supervision-vm)
- [ ] Script `provision-vm.sh` exécuté
- [ ] Provisioning terminé (message vert)
- [ ] VM arrêtée proprement
- [ ] OVA exporté
- [ ] OVA testé (import + démarrage)

---

## 🎯 Résultat Final

Une VM OVA **prête à l'emploi** contenant :

✅ Ubuntu Server 22.04 LTS optimisé  
✅ Docker + Docker Compose installés  
✅ Projet Supervision dans `/opt/Supervision`  
✅ Images Docker pré-téléchargées (pas d'Internet requis)  
✅ Service systemd auto-démarrage  
✅ Configuration réseau DHCP  
✅ Support jusqu'à 200 devices  

Taille: ~18-22 GB (compressé)  
Compatible: VirtualBox, VMware ESXi, Hyper-V

---

**Questions ou problèmes ?**  
Ouvrir une issue : https://github.com/neowilly2016-spec/Supervision/issues

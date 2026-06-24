#!/bin/bash
###############################################################################
# Script AUTOMATIQUE de Création VM OVA - VMware Workstation/Player
# Supervision Network Monitoring
# OS: Ubuntu Server 22.04 LTS | RAM: 16GB | CPU: 8 vCPUs | Disk: 200GB
###############################################################################

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
VM_NAME="Supervision-NetworkMonitoring-v1.0"
RAM=16384  # 16GB en MB
CPUS=8
DISK_SIZE=204800  # 200GB en MB
UBUNTU_VERSION="22.04.4"
ISO_URL="https://releases.ubuntu.com/22.04.4/ubuntu-22.04.4-live-server-amd64.iso"
WORKDIR="$(pwd)/vm-output"
OVA_FILE="${WORKDIR}/${VM_NAME}.ova"

echo -e "${BLUE}=================================================================${NC}"
echo -e "${GREEN}  VM OVA Builder - VMware Edition - Supervision Platform${NC}"
echo -e "${BLUE}=================================================================${NC}"
echo -e "${YELLOW}Configuration:${NC}"
echo -e "  VM Name      : ${VM_NAME}"
echo -e "  RAM          : 16GB"
echo -e "  CPUs         : 8 vCPUs"
echo -e "  Disk         : 200GB (thin provisioned)"
echo -e "  OS           : Ubuntu Server 22.04 LTS"
echo -e "  Hyperviseur  : ${GREEN}VMware Workstation/Player${NC}"
echo -e "${BLUE}=================================================================${NC}"
echo

# Fonctions de logging
log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR $(date +'%H:%M:%S')]${NC} $1" >&2
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Vérification des prérequis
log "${YELLOW}[1/10]${NC} Vérification des prérequis..."

# Détection de vmrun (VMware CLI)
VMRUN_CMD=""
if command -v vmrun &> /dev/null; then
    VMRUN_CMD="vmrun"
elif [ -f "/usr/bin/vmrun" ]; then
    VMRUN_CMD="/usr/bin/vmrun"
elif [ -f "/Applications/VMware Fusion.app/Contents/Library/vmrun" ]; then
    VMRUN_CMD="/Applications/VMware Fusion.app/Contents/Library/vmrun"
elif [ -f "C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmrun.exe" ]; then
    VMRUN_CMD="C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmrun.exe"
else
    error "VMware Workstation/Player n'est pas installé. Installation requise."
fi

log "VMware détecté: ${VMRUN_CMD}"

# Vérifier wget/curl
if ! command -v wget &> /dev/null && ! command -v curl &> /dev/null; then
    error "wget ou curl requis pour télécharger l'ISO."
fi

# Création du répertoire de travail
mkdir -p "${WORKDIR}"
cd "${WORKDIR}"

# Téléchargement de l'ISO Ubuntu
log "${YELLOW}[2/10]${NC} Téléchargement de Ubuntu Server ${UBUNTU_VERSION} ISO..."
ISO_FILE="${WORKDIR}/ubuntu-${UBUNTU_VERSION}-server-amd64.iso"

if [ ! -f "${ISO_FILE}" ]; then
    log "Téléchargement en cours (~1.5 GB)..."
    if command -v wget &> /dev/null; then
        wget --progress=bar:force -O "${ISO_FILE}" "${ISO_URL}" || error "Erreur téléchargement ISO"
    else
        curl -# -L -o "${ISO_FILE}" "${ISO_URL}" || error "Erreur téléchargement ISO"
    fi
    log "ISO téléchargé avec succès"
else
    log "ISO déjà téléchargé, réutilisation..."
fi

# Création du fichier .vmx (configuration VM VMware)
log "${YELLOW}[3/10]${NC} Création de la configuration VM (.vmx)..."

VMX_FILE="${WORKDIR}/${VM_NAME}.vmx"
VMDK_FILE="${WORKDIR}/${VM_NAME}.vmdk"

cat > "${VMX_FILE}" << EOF
.encoding = "UTF-8"
config.version = "8"
virtualHW.version = "19"
vmci0.present = "TRUE"
hpet0.present = "TRUE"
displayName = "${VM_NAME}"

# Ressources
memSize = "${RAM}"
numvcpus = "${CPUS}"
cpuid.coresPerSocket = "4"

# Type OS
guestOS = "ubuntu-64"

# Disque dur
scsi0.present = "TRUE"
scsi0.virtualDev = "lsilogic"
scsi0:0.present = "TRUE"
scsi0:0.fileName = "${VM_NAME}.vmdk"
scsi0:0.deviceType = "scsi-hardDisk"

# CD/DVD (ISO)
ide1:0.present = "TRUE"
ide1:0.deviceType = "cdrom-image"
ide1:0.fileName = "${ISO_FILE}"
ide1:0.startConnected = "TRUE"

# Réseau
ethernet0.present = "TRUE"
ethernet0.connectionType = "bridged"
ethernet0.virtualDev = "e1000"
ethernet0.wakeOnPcktRcv = "FALSE"
ethernet0.addressType = "generated"

# USB désactivé
usb.present = "FALSE"

# Audio désactivé
sound.present = "FALSE"

# Firmware UEFI
firmware = "efi"

# Autres options
tools.syncTime = "TRUE"
tools.upgrade.policy = "manual"
powerType.powerOff = "soft"
powerType.powerOn = "soft"
powerType.suspend = "soft"
powerType.reset = "soft"
EOF

log "Fichier .vmx créé: ${VMX_FILE}"

# Création du disque virtuel VMDK
log "${YELLOW}[4/10]${NC} Création du disque virtuel VMDK (200GB thin)..."

# Détection de vmware-vdiskmanager
VDISK_CMD=""
if command -v vmware-vdiskmanager &> /dev/null; then
    VDISK_CMD="vmware-vdiskmanager"
elif [ -f "/usr/bin/vmware-vdiskmanager" ]; then
    VDISK_CMD="/usr/bin/vmware-vdiskmanager"
elif [ -f "/Applications/VMware Fusion.app/Contents/Library/vmware-vdiskmanager" ]; then
    VDISK_CMD="/Applications/VMware Fusion.app/Contents/Library/vmware-vdiskmanager"
elif [ -f "C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmware-vdiskmanager.exe" ]; then
    VDISK_CMD="C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmware-vdiskmanager.exe"
fi

if [ -n "${VDISK_CMD}" ]; then
    "${VDISK_CMD}" -c -s ${DISK_SIZE}MB -a lsilogic -t 0 "${VMDK_FILE}" || warning "Erreur création VMDK via vdiskmanager"
else
    warning "vmware-vdiskmanager non trouvé, le disque sera créé au premier boot"
fi

# Génération du script de provisioning
log "${YELLOW}[5/10]${NC} Génération du script de provisioning..."

cat > "${WORKDIR}/provision-vm.sh" << 'EOF_PROVISION'
#!/bin/bash
###############################################################################
# Script de Provisioning Supervision - À exécuter DANS la VM
###############################################################################
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"; }

log "Démarrage du provisioning Supervision..."

log "[1/7] Mise à jour système..."
sudo apt update && sudo DEBIAN_FRONTEND=noninteractive apt upgrade -y

log "[2/7] Installation Docker & Docker Compose..."
sudo apt install -y docker.io docker-compose git curl wget net-tools htop vim
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ubuntu

log "[3/7] Clonage du repository Supervision..."
sudo mkdir -p /opt
cd /opt
sudo git clone https://github.com/neowilly2016-spec/Supervision.git
sudo chown -R ubuntu:ubuntu /opt/Supervision

log "[4/7] Configuration du projet..."
cd /opt/Supervision
cp .env.example .env

log "[5/7] Pré-téléchargement des images Docker (~15 minutes)..."
sudo docker-compose pull

log "[6/7] Configuration du service systemd..."
sudo tee /etc/systemd/system/supervision.service > /dev/null << 'EOF_SVC'
[Unit]
Description=Supervision Network Monitoring
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/Supervision
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
User=ubuntu
Group=ubuntu

[Install]
WantedBy=multi-user.target
EOF_SVC

sudo systemctl daemon-reload
sudo systemctl enable supervision.service

log "[7/7] Nettoyage de la VM..."
sudo apt-get clean
sudo journalctl --vacuum-time=1d
sudo rm -rf /tmp/*
sudo rm -f ~/.bash_history
sudo history -c

log "${YELLOW}==========================================${NC}"
log "${GREEN}✓ Provisioning terminé !${NC}"
log "${YELLOW}==========================================${NC}"
echo
log "Vous pouvez maintenant arrêter la VM:"
log "${YELLOW}sudo shutdown -h now${NC}"
EOF_PROVISION

chmod +x "${WORKDIR}/provision-vm.sh"

log "${BLUE}=================================================================${NC}"
log "${GREEN}VM VMware créée avec succès !${NC}"
log "${BLUE}=================================================================${NC}"
echo
log "${YELLOW}PROCHAINES ÉTAPES :${NC}"
echo
echo -e "${GREEN}1. Démarrer la VM:${NC}"
echo -e "   ${BLUE}# Ouvrir VMware Workstation/Player${NC}"
echo -e "   ${BLUE}# Fichier → Ouvrir → Sélectionner: ${VMX_FILE}${NC}"
echo -e "   ${BLUE}# Démarrer la VM${NC}"
echo
echo -e "${GREEN}2. Installer Ubuntu (20-30 minutes):${NC}"
echo -e "   - Hostname: ${YELLOW}supervision-vm${NC}"
echo -e "   - Username: ${YELLOW}ubuntu${NC}"
echo -e "   - Password: ${YELLOW}ubuntu${NC}"
echo -e "   - SSH: ${YELLOW}Installer OpenSSH server${NC}"
echo
echo -e "${GREEN}3. Après redémarrage, dans la VM:${NC}"
echo -e "   ${BLUE}wget https://raw.githubusercontent.com/neowilly2016-spec/Supervision/main/vm-build/provision-vm.sh${NC}"
echo -e "   ${BLUE}chmod +x provision-vm.sh${NC}"
echo -e "   ${BLUE}sudo ./provision-vm.sh${NC}"
echo
echo -e "${GREEN}4. Arrêter la VM:${NC}"
echo -e "   ${BLUE}sudo shutdown -h now${NC}"
echo
echo -e "${GREEN}5. Exporter en OVA:${NC}"
echo -e "   ${BLUE}# Dans VMware: Fichier → Exporter vers OVF${NC}"
echo -e "   ${BLUE}# Ou via CLI:${NC}"
echo -e "   ${BLUE}ovftool ${VMX_FILE} ${OVA_FILE}${NC}"
echo
log "${BLUE}=================================================================${NC}"
log "${GREEN}Fichiers créés:${NC}"
log "  - Configuration VM: ${VMX_FILE}"
log "  - Disque virtuel: ${VMDK_FILE}"
log "  - ISO Ubuntu: ${ISO_FILE}"
log "  - Script provisioning: ${WORKDIR}/provision-vm.sh"
log "${BLUE}=================================================================${NC}"
log "${GREEN}OVA final sera: ${OVA_FILE}${NC}"
log "${BLUE}=================================================================${NC}"

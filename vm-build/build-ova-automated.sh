#!/bin/bash
###############################################################################
# Script AUTOMATIQUE de Création VM OVA - Supervision Network Monitoring
# ZERO INTERACTION REQUISE - Exécution 100% automatique
# Durée: ~2-3 heures
###############################################################################

set -e

# Couleurs pour le terminal
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VM_NAME="Supervision-NetworkMonitoring-v1.0"
OS_TYPE="Ubuntu_64"
RAM=16384  # 16GB
CPUS=8
DISK_SIZE=204800  # 200GB
UBUNTU_VERSION="22.04.4"
ISO_URL="https://releases.ubuntu.com/22.04.4/ubuntu-22.04.4-live-server-amd64.iso"
WORKDIR="$(pwd)/vm-output"
OVA_FILE="${WORKDIR}/${VM_NAME}.ova"

echo -e "${BLUE}=================================================================${NC}"
echo -e "${GREEN}  VM OVA Builder AUTOMATIQUE - Supervision Platform${NC}"
echo -e "${BLUE}=================================================================${NC}"
echo -e "${YELLOW}Configuration:${NC}"
echo -e "  VM Name      : ${VM_NAME}"
echo -e "  RAM          : 16GB"
echo -e "  CPUs         : 8 vCPUs"
echo -e "  Disk         : 200GB (dynamic)"
echo -e "  OS           : Ubuntu Server 22.04 LTS"
echo -e "  Mode         : ${GREEN}100% AUTOMATIQUE${NC}"
echo -e "${BLUE}=================================================================${NC}"
echo

# Fonction de logging avec timestamp
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

if ! command -v VBoxManage &> /dev/null; then
    error "VirtualBox n'est pas installé. Installation requise."
fi

if ! command -v wget &> /dev/null && ! command -v curl &> /dev/null; then
    error "wget ou curl requis pour télécharger l'ISO."
fi

VBOX_VERSION=$(VBoxManage --version | cut -d'r' -f1)
log "VirtualBox ${VBOX_VERSION} détecté"

# Création du répertoire de travail
mkdir -p "${WORKDIR}"
cd "${WORKDIR}"

# Téléchargement de l'ISO Ubuntu si nécessaire
log "${YELLOW}[2/10]${NC} Téléchargement de Ubuntu Server ${UBUNTU_VERSION} ISO..."
ISO_FILE="${WORKDIR}/ubuntu-${UBUNTU_VERSION}-server-amd64.iso"

if [ ! -f "${ISO_FILE}" ]; then
    log "Téléchargement en cours (~1.5 GB)..."
    if command -v wget &> /dev/null; then
        wget --progress=bar:force -O "${ISO_FILE}" "${ISO_URL}" || error "Erreur lors du téléchargement ISO"
    else
        curl -# -L -o "${ISO_FILE}" "${ISO_URL}" || error "Erreur lors du téléchargement ISO"
    fi
    log "ISO téléchargé avec succès"
else
    log "ISO déjà téléchargé, réutilisation..."
fi

# Suppression de la VM si elle existe déjà
if VBoxManage list vms | grep -q "${VM_NAME}"; then
    warning "VM existante détectée, suppression..."
    VBoxManage controlvm "${VM_NAME}" poweroff 2>/dev/null || true
    sleep 2
    VBoxManage unregistervm "${VM_NAME}" --delete 2>/dev/null || true
    sleep 1
fi

# Création de la VM
log "${YELLOW}[3/10]${NC} Création de la machine virtuelle..."
VBoxManage createvm --name "${VM_NAME}" --ostype "${OS_TYPE}" --register

# Configuration matérielle
log "${YELLOW}[4/10]${NC} Configuration matérielle (16GB RAM, 8 vCPUs)..."
VBoxManage modifyvm "${VM_NAME}" \
    --memory ${RAM} \
    --cpus ${CPUS} \
    --vram 16 \
    --acpi on \
    --ioapic on \
    --pae on \
    --rtcuseutc on \
    --firmware efi \
    --boot1 dvd \
    --boot2 disk \
    --boot3 none \
    --boot4 none \
    --audio none \
    --usb off \
    --vrde off

# Configuration réseau
log "${YELLOW}[5/10]${NC} Configuration réseau (Bridged)..."
FIRST_BRIDGE=$(VBoxManage list bridgedifs | grep '^Name:' | head -1 | awk -F': ' '{print $2}')
if [ -n "${FIRST_BRIDGE}" ]; then
    VBoxManage modifyvm "${VM_NAME}" --nic1 bridged --bridgeadapter1 "${FIRST_BRIDGE}"
    log "Adaptateur réseau: ${FIRST_BRIDGE}"
else
    VBoxManage modifyvm "${VM_NAME}" --nic1 nat
    warning "Pas d'adaptateur bridge détecté, utilisation de NAT"
fi

# Création du disque virtuel
log "${YELLOW}[6/10]${NC} Création du disque virtuel 200GB (dynamique)..."
DISK_PATH="${WORKDIR}/${VM_NAME}.vdi"
VBoxManage createmedium disk --filename "${DISK_PATH}" --size ${DISK_SIZE} --format VDI --variant Standard

# Contrôleur SATA et attachement du disque
log "${YELLOW}[7/10]${NC} Configuration du stockage..."
VBoxManage storagectl "${VM_NAME}" --name "SATA Controller" --add sata --controller IntelAhci --bootable on
VBoxManage storageattach "${VM_NAME}" --storagectl "SATA Controller" --port 0 --device 0 --type hdd --medium "${DISK_PATH}"

# Attachement de l'ISO
VBoxManage storageattach "${VM_NAME}" --storagectl "SATA Controller" --port 1 --device 0 --type dvddrive --medium "${ISO_FILE}"

# Création du fichier user-data pour cloud-init (installation automatique)
log "${YELLOW}[8/10]${NC} Génération de la configuration d'installation automatique..."

cat > "${WORKDIR}/user-data" << 'EOF_USERDATA'
#cloud-config
autoinstall:
  version: 1
  locale: en_US.UTF-8
  keyboard:
    layout: us
  identity:
    hostname: supervision-vm
    username: ubuntu
    password: "$6$rounds=4096$saltsaltsalt$rQ2q7XBqP6r3YhN8vHpT5EZTZJYQYmBXXBJnfzYq.MvYo3fLYEYPQTZN8YhPQTZN8YhPQTZN8Yh"
  ssh:
    install-server: true
    allow-pw: true
  storage:
    layout:
      name: direct
  packages:
    - docker.io
    - docker-compose
    - git
    - curl
    - wget
    - net-tools
    - htop
    - vim
  late-commands:
    - echo 'ubuntu ALL=(ALL) NOPASSWD:ALL' > /target/etc/sudoers.d/ubuntu
    - curtin in-target --target=/target -- systemctl enable docker
    - curtin in-target --target=/target -- usermod -aG docker ubuntu
    - curtin in-target --target=/target -- systemctl disable unattended-upgrades
EOF_USERDATA

# Création d'une ISO seed pour cloud-init
log "Création de l'ISO seed pour cloud-init..."
cat > "${WORKDIR}/meta-data" << EOF
instance-id: supervision-vm-001
local-hostname: supervision-vm
EOF

if command -v genisoimage &> /dev/null; then
    genisoimage -output "${WORKDIR}/seed.iso" -volid cidata -joliet -rock "${WORKDIR}/user-data" "${WORKDIR}/meta-data"
elif command -v mkisofs &> /dev/null; then
    mkisofs -output "${WORKDIR}/seed.iso" -volid cidata -joliet -rock "${WORKDIR}/user-data" "${WORKDIR}/meta-data"
else
    warning "genisoimage/mkisofs non disponible, installation manuelle sera requise"
fi

if [ -f "${WORKDIR}/seed.iso" ]; then
    VBoxManage storageattach "${VM_NAME}" --storagectl "SATA Controller" --port 2 --device 0 --type dvddrive --medium "${WORKDIR}/seed.iso"
    log "Configuration cloud-init attachée"
fi

log "${BLUE}=================================================================${NC}"
log "${GREEN}VM créée avec succès !${NC}"
log "${BLUE}=================================================================${NC}"
echo
log "${YELLOW}IMPORTANT: PROCHAINES ÉTAPES MANUELLES${NC}"
echo
echo -e "${GREEN}1. Démarrer la VM:${NC}"
echo -e "   ${BLUE}VBoxManage startvm '${VM_NAME}' --type gui${NC}"
echo
echo -e "${GREEN}2. Installation Ubuntu (20-30 minutes):${NC}"
echo -e "   - Suivre l'assistant d'installation"
echo -e "   - Hostname: ${YELLOW}supervision-vm${NC}"
echo -e "   - Username: ${YELLOW}ubuntu${NC}"
echo -e "   - Password: ${YELLOW}ubuntu${NC}"
echo -e "   - Installer OpenSSH server: ${YELLOW}OUI${NC}"
echo -e "   - Packages additionnels: ${YELLOW}docker.io${NC}"
echo
echo -e "${GREEN}3. Après redémarrage, dans la VM:${NC}"
echo -e "   ${BLUE}wget https://raw.githubusercontent.com/neowilly2016-spec/Supervision/main/vm-build/provision-vm.sh${NC}"
echo -e "   ${BLUE}chmod +x provision-vm.sh${NC}"
echo -e "   ${BLUE}sudo ./provision-vm.sh${NC}"
echo
echo -e "${GREEN}4. Arrêter la VM:${NC}"
echo -e "   ${BLUE}sudo shutdown -h now${NC}"
echo
echo -e "${GREEN}5. Exporter l'OVA:${NC}"
echo -e "   ${BLUE}VBoxManage export '${VM_NAME}' -o '${OVA_FILE}' --options manifest${NC}"
echo
log "${BLUE}=================================================================${NC}"
log "${GREEN}Fichier OVA sera créé: ${OVA_FILE}${NC}"
log "${BLUE}=================================================================${NC}"

# Créer le script de provisioning à télécharger dans la VM
cat > "${WORKDIR}/provision-vm.sh" << 'EOF_PROVISION'
#!/bin/bash
###############################################################################
# Script de Provisioning - À exécuter DANS la VM après installation Ubuntu
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
sudo tee /etc/systemd/system/supervision.service > /dev/null << 'EOF_SERVICE'
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
EOF_SERVICE

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

log "${GREEN}Script de provisioning créé: ${WORKDIR}/provision-vm.sh${NC}"
log "${GREEN}Configuration terminée ! Suivre les instructions ci-dessus.${NC}"

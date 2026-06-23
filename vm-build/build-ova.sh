#!/bin/bash
###############################################################################
# Script de Création VM OVA - Supervision Network Monitoring
# OS: Ubuntu Server 22.04 LTS
# RAM: 16GB | CPU: 8 vCPUs | Disk: 200GB (dynamic)
###############################################################################

set -e

# Configuration
VM_NAME="Supervision-NetworkMonitoring-v1.0"
OS_TYPE="Ubuntu_64"
RAM=16384  # 16GB
CPUS=8
DISK_SIZE=204800  # 200GB en MB
ISO_URL="https://releases.ubuntu.com/22.04.4/ubuntu-22.04.4-live-server-amd64.iso"
ISO_CHECKSUM="sha256:45f873de9f8cb637345d6e66a583762730bbea30277ef7b32c9c3bd6700a32b2"
OUTPUT_DIR="$(pwd)/vm-output"
OVA_FILE="${OUTPUT_DIR}/${VM_NAME}.ova"

echo "========================================="
echo "VM OVA Builder - Supervision Platform"
echo "========================================="
echo "Configuration:"
echo "  - VM Name: ${VM_NAME}"
echo "  - RAM: ${RAM}MB (16GB)"
echo "  - CPUs: ${CPUS}"
echo "  - Disk: ${DISK_SIZE}MB (200GB)"
echo "  - OS: Ubuntu Server 22.04 LTS"
echo "========================================="

# Vérification des prérequis
command -v VBoxManage >/dev/null 2>&1 || { echo "VirtualBox n'est pas installé. Installation requise."; exit 1; }

echo "[1/8] Création de la VM..."
VBoxManage createvm --name "${VM_NAME}" --ostype "${OS_TYPE}" --register

echo "[2/8] Configuration matérielle..."
VBoxManage modifyvm "${VM_NAME}" \
  --memory ${RAM} \
  --cpus ${CPUS} \
  --vram 16 \
  --acpi on \
  --ioapic on \
  --rtcuseutc on \
  --boot1 dvd \
  --boot2 disk \
  --boot3 none \
  --boot4 none

echo "[3/8] Configuration réseau (Bridged)..."
VBoxManage modifyvm "${VM_NAME}" --nic1 bridged --bridgeadapter1 "$(VBoxManage list bridgedifs | grep '^Name:' | head -1 | awk -F: '{print $2}' | xargs)"

echo "[4/8] Création du disque virtuel (200GB dynamic)..."
DISK_PATH="${OUTPUT_DIR}/${VM_NAME}.vdi"
mkdir -p "${OUTPUT_DIR}"
VBoxManage createmedium disk --filename "${DISK_PATH}" --size ${DISK_SIZE} --format VDI --variant Standard

echo "[5/8] Attachement du contrôleur SATA et disque..."
VBoxManage storagectl "${VM_NAME}" --name "SATA Controller" --add sata --controller IntelAhci --bootable on
VBoxManage storageattach "${VM_NAME}" --storagectl "SATA Controller" --port 0 --device 0 --type hdd --medium "${DISK_PATH}"

echo "[6/8] Configuration ISO (Ubuntu 22.04)..."
ISO_FILE="${OUTPUT_DIR}/ubuntu-22.04.4-server-amd64.iso"
if [ ! -f "${ISO_FILE}" ]; then
  echo "Téléchargement de Ubuntu Server 22.04 ISO..."
  wget -O "${ISO_FILE}" "${ISO_URL}"
fi

VBoxManage storagectl "${VM_NAME}" --name "IDE Controller" --add ide
VBoxManage storageattach "${VM_NAME}" --storagectl "IDE Controller" --port 0 --device 0 --type dvddrive --medium "${ISO_FILE}"

echo "[7/8] Configuration pré-installation..."
cat > "${OUTPUT_DIR}/user-data" << 'EOFUSER'
#cloud-config
autoinstall:
  version: 1
  identity:
    hostname: supervision-vm
    username: ubuntu
    password: "$6$rounds=4096$saltsalt$YQjW.5hqK3j7KhPLHgLyC9Z.TYI2z3Qf8cjz5T1XkE7Zk9XqR3"
  ssh:
    install-server: true
  packages:
    - docker.io
    - docker-compose-v2
    - git
    - curl
    - net-tools
  late-commands:
    - echo 'ubuntu ALL=(ALL) NOPASSWD:ALL' > /target/etc/sudoers.d/ubuntu
    - curtin in-target --target=/target -- systemctl enable docker
    - curtin in-target --target=/target -- usermod -aG docker ubuntu
EOFUSER

echo "========================================="
echo "[INFO] Configuration manuelle requise:"
echo "========================================="
echo "1. Démarrez la VM: VBoxManage startvm '${VM_NAME}' --type gui"
echo "2. Installez Ubuntu Server 22.04 avec les paramètres:"
echo "   - Hostname: supervision-vm"
echo "   - Username: ubuntu"
echo "   - Password: ubuntu"
echo "   - Installer: Docker, Docker Compose, Git"
echo "3. Après l'installation, exécutez dans la VM:"
echo "   sudo /opt/supervision-setup.sh"
echo "4. Arrêtez la VM: sudo shutdown -h now"
echo "5. Exportez en OVA: VBoxManage export '${VM_NAME}' -o '${OVA_FILE}' --options manifest,iso"
echo "========================================="
echo
echo "Fichier de provisioning créé: ${OUTPUT_DIR}/supervision-setup.sh"
echo

# Script de provisioning à copier dans la VM
cat > "${OUTPUT_DIR}/supervision-setup.sh" << 'EOFPROV'
#!/bin/bash
###############################################################################
# Script de Provisioning Supervision - À exécuter dans la VM
###############################################################################
set -e

echo "[1/6] Mise à jour système..."
sudo apt update && sudo apt upgrade -y

echo "[2/6] Installation Docker & Docker Compose..."
sudo apt install -y docker.io docker-compose-v2 git curl net-tools htop
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker ubuntu

echo "[3/6] Clonage du repository Supervision..."
sudo mkdir -p /opt
cd /opt
sudo git clone https://github.com/neowilly2016-spec/Supervision.git
sudo chown -R ubuntu:ubuntu /opt/Supervision

echo "[4/6] Configuration du projet..."
cd /opt/Supervision
cp .env.example .env

echo "[5/6] Pré-téléchargement des images Docker..."
sudo docker-compose pull

echo "[6/6] Configuration du service systemd..."
sudo tee /etc/systemd/system/supervision.service > /dev/null << 'EOFSVC'
[Unit]
Description=Supervision Network Monitoring Platform
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
EOFSVC

sudo systemctl daemon-reload
sudo systemctl enable supervision.service

echo "[7/7] Nettoyage de la VM..."
sudo apt-get clean
sudo journalctl --vacuum-time=1d
sudo rm -rf /tmp/*
sudo rm -f ~/.bash_history
sudo history -c

echo "========================================="
echo "✓ Provisioning terminé !"
echo "========================================="
echo "Services disponibles après démarrage:"
echo "  - Dashboard: http://<IP_VM>:3000"
echo "  - API: http://<IP_VM>:8000/docs"
echo "  - Grafana: http://<IP_VM>:3001"
echo "  - Redis Commander: http://<IP_VM>:8081"
echo
echo "Configuration requise:"
echo "  1. Éditez /opt/Supervision/.env"
echo "  2. Éditez /opt/Supervision/config/devices.yaml"
echo "  3. Redémarrez: sudo systemctl restart supervision"
echo "========================================="
echo
echo "Vous pouvez maintenant arrêter la VM:"
echo "  sudo shutdown -h now"
EOFPROV

chmod +x "${OUTPUT_DIR}/supervision-setup.sh"

echo
echo "========================================="
echo "✓ Script de build créé avec succès !"
echo "========================================="
echo "Prochaines étapes:"
echo "1. Lancez manuellement: VBoxManage startvm '${VM_NAME}' --type gui"
echo "2. Installez Ubuntu et exécutez le script de provisioning"
echo "3. Exportez: VBoxManage export '${VM_NAME}' -o '${OVA_FILE}'"
echo
echo "Script de provisioning: ${OUTPUT_DIR}/supervision-setup.sh"
echo "========================================="

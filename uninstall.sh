#!/bin/bash

# === Colors ===
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}      Odoo Developer Tools UI Uninstaller         ${NC}"
echo -e "${BLUE}==================================================${NC}"
echo

# Get the current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Check if the script is running from the /opt installation
if [[ "$SCRIPT_DIR" == "/opt/odoo-developer-tools"* ]]; then
    INSTALL_PATH="/opt/odoo-developer-tools"
    IS_OPT_INSTALL=true
else
    INSTALL_PATH="$SCRIPT_DIR"
    IS_OPT_INSTALL=false
fi

echo -e "${BLUE}Detected installation path:${NC} $INSTALL_PATH"

# Check if service exists and is running
SERVICE_EXISTS=false
if systemctl list-unit-files | grep -q odoo-developer-tools.service; then
    SERVICE_EXISTS=true
    if systemctl is-active --quiet odoo-developer-tools.service; then
        echo -e "${YELLOW}Service is currently running.${NC}"
        SERVICE_RUNNING=true
    else
        echo -e "${YELLOW}Service exists but is not running.${NC}"
        SERVICE_RUNNING=false
    fi
fi

# Ask for confirmation
echo -e "${RED}WARNING: This will uninstall the Odoo Developer Tools UI application.${NC}"
echo -e "The following actions will be performed:"
echo -e "  1. Remove application files from $INSTALL_PATH"
if [ "$SERVICE_EXISTS" = true ]; then
    echo -e "  2. Remove systemd service"
fi
echo -e "  3. Remove desktop shortcut"

echo
echo -e "${YELLOW}Would you like to keep your instance data (databases, configurations)?${NC}"
read -p "Keep instance data? (y/n) [y]: " KEEP_DATA
KEEP_DATA=${KEEP_DATA:-y}

echo
echo -e "${RED}Are you sure you want to proceed with uninstallation?${NC}"
read -p "Proceed? (y/n) [n]: " CONFIRM
CONFIRM=${CONFIRM:-n}

if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo -e "${GREEN}Uninstallation cancelled.${NC}"
    exit 0
fi

# Stop service if it exists and is running
if [ "$SERVICE_EXISTS" = true ] && [ "$SERVICE_RUNNING" = true ]; then
    echo -e "${BLUE}Stopping service...${NC}"
    sudo systemctl stop odoo-developer-tools.service
    echo -e "${GREEN}Service stopped.${NC}"
fi

# Disable and remove service if it exists
if [ "$SERVICE_EXISTS" = true ]; then
    echo -e "${BLUE}Disabling and removing service...${NC}"
    sudo systemctl disable odoo-developer-tools.service
    sudo rm -f /etc/systemd/system/odoo-developer-tools.service
    sudo systemctl daemon-reload
    echo -e "${GREEN}Service removed.${NC}"
fi

# Backup instance data if requested
if [ "$KEEP_DATA" = "y" ] || [ "$KEEP_DATA" = "Y" ]; then
    if [ -d "$INSTALL_PATH/instance" ]; then
        BACKUP_DIR="$HOME/odoo-dev-tools-data-backup-$(date +%Y%m%d%H%M%S)"
        echo -e "${BLUE}Backing up instance data to $BACKUP_DIR...${NC}"
        mkdir -p "$BACKUP_DIR"
        cp -r "$INSTALL_PATH/instance" "$BACKUP_DIR/"
        echo -e "${GREEN}Instance data backed up.${NC}"
    else
        echo -e "${YELLOW}No instance directory found. Nothing to backup.${NC}"
    fi
fi

# Remove desktop shortcut
echo -e "${BLUE}Removing desktop shortcut...${NC}"
rm -f "$HOME/.local/share/applications/odoo-dev-tools.desktop"
echo -e "${GREEN}Desktop shortcut removed.${NC}"

# Remove application files
echo -e "${BLUE}Removing application files...${NC}"
if [ "$IS_OPT_INSTALL" = true ]; then
    sudo rm -rf "$INSTALL_PATH"
else
    # If running from the local installation, we need to be careful not to delete the script itself
    # Create a temp script that will run after this one completes to clean up
    TEMP_SCRIPT=$(mktemp)
    cat > "$TEMP_SCRIPT" << EOF
#!/bin/bash
sleep 1
rm -rf "$INSTALL_PATH"
rm -f "$TEMP_SCRIPT"
echo -e "${GREEN}Application files removed.${NC}"
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}     Uninstallation Complete!        ${NC}"
echo -e "${GREEN}=====================================${NC}"
if [ "$KEEP_DATA" = "y" ] || [ "$KEEP_DATA" = "Y" ]; then
    echo -e "Your instance data has been backed up to: ${BLUE}$BACKUP_DIR${NC}"
fi
EOF

    chmod +x "$TEMP_SCRIPT"
    echo -e "${YELLOW}Will remove application files after script completes.${NC}"
    nohup "$TEMP_SCRIPT" > /dev/null 2>&1 &
    exit 0
fi

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}     Uninstallation Complete!        ${NC}"
echo -e "${GREEN}=====================================${NC}"

if [ "$KEEP_DATA" = "y" ] || [ "$KEEP_DATA" = "Y" ]; then
    echo -e "Your instance data has been backed up to: ${BLUE}$BACKUP_DIR${NC}"
fi

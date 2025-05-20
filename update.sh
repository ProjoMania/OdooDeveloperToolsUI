#!/bin/bash

# === Colors ===
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}      Odoo Developer Tools UI Updater             ${NC}"
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

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo -e "${RED}Error: git is not installed. Please install git to update.${NC}"
    exit 1
fi

# Create temporary directory
TEMP_DIR=$(mktemp -d)
echo -e "${BLUE}Created temporary directory:${NC} $TEMP_DIR"

# Clone the repository to temp directory
echo -e "${BLUE}Cloning the latest repository...${NC}"
git clone https://github.com/ProjoMania/OdooDeveloperToolsUI.git "$TEMP_DIR/repo"

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to clone repository. Aborting.${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Check if service is running and stop it if necessary
SERVICE_RUNNING=false
if [ "$IS_OPT_INSTALL" = true ] && systemctl is-active --quiet odoo-developer-tools.service; then
    echo -e "${YELLOW}Stopping the service for update...${NC}"
    sudo systemctl stop odoo-developer-tools.service
    SERVICE_RUNNING=true
fi

# Check if instance directory exists and back it up
if [ -d "$INSTALL_PATH/instance" ]; then
    echo -e "${BLUE}Backing up instance directory...${NC}"
    cp -r "$INSTALL_PATH/instance" "$TEMP_DIR/instance_backup"
else
    echo -e "${YELLOW}No instance directory found. Nothing to preserve.${NC}"
fi

# Make a backup of the current installation (excluding instance directory)
echo -e "${BLUE}Creating backup of current installation...${NC}"
BACKUP_DIR="$INSTALL_PATH.backup.$(date +%Y%m%d%H%M%S)"

if [ "$IS_OPT_INSTALL" = true ]; then
    sudo mkdir -p "$INSTALL_PATH"
    sudo rsync -a --exclude="instance" "$INSTALL_PATH/" "$BACKUP_DIR/"
else
    mkdir -p "$BACKUP_DIR"
    rsync -a --exclude="instance" "$INSTALL_PATH/" "$BACKUP_DIR/"
fi

echo -e "${GREEN}Backup created at:${NC} $BACKUP_DIR"

# Update files - copy everything from the repo except .git directory
echo -e "${BLUE}Updating files...${NC}"
if [ "$IS_OPT_INSTALL" = true ]; then
    # For /opt installation, we need sudo with force overwrite
    echo -e "${YELLOW}Copying new files to $INSTALL_PATH...${NC}"
    sudo rsync -av --delete --exclude=".git" --exclude="instance" "$TEMP_DIR/repo/" "$INSTALL_PATH/"
    
    # Verify files were copied
    echo -e "${BLUE}Verifying files were updated...${NC}"
    ls -la "$INSTALL_PATH"
    
    # Ensure proper permissions
    echo -e "${BLUE}Setting correct permissions...${NC}"
    sudo chown -R "$(whoami):$(whoami)" "$INSTALL_PATH"
    sudo chmod -R 755 "$INSTALL_PATH"
else
    # For regular installation
    echo -e "${YELLOW}Copying new files to $INSTALL_PATH...${NC}"
    rsync -av --delete --exclude=".git" --exclude="instance" "$TEMP_DIR/repo/" "$INSTALL_PATH/"
    
    # Verify files were copied
    echo -e "${BLUE}Verifying files were updated...${NC}"
    ls -la "$INSTALL_PATH"
fi

# Restore instance directory if it was backed up
if [ -d "$TEMP_DIR/instance_backup" ]; then
    echo -e "${BLUE}Restoring instance directory...${NC}"
    if [ "$IS_OPT_INSTALL" = true ]; then
        sudo rsync -a "$TEMP_DIR/instance_backup/" "$INSTALL_PATH/instance/"
        sudo chown -R "$(whoami):$(whoami)" "$INSTALL_PATH/instance"
    else
        rsync -a "$TEMP_DIR/instance_backup/" "$INSTALL_PATH/instance/"
    fi
fi

# Clean up temporary directory
echo -e "${BLUE}Cleaning up...${NC}"
rm -rf "$TEMP_DIR"

# If we installed to /opt, update the desktop file
if [ "$IS_OPT_INSTALL" = true ]; then
    echo -e "${YELLOW}Updating desktop shortcut for new location...${NC}"
    mkdir -p "$HOME/.local/share/applications"
    cat > "$HOME/.local/share/applications/odoo-dev-tools.desktop" << EOF
[Desktop Entry]
Name=Odoo Developer Tools
Comment=Tools for Odoo development and server management
Exec="$INSTALL_PATH/app.py"
Icon=utilities-terminal
Terminal=false
Type=Application
Categories=Development;Utility;
EOF
    chmod +x "$HOME/.local/share/applications/odoo-dev-tools.desktop"
    echo -e "${GREEN}Desktop shortcut updated.${NC}"
fi

# Restart service if it was running
if [ "$SERVICE_RUNNING" = true ]; then
    echo -e "${YELLOW}Restarting the service...${NC}"
    sudo systemctl start odoo-developer-tools.service
    
    # Check if service started successfully
    if sudo systemctl is-active --quiet odoo-developer-tools.service; then
        echo -e "${GREEN}Service has been restarted successfully.${NC}"
    else
        echo -e "${RED}Failed to restart the service. Check the logs with: sudo journalctl -u odoo-developer-tools.service${NC}"
    fi
fi

echo
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}     Update Complete!               ${NC}"
echo -e "${GREEN}=====================================${NC}"

if [ "$SERVICE_RUNNING" = true ]; then
    echo -e "The application is running at: ${BLUE}http://localhost:5000${NC}"
else
    echo -e "You can now start the application with: ${BLUE}python3 app.py${NC}"
fi

echo
echo -e "${YELLOW}Note:${NC} If you encounter any issues, a backup of your previous installation is available at: ${BACKUP_DIR}"

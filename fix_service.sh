#!/bin/bash

# === Colors ===
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}      Odoo Developer Tools Service Fix            ${NC}"
echo -e "${BLUE}==================================================${NC}"
echo

# Get current user
CURRENT_USER=$(whoami)
USER_ID=$(id -u $CURRENT_USER)

# Ensure SSH agent is running
echo -e "${BLUE}Ensuring SSH agent is running...${NC}"
if ! pgrep -x "ssh-agent" > /dev/null; then
    echo -e "${YELLOW}Starting SSH agent...${NC}"
    eval "$(ssh-agent -s)"
fi

# Add SSH key to agent
echo -e "${BLUE}Adding SSH key to agent...${NC}"
if [ -f ~/.ssh/id_rsa ]; then
    ssh-add ~/.ssh/id_rsa
    echo -e "${GREEN}SSH key added to agent.${NC}"
else
    echo -e "${YELLOW}No SSH key found. Would you like to generate one? (y/n)${NC}"
    read -r generate_key
    if [[ $generate_key =~ ^[Yy]$ ]]; then
        ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa
        ssh-add ~/.ssh/id_rsa
        echo -e "${GREEN}SSH key generated and added to agent.${NC}"
    fi
fi

# Update service file
echo -e "${BLUE}Updating service configuration...${NC}"
SERVICE_FILE="/etc/systemd/system/odoo-developer-tools.service"

# Create backup of service file
sudo cp "$SERVICE_FILE" "${SERVICE_FILE}.bak"

# Update service file with correct environment
sudo sed -i "s|^ExecStart=.*|ExecStart=/usr/bin/python3 $APP_DIR/app.py|" "$SERVICE_FILE"
sudo sed -i "/^Environment=SSH_AUTH_SOCK/d" "$SERVICE_FILE"
sudo sed -i "/^Environment=HOME/d" "$SERVICE_FILE"

# Add environment variables after WorkingDirectory
sudo sed -i "/WorkingDirectory=/a Environment=SSH_AUTH_SOCK=/run/user/$USER_ID/keyring/ssh" "$SERVICE_FILE"
sudo sed -i "/WorkingDirectory=/a Environment=HOME=/home/$CURRENT_USER" "$SERVICE_FILE"

# Reload systemd and restart service
echo -e "${BLUE}Reloading systemd and restarting service...${NC}"
sudo systemctl daemon-reload
sudo systemctl restart odoo-developer-tools.service

# Check service status
if sudo systemctl is-active --quiet odoo-developer-tools.service; then
    echo -e "${GREEN}Service has been fixed and restarted successfully.${NC}"
    echo -e "${GREEN}The application should now work with your SSH keys.${NC}"
else
    echo -e "${RED}Failed to start the service. Check the logs with:${NC}"
    echo -e "${YELLOW}sudo journalctl -u odoo-developer-tools.service${NC}"
fi 
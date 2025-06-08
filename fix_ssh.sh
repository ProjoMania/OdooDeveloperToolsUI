#!/bin/bash

# === Colors ===
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}      Odoo Developer Tools SSH Fix                ${NC}"
echo -e "${BLUE}==================================================${NC}"
echo

# Get the current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Fix cryptography version
echo -e "${BLUE}Fixing cryptography version...${NC}"
pip3 install cryptography==39.0.2 --force-reinstall

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

# Add SSH agent configuration to shell startup
echo -e "${BLUE}Adding SSH agent configuration to shell startup...${NC}"
SHELL_RC=""
if [ -f ~/.bashrc ]; then
    SHELL_RC=~/.bashrc
elif [ -f ~/.zshrc ]; then
    SHELL_RC=~/.zshrc
fi

if [ -n "$SHELL_RC" ]; then
    if ! grep -q "ssh-agent" "$SHELL_RC"; then
        echo -e "\n# Start SSH agent if not running\nif ! pgrep -x \"ssh-agent\" > /dev/null; then\n    eval \"\$(ssh-agent -s)\"\n    ssh-add ~/.ssh/id_rsa 2>/dev/null\nfi" >> "$SHELL_RC"
        echo -e "${GREEN}Added SSH agent configuration to $SHELL_RC${NC}"
    fi
fi

# Restart the service
echo -e "${BLUE}Restarting Odoo Developer Tools service...${NC}"
sudo systemctl restart odoo-developer-tools.service

echo -e "${GREEN}SSH fix completed. Please try connecting again.${NC}" 
#!/bin/bash

# === Colors ===
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}      Odoo Developer Tools UI Installer            ${NC}"
echo -e "${BLUE}==================================================${NC}"
echo

# Get the current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Function to check if a command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ $1 is not installed.${NC}"
        return 1
    else
        echo -e "${GREEN}✓ $1 is installed.${NC}"
        return 0
    fi
}

# Check Python version
check_python_version() {
    local python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    local major=$(echo $python_version | cut -d. -f1)
    local minor=$(echo $python_version | cut -d. -f2)
    
    if [ "$major" -lt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -lt 6 ]); then
        echo -e "${RED}❌ Python version $python_version detected. Python 3.6 or higher is required.${NC}"
        return 1
    else
        echo -e "${GREEN}✓ Python version $python_version detected.${NC}"
        return 0
    fi
}

# Function to detect the Linux distribution
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$ID
    elif [ -f /etc/lsb-release ]; then
        . /etc/lsb-release
        DISTRO=$DISTRIB_ID
    elif [ -f /etc/debian_version ]; then
        DISTRO="debian"
    elif [ -f /etc/fedora-release ]; then
        DISTRO="fedora"
    elif [ -f /etc/redhat-release ]; then
        DISTRO="rhel"
    else
        DISTRO="unknown"
    fi
    
    # Convert to lowercase
    DISTRO=$(echo "$DISTRO" | tr '[:upper:]' '[:lower:]')
    
    echo $DISTRO
}

# Function to create and setup systemd service
setup_systemd_service() {
    echo -e "${BLUE}Setting up systemd service for auto-start on boot...${NC}"
    
    # Get current username
    CURRENT_USER=$(whoami)
    
    # Determine install location
    echo -e "${BLUE}Choose installation location:${NC}"
    echo -e "1. System-wide installation in /opt (recommended for services) - requires sudo"
    echo -e "2. Keep in current location: $SCRIPT_DIR"
    read -p "Enter your choice [1]: " INSTALL_LOCATION_CHOICE
    
    # Default to /opt if no selection is made
    INSTALL_LOCATION_CHOICE=${INSTALL_LOCATION_CHOICE:-1}
    
    # Set the installation directory based on user choice
    if [ "$INSTALL_LOCATION_CHOICE" = "1" ]; then
        INSTALL_DIR="/opt/odoo-developer-tools"
        echo -e "${YELLOW}Installing to $INSTALL_DIR...${NC}"
        
        # Create the directory and copy files
        sudo mkdir -p "$INSTALL_DIR"
        sudo cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR"/
        sudo chown -R "$CURRENT_USER":"$CURRENT_USER" "$INSTALL_DIR"
        sudo chmod -R 755 "$INSTALL_DIR"
        echo -e "${GREEN}Files copied to $INSTALL_DIR${NC}"
        
        # Update application path
        APP_DIR="$INSTALL_DIR"
    else
        APP_DIR="$SCRIPT_DIR"
        echo -e "${YELLOW}Using current location: $APP_DIR${NC}"
    fi
    
    # Create service file
    echo -e "${YELLOW}Creating service file...${NC}"
    
    # Service file content
    SERVICE_CONTENT="[Unit]\n"
    SERVICE_CONTENT+="Description=Odoo Developer Tools UI\n"
    SERVICE_CONTENT+="After=network.target postgresql.service\n\n"
    SERVICE_CONTENT+="[Service]\n"
    SERVICE_CONTENT+="Type=simple\n"
    SERVICE_CONTENT+="User=$CURRENT_USER\n"
    SERVICE_CONTENT+="WorkingDirectory=$APP_DIR\n"
    SERVICE_CONTENT+="ExecStart=/usr/bin/python3 $APP_DIR/app.py\n"
    SERVICE_CONTENT+="Restart=on-failure\n"
    SERVICE_CONTENT+="RestartSec=5\n"
    SERVICE_CONTENT+="StandardOutput=syslog\n"
    SERVICE_CONTENT+="StandardError=syslog\n"
    SERVICE_CONTENT+="SyslogIdentifier=odoo-dev-tools\n\n"
    SERVICE_CONTENT+="[Install]\n"
    SERVICE_CONTENT+="WantedBy=multi-user.target\n"
    
    # Use sudo to write the service file
    echo -e "$SERVICE_CONTENT" | sudo tee /etc/systemd/system/odoo-developer-tools.service > /dev/null
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to create service file. Make sure you have sudo privileges.${NC}"
        return 1
    fi
    
    # If we installed to /opt, update the desktop file
    if [ "$INSTALL_LOCATION_CHOICE" = "1" ]; then
        echo -e "${YELLOW}Updating desktop shortcut for new location...${NC}"
        mkdir -p ~/.local/share/applications
        cat > ~/.local/share/applications/odoo-dev-tools.desktop << EOF
[Desktop Entry]
Name=Odoo Developer Tools
Comment=Tools for Odoo development and server management
Exec=$APP_DIR/app.py
Icon=utilities-terminal
Terminal=false
Type=Application
Categories=Development;Utility;
EOF
        chmod +x ~/.local/share/applications/odoo-dev-tools.desktop
        echo -e "${GREEN}Desktop shortcut updated.${NC}"
    fi
    
    # Reload systemd, enable and start the service
    echo -e "${YELLOW}Enabling and starting the service...${NC}"
    sudo systemctl daemon-reload
    sudo systemctl enable odoo-developer-tools.service
    sudo systemctl start odoo-developer-tools.service
    
    # Check if service started successfully
    if sudo systemctl is-active --quiet odoo-developer-tools.service; then
        echo -e "${GREEN}Service has been started successfully.${NC}"
        echo -e "${GREEN}The application will now start automatically on system boot.${NC}"
        
        if [ "$INSTALL_LOCATION_CHOICE" = "1" ]; then
            echo -e "${GREEN}Application has been installed to: $APP_DIR${NC}"
        fi
        
        echo -e "${YELLOW}Access the application at: http://localhost:5000${NC}"
        return 0
    else
        echo -e "${RED}Failed to start the service. Check the logs with: sudo journalctl -u odoo-developer-tools.service${NC}"
        return 1
    fi
}

# Install dependencies based on distribution
install_dependencies() {
    local distro=$(detect_distro)
    echo -e "${YELLOW}Detected Linux distribution: $distro${NC}"
    
    case "$distro" in
        "ubuntu"|"debian"|"pop"|"mint"|"elementary")
            echo -e "${YELLOW}Installing dependencies with apt...${NC}"
            sudo apt-get update
            sudo apt-get install -y python3-pip python3-pyqt5 libpq-dev python3-dev
            ;;
        "fedora")
            echo -e "${YELLOW}Installing dependencies with dnf...${NC}"
            sudo dnf install -y python3-pip python3-qt5 postgresql-devel python3-devel
            ;;
        "centos"|"rhel"|"rocky"|"almalinux")
            echo -e "${YELLOW}Installing dependencies with yum...${NC}"
            sudo yum install -y python3-pip python3-qt5 postgresql-devel python3-devel
            ;;
        "arch"|"manjaro")
            echo -e "${YELLOW}Installing dependencies with pacman...${NC}"
            sudo pacman -S --noconfirm python-pip python-pyqt5 postgresql-libs
            ;;
        "opensuse"|"suse")
            echo -e "${YELLOW}Installing dependencies with zypper...${NC}"
            sudo zypper install -y python3-pip python3-qt5 postgresql-devel python3-devel
            ;;
        *)
            echo -e "${RED}Could not determine your distribution.${NC}"
            echo -e "${YELLOW}Please make sure you have the following packages installed:${NC}"
            echo "  - python3-pip"
            echo "  - PyQt5"
            echo "  - libpq-dev (for psycopg2)"
            ;;
    esac
}

# Check requirements
echo -e "${BLUE}Checking requirements...${NC}"
check_python_version || { echo -e "${RED}Python 3.6+ is required.${NC}"; exit 1; }
check_command python3 || { echo -e "${RED}Python 3 is required.${NC}"; exit 1; }
check_command pip3 || echo -e "${YELLOW}pip3 not found, will try to install it.${NC}"
check_command psql || echo -e "${YELLOW}PostgreSQL client not found, will try to install it.${NC}"
check_command ssh || echo -e "${YELLOW}SSH client not found, will try to install it.${NC}"

# Install dependencies if needed
echo
echo -e "${BLUE}Installing system dependencies...${NC}"
install_dependencies

# Install Python packages
echo
echo -e "${BLUE}Installing Python packages...${NC}"
pip3 install -r "$SCRIPT_DIR/requirements.txt"

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to install Python packages. Please check the error message above.${NC}"
    exit 1
fi

# Make the main script executable
echo
echo -e "${BLUE}Making the main script executable...${NC}"
chmod +x "$SCRIPT_DIR/main.py"

# Create desktop entry
echo
echo -e "${BLUE}Creating desktop shortcut...${NC}"
mkdir -p ~/.local/share/applications
cat > ~/.local/share/applications/odoo-dev-tools.desktop << EOF
[Desktop Entry]
Name=Odoo Developer Tools
Comment=Tools for Odoo development and server management
Exec=$SCRIPT_DIR/main.py
Icon=utilities-terminal
Terminal=false
Type=Application
Categories=Development;Utility;
EOF

echo -e "${GREEN}Desktop shortcut created.${NC}"

# Create necessary directories
echo
echo -e "${BLUE}Creating necessary directories...${NC}"
mkdir -p ~/.ssh/config.d
mkdir -p ~/.local/share/Odoo/filestore

# Update the SSH config
echo -e "${BLUE}Updating SSH configuration...${NC}"
SSH_CONFIG="$HOME/.ssh/config"

# Create the SSH config file if it doesn't exist
if [ ! -f "$SSH_CONFIG" ]; then
    mkdir -p "$HOME/.ssh"
    touch "$SSH_CONFIG"
    chmod 600 "$SSH_CONFIG"
    echo -e "${GREEN}Created SSH config file.${NC}"
fi

# Check if the Include line is already in the config
if ! grep -q "Include $HOME/.ssh/config.d/\*.conf" "$SSH_CONFIG"; then
    echo -e "\nInclude $HOME/.ssh/config.d/*.conf" >> "$SSH_CONFIG"
    echo -e "${GREEN}Updated SSH config to include config.d directory.${NC}"
else
    echo -e "${GREEN}SSH config already includes config.d directory.${NC}"
fi

# Ask if the user wants to set up a system service for auto-start
echo
echo -e "${BLUE}Do you want to set up the application to start automatically at system boot?${NC}"
echo -e "This will require sudo privileges to create a systemd service."
echo -e "1. Yes - set up as a system service (recommended for server installations)"
echo -e "2. No - I'll start it manually when needed (default)"
read -p "Enter your choice [2]: " SERVICE_CHOICE

# Default to no if no selection is made
SERVICE_CHOICE=${SERVICE_CHOICE:-2}

if [ "$SERVICE_CHOICE" = "1" ]; then
    setup_systemd_service
    SERVICE_SETUP_RESULT=$?
fi

# All done
echo
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}     Installation Complete!          ${NC}"
echo -e "${GREEN}=====================================${NC}"
echo

if [ "$SERVICE_CHOICE" = "1" ] && [ $SERVICE_SETUP_RESULT -eq 0 ]; then
    echo -e "You can access the Odoo Developer Tools UI:"
    echo -e "  1. By opening a web browser and navigating to ${BLUE}http://localhost:5000${NC}"
    echo -e "  2. The service will start automatically when your system boots"
    echo -e "  3. To control the service: ${YELLOW}sudo systemctl [start|stop|restart|status] odoo-developer-tools.service${NC}"
else
    echo -e "You can run the Odoo Developer Tools UI:"
    echo -e "  1. From your desktop applications menu"
    echo -e "  2. By running ${BLUE}$SCRIPT_DIR/main.py${NC}"
fi

echo
echo -e "Enjoy using Odoo Developer Tools UI!"

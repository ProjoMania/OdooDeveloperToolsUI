# Odoo Developer Tools UI

A desktop application to simplify Odoo development and server management tasks on Linux systems.

## Features

- **Modern UI**
  - Elegant black and orange color scheme
  - Responsive design for various screen sizes
  - Consistent and intuitive interface throughout the application
  - Enhanced user experience with improved form controls and visual feedback

- **Remote Server Management**
  - Add Remote server configurations
  - List all configured Remote servers with details
  - Connect to Remote servers with a simple interface
  - Dedicated deletion page with confirmation to prevent accidental removal

- **Odoo Database Management**
  - List all local Odoo databases with details
  - Show database size, filestore size, and Odoo version
  - Drop databases and their filestores with proper confirmation
  - Restore databases from backup files
  - Extend Odoo Enterprise license expiration dates

- **Project Management**
  - Create and manage development projects
  - Track project status and progress
  - Link projects to Remote servers and databases
  - Dedicated deletion page with confirmation for safe removal

- **Task Management**
  - Create tasks within projects
  - Track task status and progress
  - Add notes and details to tasks
  - Dedicated deletion page for tasks

## Recent Updates

### Application Lifecycle Management (May 2025)
- Added full application lifecycle management:
  - Enhanced installation script with system-wide `/opt` installation option
  - Added systemd service support for automatic startup on boot
  - New update script that preserves instance data while updating code
  - New uninstall script for safe and complete application removal
- Improved deployment flexibility for various use cases:
  - Desktop usage with manual startup
  - Server deployment with automatic service management

### UI Improvements (May 2025)
- Implemented a modern black and orange color scheme throughout the application
- Enhanced form controls and improved visual feedback
- Fixed modal backdrop issues that caused screen dimming to persist

### Deletion Workflow Enhancements (May 2025)
- Replaced modal-based deletion with dedicated deletion pages for all components:
  - SSH Server deletion pages with clear warnings and confirmations
  - Project deletion pages that show associated data to be removed
  - Task deletion pages with notes and metadata details
- Improved error handling and user feedback during deletion processes
- Unified deletion workflow across the application for consistent user experience

## Installation

### Prerequisites

- Python 3.6+
- PostgreSQL client
- SSH client
- PyQt5
- psycopg2

### Automatic Installation

The easiest way to install is to use the provided installation script:

```bash
./install.sh
```

This script will:
1. Check for required dependencies
2. Install required Python packages
3. Create necessary directories
4. Create a desktop shortcut

### Manual Installation

If you prefer to install manually:

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Make the main.py executable:
   ```bash
   chmod +x main.py
   ```

3. Create a desktop shortcut:
   ```bash
   mkdir -p ~/.local/share/applications
   echo "[Desktop Entry]
   Name=Odoo Developer Tools
   Comment=Tools for Odoo development and server management
   Exec=$(pwd)/main.py
   Icon=utilities-terminal
   Terminal=false
   Type=Application
   Categories=Development;Utility;" > ~/.local/share/applications/odoo-dev-tools.desktop
   ```

### Install as a System Service (Autostart on Boot)

To make the application start automatically at system boot, you can set it up as a systemd service:

1. Create a systemd service file:
   ```bash
   sudo nano /etc/systemd/system/odoo-developer-tools.service
   ```

2. Add the following content (adjust paths as needed):
   ```
   [Unit]
   Description=Odoo Developer Tools UI
   After=network.target postgresql.service

   [Service]
   Type=simple
   User=YOUR_USERNAME
   WorkingDirectory=/path/to/OdooDeveloperToolsUI
   ExecStart=/usr/bin/python3 /path/to/OdooDeveloperToolsUI/app.py
   Restart=on-failure
   RestartSec=5
   StandardOutput=syslog
   StandardError=syslog
   SyslogIdentifier=odoo-dev-tools

   [Install]
   WantedBy=multi-user.target
   ```

3. Enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable odoo-developer-tools.service
   sudo systemctl start odoo-developer-tools.service
   ```

4. Check service status:
   ```bash
   sudo systemctl status odoo-developer-tools.service
   ```

> **Note:** The service runs the Flask application in the background. You can access it by opening a web browser and navigating to `http://localhost:5000`

### Updating the Application

To update to the latest version while preserving your data, use the provided update script:

```bash
./update.sh
```

The update script will:
1. Detect whether you're using a standard or system-wide (`/opt`) installation
2. Create a backup of your current installation
3. Clone the latest code from the repository
4. Update all application files while preserving your instance data
5. Restart the service if it was running

### Uninstalling the Application

If you need to remove the application, use the uninstallation script for a clean removal:

```bash
./uninstall.sh
```

The uninstall script will:
1. Stop and remove the systemd service if it was installed
2. Offer to back up your instance data (configurations, databases) 
3. Remove all application files and desktop shortcuts
4. Provide a clean uninstallation with proper cleanup

## Usage

### Starting the Application

You can start the application:

1. From the desktop menu (under Development or Utilities categories)
2. By running `./main.py` from the project directory

### Remote Server Management

- **Add Remote Server**: Create a new Remote server configuration with host, IP/domain, user, port, and key file.
- **Connect to Remote Server**: Select a server and connect to it through a terminal emulator.
- **List Remote Servers**: View all configured Remote servers with their details.

### Odoo Database Management

- **List Databases**: View all local Odoo databases with sizes and versions.
- **Drop Database**: Delete a database and its filestore.
- **Restore Database**: Restore a database from a backup zip file with options to:
  - Deactivate cron jobs
  - Deactivate mail servers
  - Reset admin credentials
- **Extend Enterprise License**: Extend Odoo Enterprise license expiration dates by 20 days.

## Requirements

- A Linux distribution (Ubuntu, Debian, Fedora, CentOS, etc.)
- Python 3.6 or higher
- PostgreSQL client
- SSH client
- Terminal emulator (gnome-terminal, konsole, etc.)

## License

This project is open-source software licensed under the MIT license.

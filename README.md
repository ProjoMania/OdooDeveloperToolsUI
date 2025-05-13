# Odoo Developer Tools UI

A desktop application to simplify Odoo development and server management tasks on Linux systems.

## Features

- **SSH Server Management**
  - Add SSH server configurations
  - List all configured SSH servers
  - Connect to SSH servers with a simple interface

- **Odoo Database Management**
  - List all local Odoo databases with details
  - Show database size, filestore size, and Odoo version
  - Drop databases and their filestores
  - Restore databases from backup files
  - Extend Odoo Enterprise license expiration dates

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

## Usage

### Starting the Application

You can start the application:

1. From the desktop menu (under Development or Utilities categories)
2. By running `./main.py` from the project directory

### SSH Server Management

- **Add SSH Server**: Create a new SSH server configuration with host, IP/domain, user, port, and key file.
- **Connect to SSH Server**: Select a server and connect to it through a terminal emulator.
- **List SSH Servers**: View all configured SSH servers with their details.

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

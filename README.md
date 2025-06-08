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

1. Clone the repository:
```bash
git clone https://github.com/yourusername/OdooDevTools.git
cd OdooDevTools
```

2. Run the installation script:
```bash
./install.sh
```

The installation script will:
- Install all required dependencies
- Set up SSH configuration
- Create a systemd service for auto-start
- Create a desktop shortcut
- Create an update script

## Updating

To update the application to the latest version:

1. Navigate to the cloned repository
2. Run the update script:
```bash
./update.sh
```

The update script will:
- Pull the latest changes from git
- Update Python packages
- Restart the service

## Service Management

The application runs as a systemd service. You can control it using:

```bash
# Start the service
sudo systemctl start odoo-developer-tools.service

# Stop the service
sudo systemctl stop odoo-developer-tools.service

# Restart the service
sudo systemctl restart odoo-developer-tools.service

# Check service status
sudo systemctl status odoo-developer-tools.service

# View service logs
sudo journalctl -u odoo-developer-tools.service
```

## Accessing the Application

After installation, you can access the application at:
- Web Interface: http://127.0.0.1:5000
- Desktop Application: Search for "Odoo Developer Tools" in your applications menu

## Troubleshooting

If you encounter SSH connection issues:
1. Run the SSH fix script:
```bash
./fix_ssh.sh
```

2. Check the service logs:
```bash
sudo journalctl -u odoo-developer-tools.service
```

## Development

The application is installed as a symlink from `/opt/odoo-developer-tools` to your cloned repository. This allows you to:
- Keep the repository for updates
- Make local changes for testing
- Pull updates from the remote repository

## License

This project is open-source software licensed under the MIT license.

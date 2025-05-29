#!/usr/bin/env python3
import paramiko
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class OdooInstallConfig:
    """Configuration for Odoo installation"""
    version: str
    user: str = 'odoo'
    port: int = 8069
    install_nginx: bool = False
    is_enterprise: bool = False
    admin_password: str = 'admin'

class OdooInstaller:
    """Handles remote installation of Odoo"""
    
    def __init__(self, host: str, username: str, password: Optional[str] = None, key_filename: Optional[str] = None):
        """Initialize the installer with SSH connection details"""
        self.host = host
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.client = None
        
    def connect(self) -> bool:
        """Establish SSH connection to the server"""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if self.key_filename:
                self.client.connect(
                    hostname=self.host,
                    username=self.username,
                    key_filename=self.key_filename
                )
            else:
                self.client.connect(
                    hostname=self.host,
                    username=self.username,
                    password=self.password
                )
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {self.host}: {str(e)}")
            return False
            
    def disconnect(self):
        """Close SSH connection"""
        if self.client:
            self.client.close()
            self.client = None
            
    def execute_command(self, command: str) -> tuple[bool, str]:
        """Execute a command on the remote server"""
        if not self.client:
            if not self.connect():
                return False, "Failed to connect to server"
                
        try:
            stdin, stdout, stderr = self.client.exec_command(command)
            exit_status = stdout.channel.recv_exit_status()
            
            if exit_status == 0:
                return True, stdout.read().decode()
            else:
                return False, stderr.read().decode()
        except Exception as e:
            return False, str(e)
            
    def install_odoo(self, config: OdooInstallConfig) -> bool:
        """Install Odoo on the remote server"""
        try:
            # Connect to the server
            if not self.connect():
                return False
                
            # Update system packages
            success, output = self.execute_command("sudo apt-get update && sudo apt-get upgrade -y")
            if not success:
                logger.error(f"Failed to update system: {output}")
                return False
                
            # Install required packages
            packages = [
                "python3-pip",
                "python3-dev",
                "python3-venv",
                "python3-wheel",
                "libxml2-dev",
                "libpq-dev",
                "libjpeg8-dev",
                "liblcms2-dev",
                "libxslt1-dev",
                "zlib1g-dev",
                "libsasl2-dev",
                "libldap2-dev",
                "build-essential",
                "git",
                "libssl-dev",
                "libffi-dev",
                "libmysqlclient-dev",
                "default-libmysqlclient-dev",
                "pkg-config",
                "libfreetype6-dev"
            ]
            
            if config.install_nginx:
                packages.extend(["nginx", "certbot", "python3-certbot-nginx"])
                
            success, output = self.execute_command(f"sudo apt-get install -y {' '.join(packages)}")
            if not success:
                logger.error(f"Failed to install required packages: {output}")
                return False
                
            # Create Odoo user if it doesn't exist
            success, output = self.execute_command(f"id -u {config.user} &>/dev/null || sudo useradd -m -s /bin/bash {config.user}")
            if not success:
                logger.error(f"Failed to create Odoo user: {output}")
                return False
                
            # Create Odoo directory
            success, output = self.execute_command(f"sudo mkdir -p /opt/odoo && sudo chown {config.user}:{config.user} /opt/odoo")
            if not success:
                logger.error(f"Failed to create Odoo directory: {output}")
                return False
                
            # Clone Odoo repository
            repo_url = "https://github.com/odoo/odoo.git"
            success, output = self.execute_command(f"sudo -u {config.user} git clone --depth 1 --branch {config.version} {repo_url} /opt/odoo/odoo")
            if not success:
                logger.error(f"Failed to clone Odoo repository: {output}")
                return False
                
            # Create virtual environment
            success, output = self.execute_command(f"sudo -u {config.user} python3 -m venv /opt/odoo/venv")
            if not success:
                logger.error(f"Failed to create virtual environment: {output}")
                return False
                
            # Install Python dependencies
            success, output = self.execute_command(
                f"sudo -u {config.user} /opt/odoo/venv/bin/pip3 install -r /opt/odoo/odoo/requirements.txt"
            )
            if not success:
                logger.error(f"Failed to install Python dependencies: {output}")
                return False
                
            # Create Odoo configuration file
            config_content = f"""[options]
admin_passwd = {config.admin_password}
db_host = False
db_port = False
db_user = {config.user}
db_password = False
addons_path = /opt/odoo/odoo/addons
http_port = {config.port}
"""
            success, output = self.execute_command(f"echo '{config_content}' | sudo tee /etc/odoo.conf")
            if not success:
                logger.error(f"Failed to create Odoo configuration: {output}")
                return False
                
            # Create systemd service file
            service_content = f"""[Unit]
Description=Odoo Open Source ERP and CRM
After=network.target

[Service]
Type=simple
User={config.user}
Group={config.user}
ExecStart=/opt/odoo/venv/bin/python3 /opt/odoo/odoo/odoo-bin -c /etc/odoo.conf
Restart=always

[Install]
WantedBy=multi-user.target
"""
            success, output = self.execute_command(f"echo '{service_content}' | sudo tee /etc/systemd/system/odoo.service")
            if not success:
                logger.error(f"Failed to create systemd service: {output}")
                return False
                
            # Reload systemd and start Odoo
            success, output = self.execute_command("sudo systemctl daemon-reload && sudo systemctl enable odoo && sudo systemctl start odoo")
            if not success:
                logger.error(f"Failed to start Odoo service: {output}")
                return False
                
            # Install Nginx if requested
            if config.install_nginx:
                nginx_config = f"""server {{
    listen 80;
    server_name _;

    location / {{
        proxy_pass http://127.0.0.1:{config.port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}
"""
                success, output = self.execute_command(f"echo '{nginx_config}' | sudo tee /etc/nginx/sites-available/odoo")
                if not success:
                    logger.error(f"Failed to create Nginx configuration: {output}")
                    return False
                    
                success, output = self.execute_command("sudo ln -sf /etc/nginx/sites-available/odoo /etc/nginx/sites-enabled/ && sudo nginx -t && sudo systemctl restart nginx")
                if not success:
                    logger.error(f"Failed to configure Nginx: {output}")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Error during Odoo installation: {str(e)}")
            return False
        finally:
            self.disconnect() 
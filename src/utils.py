"""
Utility functions for Odoo Developer Tools UI
"""

import os
import psycopg2
import paramiko
import logging
import re
from typing import Dict, List, Optional, Tuple, Any
from flask import current_app, flash
from .models import Setting

logger = logging.getLogger(__name__)

def get_setting(key: str, default: Any = None) -> Any:
    """
    Get a setting value from the database
    
    Args:
        key: Setting key
        default: Default value if setting not found
    
    Returns:
        Setting value or default
    """
    try:
        setting = Setting.query.filter_by(key=key).first()
        return setting.value if setting else default
    except Exception as e:
        logger.error(f"Error getting setting {key}: {str(e)}")
        return default

def get_db_connection_params() -> Dict[str, str]:
    """
    Get PostgreSQL connection parameters from settings
    
    Returns:
        Dictionary with connection parameters
    """
    return {
        'user': get_setting('postgres_user', 'postgres'),
        'password': get_setting('postgres_password', ''),
        'host': get_setting('postgres_host', '127.0.0.1'),
        'port': get_setting('postgres_port', '5432')
    }

def get_db_connection() -> Optional[psycopg2.extensions.connection]:
    """
    Create a connection to PostgreSQL using settings from the database
    
    Returns:
        PostgreSQL connection or None if failed
    """
    try:
        conn_params = get_db_connection_params()
        
        logger.info(f"Attempting to connect to PostgreSQL at {conn_params['host']}:{conn_params['port']} as user {conn_params['user']}")
        
        # Build connection string based on whether password is provided
        if conn_params['password']:
            conn = psycopg2.connect(
                dbname="postgres",
                user=conn_params['user'],
                password=conn_params['password'],
                host=conn_params['host'],
                port=conn_params['port']
            )
        else:
            # Use peer authentication (no password)
            conn = psycopg2.connect(
                dbname="postgres",
                user=conn_params['user'],
                host=conn_params['host'],
                port=conn_params['port']
            )
            
        conn.autocommit = True
        logger.info("Successfully connected to PostgreSQL")
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        flash(f'Could not connect to PostgreSQL: {str(e)}', 'danger')
        return None

def format_size(size_bytes: int) -> str:
    """
    Format size in bytes to human-readable format
    
    Args:
        size_bytes: Size in bytes
    
    Returns:
        Formatted size string
    """
    if size_bytes > 1073741824:  # 1 GB
        return f"{size_bytes / 1073741824:.2f} GB"
    elif size_bytes > 1048576:  # 1 MB
        return f"{size_bytes / 1048576:.2f} MB"
    elif size_bytes > 1024:  # 1 KB
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes} bytes"

def get_dir_size(path: str) -> int:
    """
    Get the size of a directory in bytes
    
    Args:
        path: Directory path
    
    Returns:
        Total size in bytes
    """
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(file_path)
                except (FileNotFoundError, PermissionError):
                    pass
    except (FileNotFoundError, PermissionError):
        logger.warning(f"Cannot access directory: {path}")
    
    return total_size

def get_ssh_servers() -> List[Dict[str, str]]:
    """
    Get list of SSH servers from config files
    
    Returns:
        List of server configurations
    """
    ssh_config_dir = current_app.config['SSH_CONFIG_DIR']
    
    if not os.path.exists(ssh_config_dir):
        return []
        
    # List all .conf files in the SSH config directory
    config_files = [f for f in os.listdir(ssh_config_dir) if f.endswith('.conf')]
    
    servers = []
    for conf_file in config_files:
        file_path = os.path.join(ssh_config_dir, conf_file)
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                
            # Parse the SSH config file
            server_config = parse_ssh_config(content)
            if server_config:
                servers.append(server_config)
        except Exception as e:
            logger.error(f"Error reading SSH config file {file_path}: {str(e)}")
    
    return servers

def parse_ssh_config(content: str) -> Optional[Dict[str, str]]:
    """
    Parse SSH config content and extract server information
    
    Args:
        content: SSH config file content
    
    Returns:
        Server configuration dictionary or None if invalid
    """
    host = None
    hostname = None
    user = None
    port = "22"  # Default
    key_file = None
    password = None
    
    for line in content.splitlines():
        line = line.strip()
        if line.startswith('Host '):
            host = line.split(' ', 1)[1].strip()
        elif line.startswith('HostName '):
            hostname = line.split(' ', 1)[1].strip()
        elif line.startswith('User '):
            user = line.split(' ', 1)[1].strip()
        elif line.startswith('Port '):
            port = line.split(' ', 1)[1].strip()
        elif line.startswith('IdentityFile '):
            key_file = line.split(' ', 1)[1].strip()
        elif line.startswith('# Password:'):
            # Extract password from comment line
            password = line.split(':', 1)[1].strip()
    
    if host and hostname:
        return {
            'host': host,
            'hostname': hostname,
            'user': user or "",
            'port': port,
            'key_file': key_file or "",
            'password': password or ""
        }
    
    return None

def update_main_ssh_config() -> None:
    """Ensure the main SSH config includes the config.d directory"""
    ssh_config_file = os.path.expanduser("~/.ssh/config")
    
    # Create the main config file if it doesn't exist
    if not os.path.exists(ssh_config_file):
        os.makedirs(os.path.dirname(ssh_config_file), exist_ok=True)
        with open(ssh_config_file, 'w') as f:
            f.write(f"Include ~/.ssh/config.d/*.conf\n")
        return
    
    # Check if the Include line already exists
    include_line = f"Include ~/.ssh/config.d/*.conf"
    try:
        with open(ssh_config_file, 'r') as f:
            if include_line in f.read():
                return
    except Exception as e:
        logger.error(f"Error reading SSH config file: {str(e)}")
        return
        
    # Append the Include line
    try:
        with open(ssh_config_file, 'a') as f:
            f.write(f"\n{include_line}\n")
    except Exception as e:
        logger.error(f"Error updating SSH config file: {str(e)}")

def get_ssh_config(host: str) -> Optional[Dict[str, str]]:
    """
    Get SSH configuration for a specific host
    
    Args:
        host: Host name
    
    Returns:
        SSH configuration dictionary or None if not found
    """
    servers = get_ssh_servers()
    for server in servers:
        if server['host'] == host:
            return server
    return None

def create_ssh_client(host: str) -> Optional[paramiko.SSHClient]:
    """
    Create SSH client for a host
    
    Args:
        host: Host name
    
    Returns:
        SSH client or None if connection failed
    """
    try:
        server_config = get_ssh_config(host)
        if not server_config:
            logger.error(f"SSH configuration not found for host: {host}")
            return None
        
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connection parameters
        connect_kwargs = {
            'hostname': server_config['hostname'],
            'port': int(server_config['port']),
            'username': server_config['user'],
            'timeout': current_app.config.get('SSH_TIMEOUT', 30)
        }
        
        # Add authentication method
        if server_config['key_file'] and os.path.exists(server_config['key_file']):
            connect_kwargs['key_filename'] = server_config['key_file']
        elif server_config['password']:
            connect_kwargs['password'] = server_config['password']
        
        client.connect(**connect_kwargs)
        return client
        
    except Exception as e:
        logger.error(f"Error creating SSH client for {host}: {str(e)}")
        return None

def check_sshpass_available() -> bool:
    """
    Check if sshpass is available on the system
    
    Returns:
        True if sshpass is available
    """
    try:
        import subprocess
        result = subprocess.run(['which', 'sshpass'], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False

def get_portal_user_status() -> Dict[str, Any]:
    """
    Get portal user status for templates
    
    Returns:
        User status dictionary
    """
    # For local development, always return premium status
    # In production, this would check actual user authentication
    return {
        'is_premium': True, 
        'username': 'local-dev', 
        'email': 'local@example.com'
    }

def validate_file_extension(filename: str) -> bool:
    """
    Validate file extension against allowed extensions
    
    Args:
        filename: File name to validate
    
    Returns:
        True if extension is allowed
    """
    if '.' not in filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in current_app.config.get('ALLOWED_EXTENSIONS', set())

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage
    
    Args:
        filename: Original filename
    
    Returns:
        Sanitized filename
    """
    # Remove or replace potentially dangerous characters
    filename = re.sub(r'[^\w\-_\.]', '_', filename)
    # Ensure it doesn't start with a dot or dash
    filename = filename.lstrip('.-')
    return filename 
"""
SSH Server Management Blueprint
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app
from flask_login import login_required
import os
import logging
from typing import Optional
from .utils import (
    get_ssh_servers, 
    get_ssh_config, 
    update_main_ssh_config, 
    create_ssh_client,
    check_sshpass_available,
    sanitize_filename
)
from .models import db

ssh_bp = Blueprint('ssh', __name__, url_prefix='/ssh')
logger = logging.getLogger(__name__)

@ssh_bp.route('/')
@ssh_bp.route('/servers')
def ssh_servers():
    """Display list of SSH servers"""
    servers = get_ssh_servers()
    return render_template('ssh_servers.html', servers=servers)

@ssh_bp.route('/add')
def add_ssh_server():
    """Display form to add SSH server"""
    return render_template('add_ssh_server.html')

@ssh_bp.route('/add', methods=['POST'])
def add_ssh_server_post():
    """Handle SSH server addition"""
    try:
        host = request.form.get('host', '').strip()
        hostname = request.form.get('hostname', '').strip()
        user = request.form.get('user', '').strip()
        port = request.form.get('port', '22').strip()
        key_file = request.form.get('key_file', '').strip()
        password = request.form.get('password', '').strip()
        
        # Validation
        if not host or not hostname:
            flash('Host and Hostname are required', 'danger')
            return redirect(url_for('ssh.add_ssh_server'))
        
        if not user:
            flash('Username is required', 'danger')
            return redirect(url_for('ssh.add_ssh_server'))
        
        # Sanitize host name for filename
        safe_host = sanitize_filename(host)
        if not safe_host:
            flash('Invalid host name', 'danger')
            return redirect(url_for('ssh.add_ssh_server'))
        
        # Create SSH config content
        config_content = f"Host {host}\n"
        config_content += f"    HostName {hostname}\n"
        config_content += f"    User {user}\n"
        config_content += f"    Port {port}\n"
        
        if key_file:
            config_content += f"    IdentityFile {key_file}\n"
        
        if password:
            config_content += f"    # Password: {password}\n"
        
        # Write config file
        config_file = os.path.join(current_app.config['SSH_CONFIG_DIR'], f"{safe_host}.conf")
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        # Update main SSH config
        update_main_ssh_config()
        
        flash(f'SSH server "{host}" added successfully', 'success')
        return redirect(url_for('ssh.ssh_servers'))
        
    except Exception as e:
        logger.error(f"Error adding SSH server: {str(e)}")
        flash(f'Error adding SSH server: {str(e)}', 'danger')
        return redirect(url_for('ssh.add_ssh_server'))

@ssh_bp.route('/connect/<host>', methods=['GET', 'POST'])
def connect_ssh(host):
    """Connect to SSH server"""
    server_config = get_ssh_config(host)
    if not server_config:
        flash(f'SSH configuration not found for host: {host}', 'danger')
        return redirect(url_for('ssh.ssh_servers'))
    
    # Generate SSH command
    command_parts = ['ssh']
    
    if server_config.get('port', '22') != '22':
        command_parts.extend(['-p', server_config['port']])
    
    if server_config.get('key_file'):
        command_parts.extend(['-i', server_config['key_file']])
    
    command_parts.append(f"{server_config['user']}@{server_config['hostname']}")
    
    command = ' '.join(command_parts)
    
    return render_template('ssh_connect.html', host=host, server=server_config, command=command)

@ssh_bp.route('/terminal/<host>')
def ssh_terminal_page(host):
    """SSH terminal page"""
    server_config = get_ssh_config(host)
    if not server_config:
        flash(f'SSH configuration not found for host: {host}', 'danger')
        return redirect(url_for('ssh.ssh_servers'))
    
    sshpass_available = check_sshpass_available()
    return render_template('ssh_terminal.html', 
                         host=host, 
                         server=server_config,
                         sshpass_available=sshpass_available)

@ssh_bp.route('/delete/<host>')
def delete_ssh_server(host):
    """Display SSH server deletion confirmation"""
    server_config = get_ssh_config(host)
    if not server_config:
        flash(f'SSH configuration not found for host: {host}', 'danger')
        return redirect(url_for('ssh.ssh_servers'))
    
    return render_template('delete_ssh_server.html', host=host, server=server_config)

@ssh_bp.route('/delete/<host>', methods=['POST'])
def delete_ssh_server_post(host):
    """Handle SSH server deletion"""
    try:
        safe_host = sanitize_filename(host)
        config_file = os.path.join(current_app.config['SSH_CONFIG_DIR'], f"{safe_host}.conf")
        
        if os.path.exists(config_file):
            os.remove(config_file)
            flash(f'SSH server "{host}" deleted successfully', 'success')
        else:
            flash(f'SSH configuration file not found for host: {host}', 'warning')
        
        return redirect(url_for('ssh.ssh_servers'))
        
    except Exception as e:
        logger.error(f"Error deleting SSH server {host}: {str(e)}")
        flash(f'Error deleting SSH server: {str(e)}', 'danger')
        return redirect(url_for('ssh.ssh_servers'))

@ssh_bp.route('/details/<host>')
def ssh_server_details(host):
    """Display SSH server details"""
    server_config = get_ssh_config(host)
    if not server_config:
        flash(f'SSH configuration not found for host: {host}', 'danger')
        return redirect(url_for('ssh.ssh_servers'))
    
    return render_template('ssh_server_details.html', host=host, server=server_config)

@ssh_bp.route('/edit/<host>')
def edit_ssh_server(host):
    """Display SSH server edit form"""
    server_config = get_ssh_config(host)
    if not server_config:
        flash(f'SSH configuration not found for host: {host}', 'danger')
        return redirect(url_for('ssh.ssh_servers'))
    
    return render_template('ssh_edit.html', host=host, server=server_config)

@ssh_bp.route('/edit/<host>', methods=['POST'])
def edit_ssh_server_post(host):
    """Handle SSH server editing"""
    try:
        hostname = request.form.get('hostname', '').strip()
        user = request.form.get('user', '').strip()
        port = request.form.get('port', '22').strip()
        key_file = request.form.get('key_file', '').strip()
        password = request.form.get('password', '').strip()
        
        # Validation
        if not hostname:
            flash('Hostname is required', 'danger')
            return redirect(url_for('ssh.edit_ssh_server', host=host))
        
        if not user:
            flash('Username is required', 'danger')
            return redirect(url_for('ssh.edit_ssh_server', host=host))
        
        # Get existing config
        server_config = get_ssh_config(host)
        if not server_config:
            flash(f'SSH configuration not found for host: {host}', 'danger')
            return redirect(url_for('ssh.ssh_servers'))
        
        # Create updated SSH config content
        config_content = f"Host {host}\n"
        config_content += f"    HostName {hostname}\n"
        config_content += f"    User {user}\n"
        config_content += f"    Port {port}\n"
        
        if key_file:
            config_content += f"    IdentityFile {key_file}\n"
        
        if password:
            config_content += f"    # Password: {password}\n"
        
        # Write updated config file
        safe_host = sanitize_filename(host)
        config_file = os.path.join(current_app.config['SSH_CONFIG_DIR'], f"{safe_host}.conf")
        
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        flash(f'SSH server "{host}" updated successfully', 'success')
        return redirect(url_for('ssh.ssh_servers'))
        
    except Exception as e:
        logger.error(f"Error updating SSH server {host}: {str(e)}")
        flash(f'Error updating SSH server: {str(e)}', 'danger')
        return redirect(url_for('ssh.edit_ssh_server', host=host))

@ssh_bp.route('/generate_command/<host>')
def generate_ssh_command(host):
    """Generate SSH command for a host"""
    try:
        server_config = get_ssh_config(host)
        if not server_config:
            return jsonify({'error': 'SSH configuration not found'}), 404
        
        # Build SSH command
        command_parts = ['ssh']
        
        if server_config['port'] != '22':
            command_parts.extend(['-p', server_config['port']])
        
        if server_config['key_file']:
            command_parts.extend(['-i', server_config['key_file']])
        
        command_parts.append(f"{server_config['user']}@{server_config['hostname']}")
        
        command = ' '.join(command_parts)
        
        return jsonify({'command': command})
        
    except Exception as e:
        logger.error(f"Error generating SSH command for {host}: {str(e)}")
        return jsonify({'error': str(e)}), 500 
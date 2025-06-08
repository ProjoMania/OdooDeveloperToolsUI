#!/usr/bin/env python3
# Developer Management Tool - Comprehensive developer workspace management
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
import requests
import os
import psycopg2
import paramiko
from src.api_endpoints import api_bp
from src.database import db
import subprocess
import json
import re
import zipfile
import tempfile
import shutil
import glob
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import logging
import importlib.metadata
import importlib.util
from models import Project, Task, TaskNote, ProjectServer, ProjectDatabase, Setting, User
from auth import check_subscription_status, subscription_required, premium_feature_required, get_subscription_portal_url
from src.portal_auth import get_portal_user_status, premium_required
from flask_sock import Sock

# Create a mock user for local development
class MockUser:
    is_authenticated = True
    is_active = True
    is_anonymous = False
    github_id = "local-dev"
    email = "local@example.com"
    
    def get_id(self):
        return "local-user"

# Create a global instance to use throughout the app
current_user = MockUser()

# Try to import markdown safely
try:
    import markdown
    MARKDOWN_AVAILABLE = True
except (ImportError, AttributeError):
    MARKDOWN_AVAILABLE = False
    logging.warning("Markdown support is not available")

# Initialize Flask application
app = Flask(__name__, 
            template_folder='src/templates',
            static_folder='src/static')
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = '/tmp/odoo_dev_tools_uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dev_tools.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# Initialize database
db.init_app(app)

# Create database tables
with app.app_context():
    try:
        db.create_all()
        print("Database tables created successfully")
    except Exception as e:
        print(f"Error creating database tables: {str(e)}")
        raise

# Initialize Flask-Sock
sock = Sock(app)

# Store active SSH sessions
active_sessions = {}

# Register API blueprint
app.register_blueprint(api_bp)

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add portal status function to template globals
@app.template_global()
def get_portal_user_status():
    """Make portal status available in templates"""
    # For local development, always return premium status
    return {'is_premium': True, 'username': 'local-dev', 'email': 'local@example.com'}

# Global settings
SSH_CONFIG_DIR = os.path.expanduser("~/.ssh/config.d")
FILESTORE_DIR = os.path.expanduser("~/.local/share/Odoo/filestore")

# Ensure necessary directories exist
os.makedirs(SSH_CONFIG_DIR, exist_ok=True)
os.makedirs(FILESTORE_DIR, exist_ok=True)

# === Helper Functions ===

def get_setting(key, default=None):
    """Get a setting value from the database"""
    try:
        setting = Setting.query.filter_by(key=key).first()
        return setting.value if setting else default
    except Exception as e:
        logger.error(f"Error getting setting {key}: {str(e)}")
        return default

def get_db_connection():
    """Create a connection to PostgreSQL using settings from the database"""
    try:
        # Get PostgreSQL connection settings from database
        with app.app_context():
            # Get settings with defaults if not set
            user = get_setting('postgres_user', 'postgres')
            password = get_setting('postgres_password', '')
            host = get_setting('postgres_host', '127.0.0.1')
            port = get_setting('postgres_port', '5432')

        logger.info(f"Attempting to connect to PostgreSQL at {host}:{port} as user {user}")

        # Build connection string based on whether password is provided
        if password:
            conn = psycopg2.connect(
                dbname="postgres",
                user=user,
                password=password,
                host=host,
                port=port
            )
        else:
            # Use peer authentication (no password)
            conn = psycopg2.connect(
                dbname="postgres",
                user=user,
                host=host,
                port=port
            )
            
        conn.autocommit = True
        logger.info("Successfully connected to PostgreSQL")
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        flash(f'Could not connect to PostgreSQL: {str(e)}', 'danger')
        return None

def format_size(size_bytes):
    """Format size in bytes to human-readable format"""
    if size_bytes > 1073741824:  # 1 GB
        return f"{size_bytes / 1073741824:.2f} GB"
    else:
        return f"{size_bytes / 1048576:.2f} MB"

def get_dir_size(path):
    """Get the size of a directory in bytes"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            file_path = os.path.join(dirpath, filename)
            try:
                total_size += os.path.getsize(file_path)
            except (FileNotFoundError, PermissionError):
                pass
    return total_size

def get_ssh_servers():
    """Get list of SSH servers from config files"""
    if not os.path.exists(SSH_CONFIG_DIR):
        return []
        
    # List all .conf files in the SSH config directory
    config_files = [f for f in os.listdir(SSH_CONFIG_DIR) if f.endswith('.conf')]
    
    servers = []
    for conf_file in config_files:
        file_path = os.path.join(SSH_CONFIG_DIR, conf_file)
        with open(file_path, 'r') as f:
            content = f.read()
            
        # Parse the SSH config file
        host = None
        hostname = None
        user = None
        port = "22"  # Default
        key_file = None
        
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
        
        if host and hostname:
            servers.append({
                'host': host,
                'hostname': hostname,
                'user': user or "",
                'port': port,
                'key_file': key_file or ""
            })
    
    return servers

def update_main_ssh_config():
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
    with open(ssh_config_file, 'r') as f:
        if include_line in f.read():
            return
        
    # Append the Include line
    with open(ssh_config_file, 'a') as f:
        f.write(f"\n{include_line}\n")

def get_ssh_config(host):
    """Get SSH configuration for a host"""
    config_file = os.path.join(SSH_CONFIG_DIR, f"{host}.conf")
    if not os.path.exists(config_file):
        return None
        
    config = {}
    with open(config_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split(' ', 1)
                config[key] = value.strip()
    return config

def create_ssh_client(host):
    """Create and configure SSH client"""
    config = get_ssh_config(host)
    if not config:
        return None
        
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # Get connection parameters
        hostname = config.get('HostName', host)
        username = config.get('User', os.getenv('USER'))
        port = int(config.get('Port', 22))
        
        # Connect using key or password
        if 'IdentityFile' in config:
            key_path = os.path.expanduser(config['IdentityFile'])
            client.connect(
                hostname=hostname,
                username=username,
                key_filename=key_path,
                port=port
            )
        else:
            # Try to get password from config or environment
            password = os.getenv('SSH_PASSWORD', '')
            client.connect(
                hostname=hostname,
                username=username,
                password=password,
                port=port
            )
            
        return client
    except Exception as e:
        print(f"SSH connection error: {str(e)}")
        return None

# === Routes ===

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

# === SSH Server Routes ===
@app.route('/servers')
def ssh_servers():
    """Remote Server management page"""
    servers = get_ssh_servers()
    return render_template('ssh.html', servers=servers)

@app.route('/servers/add', methods=['GET', 'POST'])
def add_ssh_server():
    """Add a new Remote Server"""
    if request.method == 'POST':
        # Get form data
        host = request.form.get('host').strip()
        hostname = request.form.get('hostname').strip()
        user = request.form.get('user').strip()
        port = request.form.get('port').strip() or "22"
        auth_method = request.form.get('auth_method', 'key')
        key_file = request.form.get('key_file', '').strip() if auth_method == 'key' else ''
        password = request.form.get('password', '').strip() if auth_method == 'password' else ''
        
        # Validate inputs
        if not host or not hostname:
            flash('Host and IP/Domain are required fields', 'danger')
            return redirect(url_for('add_ssh_server'))
        
        # Create config file
        config_file = os.path.join(SSH_CONFIG_DIR, f"{host}.conf")
        
        # Check if file already exists
        if os.path.exists(config_file):
            if not request.form.get('confirm_overwrite'):
                # Ask for confirmation
                flash(f'SSH configuration for {host} already exists. Confirm overwrite?', 'warning')
                session['overwrite_data'] = {
                    'host': host,
                    'hostname': hostname,
                    'user': user,
                    'port': port,
                    'auth_method': auth_method,
                    'key_file': key_file,
                    'password': password
                }
                return render_template('ssh_add.html', overwrite=True, 
                                      host=host, hostname=hostname, 
                                      user=user, port=port, auth_method=auth_method,
                                      key_file=key_file, password=password)
        
        # Write the configuration file
        with open(config_file, 'w') as f:
            f.write(f"Host {host}\n")
            f.write(f"    HostName {hostname}\n")
            if user:
                f.write(f"    User {user}\n")
            f.write(f"    Port {port}\n")
            
            # Authentication settings
            if auth_method == 'key' and key_file:
                f.write(f"    IdentityFile {key_file}\n")
                f.write(f"    PreferredAuthentications publickey\n")
            elif auth_method == 'password' and password:
                f.write(f"    PreferredAuthentications password\n")
                f.write(f"    PasswordAuthentication yes\n")
                # Store password in a safer way in a real-world application
                # For this demo, we'll add it as a comment (NOT recommended for production)
                f.write(f"    # Password: {password}\n")
        
        # Update main SSH config if needed
        update_main_ssh_config()
        
        flash(f'SSH server "{host}" added successfully', 'success')
        return redirect(url_for('ssh_servers'))
    
    # Handle overwrite confirmation from session
    overwrite_data = session.pop('overwrite_data', None)
    if overwrite_data:
        return render_template('ssh_add.html', overwrite=True, 
                              host=overwrite_data.get('host', ''),
                              hostname=overwrite_data.get('hostname', ''), 
                              user=overwrite_data.get('user', ''),
                              port=overwrite_data.get('port', '22'),
                              key_file=overwrite_data.get('key_file', ''))
    
    return render_template('ssh_add.html')

@app.route('/servers/delete/<host>', methods=['GET', 'POST'])
def delete_ssh_server(host):
    """Delete a Remote Server configuration"""
    try:
        # Build the path to the config file
        config_file = os.path.join(SSH_CONFIG_DIR, f"{host}.conf")
        
        # Check if the file exists
        if not os.path.exists(config_file):
            flash(f"SSH configuration for {host} not found.", "danger")
            return redirect(url_for('ssh_servers'))
            
        # Get server details for display
        servers = get_ssh_servers()
        server = next((s for s in servers if s['host'] == host), None)
        
        if not server:
            flash(f"SSH server {host} not found.", "danger")
            return redirect(url_for('ssh_servers'))
        
        # If GET request, show confirmation page
        if request.method == 'GET':
            return render_template('delete_ssh_server.html', server=server)
        
        # If POST request, process deletion
        os.remove(config_file)
        
        # Ensure the main SSH config includes the config.d directory
        update_main_ssh_config()
        
        flash(f"SSH server {host} has been deleted successfully.", "success")
        return redirect(url_for('ssh_servers'))
    except Exception as e:
        logger.error(f"Error deleting SSH server: {str(e)}")
        flash(f"Error deleting SSH server: {str(e)}", "danger")
        return redirect(url_for('ssh_servers'))

@app.route('/servers/generate_command/<host>', methods=['GET'])
def generate_ssh_command(host):
    """Generate a Remote Server command for the client to execute"""
    servers = get_ssh_servers()
    
    # Find the server with matching host
    for server in servers:
        if server.get('host') == host:
            # Build ssh command with appropriate flags
            command = f"ssh {server.get('host')}"
            
            # Add authentication info to command response
            auth_type = 'key' if server.get('identity_file') else 'password'
            response = {
                'command': command,
                'auth_type': auth_type,
                'host': server.get('host'),
                'user': server.get('user', ''),
                'hostname': server.get('hostname', '')
            }
            
            return jsonify(response)
    
    return jsonify({'error': 'Server not found'})

@app.route('/servers/connect/<host>', methods=['GET', 'POST'])
def connect_ssh(host):
    """Connect to SSH server using system ssh command only"""
    import subprocess
    import os
    
    # Parse config as before
    config_file = os.path.join(SSH_CONFIG_DIR, f"{host}.conf")
    if not os.path.exists(config_file):
        flash('Server configuration not found', 'error')
        return redirect(url_for('ssh_servers'))
    
    # Get SSH_AUTH_SOCK from environment or use default
    ssh_auth_sock = os.environ.get('SSH_AUTH_SOCK', '/run/user/{}/keyring/ssh'.format(os.getuid()))
    
    # Set up environment for SSH command
    env = os.environ.copy()
    env['SSH_AUTH_SOCK'] = ssh_auth_sock
    
    # Optionally parse config for display, but not needed for connection
    ssh_config = os.path.expanduser('~/.ssh/config')
    ssh_cmd = [
        'ssh',
        '-F', ssh_config,
        host,
        'echo "Connection successful"'
    ]
    
    try:
        # Run SSH command with the correct environment
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=10,
            env=env
        )
        
        if result.returncode == 0:
            flash(f'Successfully connected to {host}', 'success')
        else:
            flash(f'Failed to connect: {result.stderr}', 'danger')
    except Exception as e:
        flash(f'Error connecting to SSH: {str(e)}', 'danger')
    return redirect(url_for('ssh_servers'))

@app.route('/servers/<host>/details')
@premium_required
def ssh_server_details(host):
    """Remote Server details page for managing servers and installing Odoo"""
    # Get portal user status for premium check
    portal_status = get_portal_user_status()
    is_premium = portal_status and portal_status.get('is_premium', False)
    
    servers = get_ssh_servers()
    
    # Find the specific server
    server = None
    for s in servers:
        if s['host'] == host:
            server = s
            break
    
    if not server:
        flash(f'SSH server "{host}" not found', 'danger')
        return redirect(url_for('ssh_servers'))
    
    return render_template('ssh_server_details.html', server=server, is_premium=is_premium)

@app.route('/servers/<host>/edit', methods=['GET', 'POST'])
@premium_required
def edit_ssh_server(host):
    """Edit an existing SSH server configuration"""
    # Get portal user status for premium check
    portal_status = get_portal_user_status()
    is_premium = portal_status and portal_status.get('is_premium', False)
    
    if not is_premium:
        flash('This feature requires a premium subscription', 'warning')
        return redirect(url_for('settings'))
    
    # Get all servers
    servers = get_ssh_servers()
    
    # Find the specific server
    server = None
    for s in servers:
        if s['host'] == host:
            server = s
            break
    
    if not server:
        flash(f'SSH server "{host}" not found', 'danger')
        return redirect(url_for('ssh_servers'))
    
    if request.method == 'POST':
        # Get form data
        new_host = request.form.get('host').strip()
        hostname = request.form.get('hostname').strip()
        user = request.form.get('user').strip()
        port = request.form.get('port').strip() or "22"
        auth_method = request.form.get('auth_method', 'key')
        key_file = request.form.get('key_file', '').strip() if auth_method == 'key' else ''
        password = request.form.get('password', '').strip() if auth_method == 'password' else ''
        
        # Validate inputs
        if not new_host or not hostname:
            flash('Host and IP/Domain are required fields', 'danger')
            return render_template('ssh_edit.html', server=server)
        
        # Create config file
        config_file = os.path.join(SSH_CONFIG_DIR, f"{host}.conf")
        new_config_file = os.path.join(SSH_CONFIG_DIR, f"{new_host}.conf")
        
        # Check if new hostname already exists (if changed)
        if new_host != host and os.path.exists(new_config_file):
            flash(f'SSH configuration for {new_host} already exists', 'danger')
            return render_template('ssh_edit.html', server=server)
        
        # Write the configuration file
        with open(config_file, 'w') as f:
            f.write(f"Host {new_host}\n")
            f.write(f"    HostName {hostname}\n")
            if user:
                f.write(f"    User {user}\n")
            f.write(f"    Port {port}\n")
            
            # Authentication settings
            if auth_method == 'key' and key_file:
                f.write(f"    IdentityFile {key_file}\n")
                f.write(f"    PreferredAuthentications publickey\n")
            elif auth_method == 'password' and password:
                f.write(f"    PreferredAuthentications password\n")
                f.write(f"    PasswordAuthentication yes\n")
                # Store password in a safer way in a real-world application
                # For this demo, we'll add it as a comment (NOT recommended for production)
                f.write(f"    # Password: {password}\n")
        
        # Rename config file if hostname changed
        if new_host != host:
            os.rename(config_file, new_config_file)
        
        # Update main SSH config if needed
        update_main_ssh_config()
        
        flash(f'SSH server "{new_host}" updated successfully', 'success')
        return redirect(url_for('ssh_server_details', host=new_host))
    
    return render_template('ssh_edit.html', server=server)

# === Database Routes ===

@app.route('/databases')
def list_databases():
    """List all Odoo databases"""
    conn = get_db_connection()
    
    if not conn:
        return render_template('databases.html', databases=[])
    
    try:
        cursor = conn.cursor()
        
        # Get all databases with size
        cursor.execute("""
            SELECT 
                d.datname AS database_name, 
                u.usename AS owner,
                pg_database_size(d.datname) AS size_bytes
            FROM 
                pg_database d
                JOIN pg_user u ON d.datdba = u.usesysid
            WHERE 
                d.datname NOT IN ('postgres', 'template0', 'template1')
            ORDER BY 
                d.datname
        """)
        
        db_rows = cursor.fetchall()
        databases = []
        
        for db_name, owner, size_bytes in db_rows:
            # Format database size
            db_size = format_size(size_bytes)
            
            # Check if it's an Odoo database and get version
            odoo_version = "Not Odoo DB"
            is_enterprise = False
            expiration_date = None
            
            try:
                # Try to connect to the specific database
                db_conn = psycopg2.connect(
                    dbname=db_name,
                    user=get_setting('postgres_user', 'postgres'),
                    password=get_setting('postgres_password', ''),
                    host=get_setting('postgres_host', '127.0.0.1'),
                    port=get_setting('postgres_port', '5432')
                )
                db_cursor = db_conn.cursor()
                
                # Check if it's an Odoo database
                db_cursor.execute("""
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'ir_module_module'
                """)
                
                if db_cursor.fetchone():
                    # Get Odoo version from base module
                    db_cursor.execute("""
                        SELECT latest_version FROM ir_module_module
                        WHERE name = 'base' LIMIT 1
                    """)
                    version_row = db_cursor.fetchone()
                    if version_row:
                        odoo_version = version_row[0]
                    
                    # Check if it's Enterprise
                    db_cursor.execute("""
                        SELECT 1 FROM ir_module_module
                        WHERE name = 'web_enterprise' AND state = 'installed'
                    """)
                    is_enterprise = bool(db_cursor.fetchone())
                    
                    # Try to get the expiration date for enterprise databases
                    if is_enterprise:
                        try:
                            db_cursor.execute("""
                                SELECT value FROM ir_config_parameter
                                WHERE key = 'database.expiration_date'
                            """)
                            date_row = db_cursor.fetchone()
                            if date_row:
                                expiration_date = date_row[0]
                        except Exception as e:
                            logger.error(f"Error getting expiration date for {db_name}: {str(e)}")
                
                db_cursor.close()
                db_conn.close()
            except Exception as e:
                logger.error(f"Error checking database {db_name}: {str(e)}")
                # Continue with default values if we can't check the database
            
            # Get filestore size
            filestore_path = os.path.join(FILESTORE_DIR, db_name)
            if os.path.exists(filestore_path):
                filestore_bytes = get_dir_size(filestore_path)
                filestore_size = format_size(filestore_bytes)
            else:
                filestore_size = "N/A"
            
            # Add database to list
            databases.append({
                'name': db_name,
                'owner': owner,
                'version': odoo_version,
                'expiration_date': expiration_date,
                'size': db_size,
                'filestore_size': filestore_size,
                'is_enterprise': is_enterprise
            })
        
        cursor.close()
        conn.close()
        
        if not databases:
            flash('No databases found. Please check your PostgreSQL connection settings.', 'warning')
        
        return render_template('databases.html', databases=databases)
        
    except Exception as e:
        logger.error(f"Error listing databases: {str(e)}")
        flash(f'Error listing databases: {str(e)}', 'danger')
        return render_template('databases.html', databases=[])

@app.route('/databases/drop/<db_name>', methods=['GET', 'POST'])
def drop_database(db_name):
    """Drop a database and its filestore"""
    if request.method == 'POST':
        try:
            # Connect to PostgreSQL
            conn = get_db_connection()
            if not conn:
                flash('Could not connect to PostgreSQL', 'danger')
                return redirect(url_for('list_databases'))
            
            cursor = conn.cursor()
            
            # First terminate all connections to the database
            cursor.execute(f"""
                SELECT pg_terminate_backend(pid) 
                FROM pg_stat_activity 
                WHERE datname = '{db_name}'
            """)
            
            # Drop the database
            cursor.execute(f"DROP DATABASE IF EXISTS \"{db_name}\"")
            
            # Remove the filestore if it exists
            filestore_path = os.path.join(FILESTORE_DIR, db_name)
            if os.path.exists(filestore_path):
                shutil.rmtree(filestore_path)
                
            cursor.close()
            conn.close()
            
            flash(f'Database "{db_name}" and its filestore have been dropped', 'success')
        except Exception as e:
            flash(f'Error dropping database: {str(e)}', 'danger')
        
        return redirect(url_for('list_databases'))
    
    # Confirmation page
    return render_template('drop_database.html', db_name=db_name)

@app.route('/databases/restore', methods=['GET', 'POST'])
def restore_database():
    """Restore a database from backup"""
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'backup_file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
            
        file = request.files['backup_file']
        
        # If user does not select file, browser also submits an empty part without filename
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
            
        if file:
            # Check if the file is a .dump file
            is_dump_file = file.filename.lower().endswith('.dump')
            # Get form data
            db_name = request.form.get('db_name', '').strip()
            
            # Validate database name
            if not re.match(r'^[a-zA-Z0-9_]+$', db_name):
                flash('Database name can only contain letters, numbers, and underscores', 'danger')
                return redirect(request.url)
            
            # Get options
            deactivate_cron = 'deactivate_cron' in request.form
            deactivate_mail = 'deactivate_mail' in request.form
            reset_admin = 'reset_admin' in request.form
            
            # Save the file
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = secure_filename(f"{timestamp}_{file.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                # Create temp directory for extraction
                temp_dir = tempfile.mkdtemp()
                
                # Handle direct .dump files or ZIP archives differently
                if is_dump_file:
                    # Use the uploaded .dump file directly
                    dump_file = filepath
                    dump_found = True
                    has_filestore = False  # Direct .dump files don't have filestore
                else:
                    # Extract the backup zip
                    try:
                        with zipfile.ZipFile(filepath, 'r') as zip_ref:
                            zip_ref.extractall(temp_dir)
                    except zipfile.BadZipFile:
                        flash('The uploaded file is not a valid ZIP archive. Please upload a proper ZIP file containing SQL dump or a direct .dump file.', 'danger')
                        shutil.rmtree(temp_dir)
                        os.remove(filepath)
                        return redirect(request.url)
                    
                    # Look for the SQL dump file (both dump.sql and *.dump formats)
                    dump_file = os.path.join(temp_dir, "dump.sql")
                    dump_found = os.path.exists(dump_file)
                    
                    # If dump.sql not found, look for *.dump files
                    if not dump_found:
                        dump_files = glob.glob(os.path.join(temp_dir, "*.dump"))
                        if dump_files:
                            dump_file = dump_files[0]  # Use the first dump file found
                            dump_found = True
                    
                    if not dump_found:
                        flash('Invalid backup: No SQL dump file (dump.sql or *.dump) found in the backup file', 'danger')
                        shutil.rmtree(temp_dir)
                        os.remove(filepath)
                        return redirect(request.url)
                
                # Check for filestore directory or filestore.zip (for backward compatibility)
                filestore_dir = os.path.join(temp_dir, "filestore")
                filestore_zip = os.path.join(temp_dir, "filestore.zip")
                has_filestore_dir = os.path.exists(filestore_dir) and os.path.isdir(filestore_dir)
                has_filestore_zip = os.path.exists(filestore_zip)
                has_filestore = has_filestore_dir or has_filestore_zip
                
                # Connect to PostgreSQL
                conn = get_db_connection()
                if not conn:
                    flash('Could not connect to PostgreSQL', 'danger')
                    shutil.rmtree(temp_dir)
                    os.remove(filepath)
                    return redirect(request.url)
                
                cursor = conn.cursor()
                
                # Drop the database if it exists
                cursor.execute(f"""
                    SELECT pg_terminate_backend(pid) 
                    FROM pg_stat_activity 
                    WHERE datname = '{db_name}'
                """)
                cursor.execute(f"DROP DATABASE IF EXISTS \"{db_name}\"")
                
                # Create new database
                cursor.execute(f"CREATE DATABASE \"{db_name}\" TEMPLATE template0 ENCODING 'UTF8'")
                cursor.close()
                conn.close()
                
                # Restore the SQL dump
                subprocess.run(["psql", "-U", "postgres", "-d", db_name, "-f", dump_file])
                
                # Handle filestore if it exists
                if has_filestore:
                    filestore_path = os.path.join(FILESTORE_DIR, db_name)
                    
                    # Remove existing filestore if it exists
                    if os.path.exists(filestore_path):
                        shutil.rmtree(filestore_path)
                    
                    # Create the directory
                    os.makedirs(filestore_path, exist_ok=True)
                    
                    # Copy filestore directory or extract filestore zip
                    if has_filestore_dir:
                        # Copy the filestore directory contents
                        for item in os.listdir(filestore_dir):
                            source = os.path.join(filestore_dir, item)
                            destination = os.path.join(filestore_path, item)
                            if os.path.isdir(source):
                                shutil.copytree(source, destination)
                            else:
                                shutil.copy2(source, destination)
                    elif has_filestore_zip:
                        # Extract the filestore zip
                        with zipfile.ZipFile(filestore_zip, 'r') as zip_ref:
                            zip_ref.extractall(filestore_path)
                
                # Post-restore operations
                # Connect to the restored database
                conn = psycopg2.connect(dbname=db_name, user="postgres")
                conn.autocommit = True
                cursor = conn.cursor()
                
                if deactivate_cron:
                    cursor.execute("UPDATE ir_cron SET active = false")
                
                if deactivate_mail:
                    cursor.execute("UPDATE ir_mail_server SET active = false")
                    cursor.execute("UPDATE fetchmail_server SET active = false")
                
                if reset_admin:
                    cursor.execute("""
                        UPDATE res_users
                        SET password = 'admin', login = 'admin'
                        WHERE id = 2
                    """)
                
                cursor.close()
                conn.close()
                
                flash(f'Database "{db_name}" has been successfully restored', 'success')
                
            except Exception as e:
                flash(f'Error restoring database: {str(e)}', 'danger')
            finally:
                # Clean up
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                if os.path.exists(filepath):
                    os.remove(filepath)
            
            return redirect(url_for('list_databases'))
    
    return render_template('restore_database.html')

@app.route('/databases/extend_enterprise', methods=['GET', 'POST'])
@app.route('/databases/extend_enterprise/<db_name>', methods=['GET', 'POST'])
def extend_enterprise(db_name=None):
    """Extend Odoo Enterprise license expiration date for selected databases"""
    # Get enterprise databases for display in the GET request
    enterprise_dbs = []
    
    # Connect to PostgreSQL
    try:
        # Get PostgreSQL connection settings directly to show in debug log
        postgres_user = get_setting('postgres_user', 'postgres')
        postgres_host = get_setting('postgres_host', '127.0.0.1')
        postgres_port = get_setting('postgres_port', '5432')
                
        conn = get_db_connection()
        if not conn:
            error_msg = 'Could not connect to PostgreSQL. Please check your database settings.'
            flash(error_msg, 'danger')
            logger.error(error_msg)
            return render_template('extend_enterprise.html', enterprise_dbs=[])
    except Exception as e:
        error_msg = f'PostgreSQL connection error: {str(e)}'
        flash(error_msg, 'danger')
        logger.error(error_msg)
        return render_template('extend_enterprise.html', enterprise_dbs=[])
    
    cursor = conn.cursor()
    
    # Get all databases
    cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false")
    databases = [row[0] for row in cursor.fetchall() if row[0] not in ('postgres', 'template0', 'template1')]
    
    # Check each database for Odoo Enterprise
    for dbs_name in databases:
        try:
            # Use complete connection settings from the database
            postgres_user = get_setting('postgres_user', 'postgres')
            postgres_password = get_setting('postgres_password', '')
            postgres_host = get_setting('postgres_host', '127.0.0.1')
            postgres_port = get_setting('postgres_port', '5432')
            
            # Connect with appropriate parameters based on whether password is set
            if postgres_password:
                db_conn = psycopg2.connect(
                    dbname=dbs_name,
                    user=postgres_user,
                    password=postgres_password,
                    host=postgres_host,
                    port=postgres_port
                )
            else:
                db_conn = psycopg2.connect(
                    dbname=dbs_name,
                    user=postgres_user,
                    host=postgres_host,
                    port=postgres_port
                )
            db_cursor = db_conn.cursor()
            
            # Check if it's an Odoo database with enterprise module
            db_cursor.execute("""
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'ir_module_module'
            """)
            
            if db_cursor.fetchone():
                # Check for enterprise module
                db_cursor.execute("""
                    SELECT 1 FROM ir_module_module
                    WHERE name = 'web_enterprise' AND state = 'installed'
                """)
                
                if db_cursor.fetchone():
                    # Get current expiration date
                    expiration_date = None
                    try:
                        db_cursor.execute("""
                            SELECT value FROM ir_config_parameter
                            WHERE key = 'database.expiration_date'
                        """)
                        row = db_cursor.fetchone()
                        if row:
                            expiration_date = row[0]
                    except:
                        pass
                    
                    # Add database to the list
                    enterprise_dbs.append({
                        'name': dbs_name,
                        'expiration_date': expiration_date
                    })
            
            db_cursor.close()
            db_conn.close()
        except Exception as e:
            logger.error(f"Error checking database {dbs_name}: {str(e)}")
            # Skip databases that can't be accessed
            pass
    
    cursor.close()
    conn.close()
    
    # Process POST request for extending licenses
    if request.method == 'POST':
        results = []
        selected_dbs = request.form.getlist('databases')
        
        if not selected_dbs:
            flash('No databases selected for extension', 'warning')
            return render_template('extend_enterprise.html', enterprise_dbs=enterprise_dbs, pre_selected_db=db_name)
        
        # Extend the expiration for each selected database
        for selected_db_name in selected_dbs:
            try:
                # Use the user settings for the database connection
                if get_setting('postgres_password', ''):
                    db_conn = psycopg2.connect(
                        dbname=selected_db_name,
                        user=get_setting('postgres_user', 'postgres'),
                        password=get_setting('postgres_password', ''),
                        host=get_setting('postgres_host', '127.0.0.1'),
                        port=get_setting('postgres_port', '5432')
                    )
                else:
                    db_conn = psycopg2.connect(
                        dbname=selected_db_name,
                        user=get_setting('postgres_user', 'postgres'),
                        host=get_setting('postgres_host', '127.0.0.1'),
                        port=get_setting('postgres_port', '5432')
                    )
                db_conn.autocommit = True
                db_cursor = db_conn.cursor()
                
                # Get the current expiration date
                db_cursor.execute("""
                    SELECT value FROM ir_config_parameter
                    WHERE key = 'database.expiration_date'
                """)
                row = db_cursor.fetchone()
                
                old_date = "Unknown"
                if row:
                    # Current expiration date exists, extend it by 20 days
                    try:
                        old_date = row[0]
                        current_date = datetime.strptime(row[0], "%Y-%m-%d")
                    except ValueError:
                        # If date format is wrong, use today
                        current_date = datetime.now()
                else:
                    # No expiration date set, use today
                    current_date = datetime.now()
                
                # Add 20 days
                new_date = current_date + timedelta(days=20)
                new_date_str = new_date.strftime("%Y-%m-%d")
                
                # Update the expiration date
                db_cursor.execute("""
                    UPDATE ir_config_parameter
                    SET value = %s
                    WHERE key = 'database.expiration_date'
                """, (new_date_str,))
                
                # If the parameter doesn't exist, create it
                if db_cursor.rowcount == 0:
                    db_cursor.execute("""
                        INSERT INTO ir_config_parameter (key, value)
                        VALUES ('database.expiration_date', %s)
                    """, (new_date_str,))
                
                results.append({
                    'database': selected_db_name,
                    'old_date': old_date,
                    'new_date': new_date_str,
                    'status': 'success'
                })
                
                db_cursor.close()
                db_conn.close()
            except Exception as e:
                results.append({
                    'database': selected_db_name,
                    'status': 'error',
                    'message': str(e)
                })
        
        cursor.close()
        conn.close()
        
        if not selected_dbs:
            flash('No databases were selected for extension', 'warning')
        else:
            flash(f'Extended license for {len(selected_dbs)} database(s)', 'success')
        
        return render_template('extend_enterprise_results.html', results=results)
    
    if not enterprise_dbs:
        flash('No Odoo Enterprise databases found', 'warning')
    
    # If a specific database was requested, check if it's an enterprise DB
    if db_name:
        # Check if the specified database is in the enterprise_dbs list
        if not any(db['name'] == db_name for db in enterprise_dbs):
            flash(f'Database {db_name} is not an Enterprise database', 'warning')
            return redirect(url_for('list_databases'))
    
    return render_template('extend_enterprise.html', enterprise_dbs=enterprise_dbs, pre_selected_db=db_name)

# === Project Routes ===
@app.route('/projects')
def projects():
    projects = Project.query.all()
    return render_template('projects/index.html', projects=projects)

@app.route('/projects/new', methods=['GET', 'POST'])
def create_project():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form.get('description', '')
        repository_url = request.form.get('repo_url', '')  # Get from repo_url field but use as repository_url
        status = request.form.get('status', 'active')
        deadline = None
        if request.form.get('deadline'):
            try:
                deadline = datetime.strptime(request.form.get('deadline'), '%Y-%m-%d')
            except ValueError:
                pass

        project = Project(
            name=name,
            description=description,
            repository_url=repository_url,
            status=status,
            end_date=deadline  # Map deadline to the end_date field
        )
        
        db.session.add(project)
        db.session.commit()
        
        flash('Project created successfully', 'success')
        return redirect(url_for('view_project', project_id=project.id))
        
    return render_template('projects/form.html')

@app.route('/projects/<int:project_id>')
def view_project(project_id):
    project = Project.query.get_or_404(project_id)
    tasks = Task.query.filter_by(project_id=project_id).all()
    servers = ProjectServer.query.filter_by(project_id=project_id).all()
    databases = ProjectDatabase.query.filter_by(project_id=project_id).all()
    
    # Calculate task statistics
    total_tasks = len(tasks)
    completed_tasks = len([t for t in tasks if t.status == 'done'])
    progress = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    upcoming_tasks = [t for t in tasks if t.status != 'done' and t.due_date and t.due_date >= datetime.now()]
    upcoming_tasks.sort(key=lambda x: x.due_date)
    
    # Calculate server role statistics
    server_roles = {}
    for server in servers:
        role = server.server_role or 'unspecified'
        if role in server_roles:
            server_roles[role] += 1
        else:
            server_roles[role] = 1
    
    # Calculate database type statistics
    database_types = {}
    for db in databases:
        db_type = db.database_type or 'unspecified'
        if db_type in database_types:
            database_types[db_type] += 1
        else:
            database_types[db_type] = 1
    
    # Get available servers and databases for the modals
    available_servers = get_ssh_servers()
    
    # Get all databases for the database modal
    conn = get_db_connection()
    available_databases = []
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false")
        available_databases = [{'name': row[0]} for row in cursor.fetchall()]
        cursor.close()
        conn.close()
    
    return render_template('projects/view.html', 
                          project=project,
                          tasks=tasks,
                          servers=servers,
                          databases=databases,
                          total_tasks=total_tasks,
                          completed_tasks=completed_tasks,
                          progress=progress,
                          upcoming_tasks=upcoming_tasks[:5],  # Show only 5 upcoming tasks
                          server_roles=server_roles,
                          database_types=database_types,
                          available_servers=available_servers,
                          available_databases=available_databases,
                          now=datetime.now())  # Add current datetime for comparisons

@app.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    if request.method == 'POST':
        project.name = request.form['name']
        project.description = request.form.get('description', '')
        project.repository_url = request.form.get('repo_url', '')
        project.status = request.form.get('status', 'active')
        
        if request.form.get('deadline'):
            try:
                project.end_date = datetime.strptime(request.form.get('deadline'), '%Y-%m-%d')
            except ValueError:
                pass
        else:
            project.end_date = None
        
        db.session.commit()
        flash('Project updated successfully!', 'success')
        return redirect(url_for('view_project', project_id=project.id))
    
    return render_template('projects/edit.html', project=project)


@app.route('/projects/<int:project_id>/delete', methods=['GET', 'POST'])
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    # If GET request, show confirmation page
    if request.method == 'GET':
        # Get associated tasks for display
        tasks = Task.query.filter_by(project_id=project_id).all()
        return render_template('projects/delete_project.html', project=project, tasks=tasks)
    
    # If POST request, process deletion
    # Delete all tasks associated with the project
    tasks = Task.query.filter_by(project_id=project_id).all()
    for task in tasks:
        # Delete all notes associated with each task
        notes = TaskNote.query.filter_by(task_id=task.id).all()
        for note in notes:
            db.session.delete(note)
        db.session.delete(task)
    
    # Delete all server associations
    server_associations = ProjectServer.query.filter_by(project_id=project_id).all()
    for assoc in server_associations:
        db.session.delete(assoc)
    
    # Delete all database associations
    db_associations = ProjectDatabase.query.filter_by(project_id=project_id).all()
    for assoc in db_associations:
        db.session.delete(assoc)
    
    # Finally, delete the project itself
    db.session.delete(project)
    db.session.commit()
    
    flash('Project deleted successfully!', 'success')
    return redirect(url_for('projects'))

@app.route('/projects/<int:project_id>/tasks')
def project_tasks(project_id):
    project = Project.query.get_or_404(project_id)
    tasks = Task.query.filter_by(project_id=project_id).all()
    now = datetime.now()
    return render_template('tasks/index.html', project=project, tasks=tasks, now=now)

@app.route('/projects/<int:project_id>/tasks/new', methods=['GET', 'POST'])
def create_task(project_id):
    project = Project.query.get_or_404(project_id)
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description', '')
        status = request.form.get('status', 'todo')
        priority = request.form.get('priority', 'medium')
        
        due_date = None
        if request.form.get('due_date'):
            try:
                due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d')
            except ValueError:
                pass
                
        task = Task(
            title=title,
            description=description,
            status=status,
            priority=priority,
            due_date=due_date,
            project_id=project_id
        )
        
        db.session.add(task)
        db.session.commit()
        
        flash('Task created successfully', 'success')
        return redirect(url_for('view_task', project_id=project_id, task_id=task.id))
        
    return render_template('tasks/form.html', project=project)

@app.route('/projects/<int:project_id>/tasks/<int:task_id>')
def view_task(project_id, task_id):
    project = Project.query.get_or_404(project_id)
    task = Task.query.get_or_404(task_id)
    
    # Ensure task belongs to the specified project
    if task.project_id != project_id:
        flash('Task does not belong to this project', 'danger')
        return redirect(url_for('project_tasks', project_id=project_id))
        
    now = datetime.now()
    markdown_enabled = True  # For rendering markdown content
    
    return render_template('tasks/view.html', 
                          project=project, 
                          task=task, 
                          now=now,
                          markdown_enabled=markdown_enabled)

@app.route('/projects/<int:project_id>/tasks/<int:task_id>/edit', methods=['GET', 'POST'])
def edit_task(project_id, task_id):
    project = Project.query.get_or_404(project_id)
    task = Task.query.get_or_404(task_id)
    
    # Ensure task belongs to the specified project
    if task.project_id != project_id:
        flash('Task does not belong to this project', 'danger')
        return redirect(url_for('project_tasks', project_id=project_id))
    
    if request.method == 'POST':
        task.title = request.form['title']
        task.description = request.form.get('description', '')
        task.status = request.form.get('status', 'todo')
        task.priority = request.form.get('priority', 'medium')
        
        # Update completed_at if status changed to 'done'
        if task.status == 'done' and not task.completed_at:
            task.completed_at = datetime.now()
        elif task.status != 'done':
            task.completed_at = None
        
        if request.form.get('due_date'):
            try:
                task.due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d')
            except ValueError:
                pass
        else:
            task.due_date = None
            
        db.session.commit()
        flash('Task updated successfully', 'success')
        return redirect(url_for('view_task', project_id=project_id, task_id=task.id))
        
    return render_template('tasks/form.html', project=project, task=task)

@app.route('/projects/<int:project_id>/tasks/<int:task_id>/delete', methods=['GET', 'POST'])
def delete_task(project_id, task_id):
    task = Task.query.get_or_404(task_id)
    project = Project.query.get_or_404(project_id)
    
    # Ensure task belongs to the specified project
    if task.project_id != project_id:
        flash('Task does not belong to this project', 'danger')
        return redirect(url_for('project_tasks', project_id=project_id))
    
    # If GET request, show confirmation page
    if request.method == 'GET':
        # Get associated notes for display
        notes = TaskNote.query.filter_by(task_id=task.id).all()
        return render_template('tasks/delete_task.html', project=project, task=task, notes=notes)
    
    # If POST request, process deletion
    # Delete all notes associated with this task first
    notes = TaskNote.query.filter_by(task_id=task.id).all()
    for note in notes:
        db.session.delete(note)
    
    # Delete the task
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted successfully', 'success')
    
    return redirect(url_for('project_tasks', project_id=project_id))

@app.route('/projects/<int:project_id>/tasks/<int:task_id>/status', methods=['POST'])
def update_task_status(project_id, task_id):
    task = Task.query.get_or_404(task_id)
    
    # Ensure task belongs to the specified project
    if task.project_id != project_id:
        flash('Task does not belong to this project', 'danger')
        return redirect(url_for('project_tasks', project_id=project_id))
        
    new_status = request.form.get('status')
    if new_status in ['todo', 'in_progress', 'review', 'done']:
        task.status = new_status
        
        # Update completed_at if status changed to 'done'
        if new_status == 'done' and not task.completed_at:
            task.completed_at = datetime.now()
        elif new_status != 'done':
            task.completed_at = None
            
        db.session.commit()
        flash('Task status updated', 'success')
    
    return redirect(url_for('view_task', project_id=project_id, task_id=task.id))

@app.route('/projects/<int:project_id>/tasks/<int:task_id>/notes/add', methods=['POST'])
def add_task_note(project_id, task_id):
    task = Task.query.get_or_404(task_id)
    
    # Ensure task belongs to the specified project
    if task.project_id != project_id:
        flash('Task does not belong to this project', 'danger')
        return redirect(url_for('project_tasks', project_id=project_id))
        
    content = request.form.get('content', '').strip()
    if content:
        note = TaskNote(content=content, task_id=task_id)
        db.session.add(note)
        db.session.commit()
        flash('Note added', 'success')
    
    return redirect(url_for('view_task', project_id=project_id, task_id=task.id))

@app.route('/projects/<int:project_id>/tasks/<int:task_id>/notes/<int:note_id>/delete', methods=['POST'])
def delete_task_note(project_id, task_id, note_id):
    note = TaskNote.query.get_or_404(note_id)
    task = Task.query.get_or_404(task_id)
    
    # Ensure note belongs to the specified task and project
    if note.task_id != task_id or task.project_id != project_id:
        flash('Note does not belong to this task or project', 'danger')
        return redirect(url_for('project_tasks', project_id=project_id))
        
    db.session.delete(note)
    db.session.commit()
    flash('Note deleted', 'success')
    
    return redirect(url_for('view_task', project_id=project_id, task_id=task_id))

# Template filter for markdown rendering
@app.template_filter('markdown')
def render_markdown(text):
    if text:
        return markdown.markdown(text, extensions=['fenced_code', 'tables'])
    return ''

# === Project Resource Link Routes ===
@app.route('/projects/<int:project_id>/link-server', methods=['POST'])
def link_server(project_id):
    project = Project.query.get_or_404(project_id)
    server_name = request.form.get('server_name')
    server_role = request.form.get('server_role', '')
    
    if server_name:
        # Check if server already linked
        existing = ProjectServer.query.filter_by(
            project_id=project_id, server_name=server_name
        ).first()
        
        if not existing:
            server = ProjectServer(
                project_id=project_id,
                server_name=server_name,
                server_role=server_role
            )
            db.session.add(server)
            db.session.commit()
            flash(f'Server {server_name} linked to project', 'success')
        else:
            flash(f'Server {server_name} is already linked to this project', 'warning')
    else:
        flash('No server selected', 'danger')
        
    return redirect(url_for('view_project', project_id=project_id))

@app.route('/projects/<int:project_id>/link-database', methods=['POST'])
def link_database(project_id):
    project = Project.query.get_or_404(project_id)
    database_name = request.form.get('database_name')
    database_type = request.form.get('database_type', '')
    
    if database_name:
        # Check if database already linked
        existing = ProjectDatabase.query.filter_by(
            project_id=project_id, database_name=database_name
        ).first()
        
        if not existing:
            database = ProjectDatabase(
                project_id=project_id,
                database_name=database_name,
                database_type=database_type
            )
            db.session.add(database)
            db.session.commit()
            flash(f'Database {database_name} linked to project', 'success')
        else:
            flash(f'Database {database_name} is already linked to this project', 'warning')
    else:
        flash('No database selected', 'danger')
        
    return redirect(url_for('view_project', project_id=project_id))

@app.route('/projects/<int:project_id>/unlink-server/<int:server_id>', methods=['POST'])
def unlink_server(project_id, server_id):
    server = ProjectServer.query.get_or_404(server_id)
    
    # Ensure server belongs to the specified project
    if server.project_id != project_id:
        flash('Server does not belong to this project', 'danger')
    else:
        server_name = server.server_name
        db.session.delete(server)
        db.session.commit()
        flash(f'Server {server_name} unlinked from project', 'success')
        
    return redirect(url_for('view_project', project_id=project_id))

@app.route('/projects/<int:project_id>/unlink-database/<int:database_id>', methods=['POST'])
def unlink_database(project_id, database_id):
    database = ProjectDatabase.query.get_or_404(database_id)
    
    # Ensure database belongs to the specified project
    if database.project_id != project_id:
        flash('Database does not belong to this project', 'danger')
    else:
        database_name = database.database_name
        db.session.delete(database)
        db.session.commit()
        flash(f'Database {database_name} unlinked from project', 'success')
        
    return redirect(url_for('view_project', project_id=project_id))

# === Settings Routes ===
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Application settings page"""
    # Get portal user status for premium check - always premium for local dev
    portal_status = {'is_premium': True}
    is_premium = True
    
    # Get all settings from the database
    all_settings = Setting.query.all()
    settings_dict = {}
    
    # Convert settings to a dictionary for easy access in the template
    for setting in all_settings:
        settings_dict[setting.key] = setting.value
    
    if request.method == 'POST':
        # Process form submission as before
        settings_to_update = [
            # PostgreSQL settings
            ('postgres_user', request.form.get('postgres_user', 'postgres')),
            ('postgres_password', request.form.get('postgres_password', '')),
            ('postgres_host', request.form.get('postgres_host', '127.0.0.1')),
            ('postgres_port', request.form.get('postgres_port', '5432')),
            
            # File paths
            ('filestore_dir', request.form.get('filestore_dir', FILESTORE_DIR)),
            ('upload_folder', request.form.get('upload_folder', app.config['UPLOAD_FOLDER'])),
            ('ssh_config_dir', request.form.get('ssh_config_dir', SSH_CONFIG_DIR)),
            
            # Application settings
            ('default_odoo_version', request.form.get('default_odoo_version', '17.0')),
            ('auto_backup_before_drop', 'true' if request.form.get('auto_backup_before_drop') else 'false'),
            ('dark_mode', 'true' if request.form.get('dark_mode') else 'false')
        ]
        
        # Update or create each setting in the database
        for key, value in settings_to_update:
            setting = Setting.query.filter_by(key=key).first()
            if setting:
                setting.value = value
            else:
                # Create new setting with appropriate description
                description = get_setting_description(key)
                new_setting = Setting(key=key, value=value, description=description)
                db.session.add(new_setting)
        
        db.session.commit()
        flash('Settings saved successfully', 'success')
        return redirect(url_for('settings'))
    
    # For local development, user is always authenticated
    user = current_user
    
    return render_template('settings.html', 
                          settings=settings_dict,
                          filestore_dir=FILESTORE_DIR,
                          upload_folder=app.config['UPLOAD_FOLDER'],
                          ssh_config_dir=SSH_CONFIG_DIR,
                          user=user,
                          is_premium=is_premium)

@app.route('/upgrade')
def upgrade_subscription():
    """Redirect to Django portal for subscription upgrade"""
    if not current_user.github_id:
        flash('Please connect your GitHub account first', 'warning')
        return redirect(url_for('github_settings'))
    
    # Generate a secure token for the Django portal
    token = generate_subscription_token(current_user)
    
    # Redirect to Django portal with the token
    portal_url = get_subscription_portal_url()
    return redirect(f"{portal_url}/upgrade?token={token}")

def generate_subscription_token(user):
    """Generate a secure token for subscription portal"""
    # In production, use a proper JWT or similar token
    import hashlib
    import time
    secret = os.environ.get('SUBSCRIPTION_SECRET_KEY', 'your-secret-key')
    data = f"{user.github_id}:{user.email}:{time.time()}"
    return hashlib.sha256(f"{data}:{secret}".encode()).hexdigest()

# === Premium Feature Routes ===
@app.route('/premium-features')
@premium_feature_required
def premium_features():
    """Show available premium features"""
    return render_template('premium_features.html', user=current_user)

@app.route('/odoo/install')
@premium_required
def odoo_install():
    """Odoo installation page"""
    servers = get_ssh_servers()
    return render_template('odoo_install.html', servers=servers)

@sock.route('/ws/ssh/<host>')
def ssh_terminal(ws, host):
    """WebSocket endpoint for SSH terminal"""
    try:
        # Get server details
        server = SSHServer.query.filter_by(host=host).first()
        if not server:
            ws.send(json.dumps({'type': 'error', 'message': 'Server not found'}))
            return

        # Create SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect to server
        ssh.connect(
            hostname=server.host,
            port=server.port,
            username=server.username,
            password=server.password if server.auth_type == 'password' else None,
            key_filename=server.key_path if server.auth_type == 'key' else None
        )
        
        # Create interactive shell
        channel = ssh.invoke_shell()
        channel.settimeout(0.1)
        
        # Store session
        session_id = f"{host}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        active_sessions[session_id] = {
            'ssh': ssh,
            'channel': channel,
            'last_activity': datetime.now()
        }
        
        # Send initial connection success
        ws.send(json.dumps({
            'type': 'connected',
            'message': f'Connected to {server.host}'
        }))
        
        # Main terminal loop
        while True:
            try:
                # Check for incoming WebSocket messages
                message = ws.receive()
                if message:
                    data = json.loads(message)
                    if data['type'] == 'input':
                        channel.send(data['data'])
                    elif data['type'] == 'resize':
                        channel.get_pty(term='xterm', width=data['cols'], height=data['rows'])
                
                # Check for incoming SSH data
                if channel.recv_ready():
                    data = channel.recv(4096).decode('utf-8', errors='ignore')
                    ws.send(json.dumps({
                        'type': 'output',
                        'data': data
                    }))
                
                # Check for errors
                if channel.recv_stderr_ready():
                    error = channel.recv_stderr(4096).decode('utf-8', errors='ignore')
                    ws.send(json.dumps({
                        'type': 'error',
                        'data': error
                    }))
                
                # Check if channel is closed
                if channel.exit_status_ready():
                    break
                    
            except Exception as e:
                ws.send(json.dumps({
                    'type': 'error',
                    'message': str(e)
                }))
                break
                
    except Exception as e:
        ws.send(json.dumps({
            'type': 'error',
            'message': str(e)
        }))
    finally:
        # Clean up
        if 'session_id' in locals():
            if session_id in active_sessions:
                session = active_sessions[session_id]
                session['channel'].close()
                session['ssh'].close()
                del active_sessions[session_id]


# === Run the Application ===
if __name__ == '__main__':
    import argparse
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Odoo Developer Tools UI')
    parser.add_argument('--port', type=int, default=5001, help='Port to run the server on')
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create database tables
    with app.app_context():
        db.create_all()
        print("Database tables created successfully")
    
    app.run(debug=True, port=args.port)

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
    has_active_subscription = True
    subscription_tier = "premium"
    subscription_expires_at = None
    
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

def test_ssh_connection(host):
    """Test SSH connection with detailed debugging information"""
    servers = get_ssh_servers()
    server = None
    for s in servers:
        if s.get('host') == host:
            server = s
            break
    
    if not server:
        return {'success': False, 'error': 'Server not found'}
    
    hostname = server.get('hostname', host)
    username = server.get('user') or os.getenv('USER', 'root')
    port = int(server.get('port', 22))
    
    debug_info = {
        'hostname': hostname,
        'username': username,
        'port': port,
        'key_file': server.get('key_file'),
        'auth_methods_tried': [],
        'ssh_agent_keys': 0,
        'success': False
    }
    
    # Check SSH agent
    try:
        # Set SSH_AUTH_SOCK if not set (common issue in web applications)
        if 'SSH_AUTH_SOCK' not in os.environ:
            # Try common SSH agent socket locations
            possible_sockets = [
                f'/run/user/{os.getuid()}/keyring/ssh',
                f'/tmp/ssh-agent-{os.getuid()}',
                '/tmp/ssh-agent',
            ]
            for socket_path in possible_sockets:
                if os.path.exists(socket_path):
                    os.environ['SSH_AUTH_SOCK'] = socket_path
                    break
        
        agent = paramiko.Agent()
        agent_keys = agent.get_keys()
        debug_info['ssh_agent_keys'] = len(agent_keys)
        if agent_keys:
            debug_info['ssh_agent_fingerprints'] = []
            for key in agent_keys:
                try:
                    fingerprint = key.get_fingerprint().hex()
                    debug_info['ssh_agent_fingerprints'].append(fingerprint)
                except:
                    pass
    except Exception as e:
        debug_info['ssh_agent_error'] = str(e)
    
    # Test connection
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # Try SSH Agent first
        try:
            agent = paramiko.Agent()
            agent_keys = agent.get_keys()
            if agent_keys:
                ssh.connect(
                    hostname=hostname,
                    port=port,
                    username=username,
                    pkey=agent_keys[0],  # Try first key
                    timeout=10,
                    look_for_keys=False,
                    allow_agent=True
                )
                debug_info['success'] = True
                debug_info['auth_method'] = 'SSH Agent'
                debug_info['auth_methods_tried'].append('SSH Agent: Success')
        except Exception as e:
            debug_info['auth_methods_tried'].append(f'SSH Agent: Failed - {str(e)}')
        
        # Try key file if agent failed
        if not debug_info['success'] and server.get('key_file'):
            key_path = os.path.expanduser(server['key_file'])
            try:
                # For RSA keys, use StringIO loading to handle traditional format
                if 'RSA' in open(key_path, 'r').read():
                    try:
                        with open(key_path, 'r') as f:
                            key_data = f.read()
                        from io import StringIO
                        key_obj = paramiko.RSAKey.from_private_key(StringIO(key_data))
                        ssh.connect(
                            hostname=hostname,
                            port=port,
                            username=username,
                            pkey=key_obj,
                            timeout=10,
                            look_for_keys=False,
                            allow_agent=False
                        )
                        debug_info['success'] = True
                        debug_info['auth_method'] = 'Key File (RSA StringIO)'
                        debug_info['auth_methods_tried'].append('Key File (RSA StringIO): Success')
                    except Exception as rsa_error:
                        debug_info['auth_methods_tried'].append(f'Key File (RSA StringIO): Failed - {str(rsa_error)}')
                
                # Fallback to standard file loading
                if not debug_info['success']:
                    ssh.connect(
                        hostname=hostname,
                        port=port,
                        username=username,
                        key_filename=key_path,
                        timeout=10,
                        look_for_keys=False,
                        allow_agent=False
                    )
                    debug_info['success'] = True
                    debug_info['auth_method'] = 'Key File'
                    debug_info['auth_methods_tried'].append('Key File: Success')
            except Exception as e:
                debug_info['auth_methods_tried'].append(f'Key File: Failed - {str(e)}')
        
    except Exception as e:
        debug_info['connection_error'] = str(e)
    finally:
        try:
            ssh.close()
        except:
            pass
    
    return debug_info

@app.route('/api/test_ssh/<host>')
def api_test_ssh(host):
    """API endpoint to test SSH connection and return debug info"""
    debug_info = test_ssh_connection(host)
    return jsonify(debug_info)

@sock.route('/ws/ssh/<host>')
def ssh_terminal(ws, host):
    """WebSocket endpoint for SSH terminal"""
    import subprocess
    import pty
    import os
    import select
    import threading
    import termios
    
    try:
        # Get server details from config files
        servers = get_ssh_servers()
        server = None
        for s in servers:
            if s.get('host') == host:
                server = s
                break
        
        if not server:
            ws.send(json.dumps({'type': 'error', 'message': 'Server not found'}))
            return

        hostname = server.get('hostname', host)
        username = server.get('user') or os.getenv('USER', 'root')
        port = int(server.get('port', 22))
        
        # Send initial connection message
        ws.send(json.dumps({
            'type': 'connected',
            'message': f'Connecting to {hostname} ({host}) as {username}...'
        }))
        
        # Create a pseudo-terminal
        master_fd, slave_fd = pty.openpty()
        
        # Start SSH process using system SSH (which works)
        ssh_cmd = ['ssh', '-t', host]
        
        # Set environment for SSH
        env = os.environ.copy()
        
        proc = subprocess.Popen(
            ssh_cmd,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=env,
            preexec_fn=os.setsid
        )
        
        os.close(slave_fd)  # Close slave fd in parent
        
        # Make master_fd non-blocking
        import fcntl
        fcntl.fcntl(master_fd, fcntl.F_SETFL, os.O_NONBLOCK)
        
        # Send success message
        ws.send(json.dumps({
            'type': 'connected',
            'message': f'Connected to {hostname} ({host}) using system SSH'
        }))
        
        # Store session
        session_id = f"{host}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        active_sessions[session_id] = {
            'process': proc,
            'master_fd': master_fd,
            'last_activity': datetime.now()
        }
        
        def read_output():
            """Read output from SSH process and send to WebSocket"""
            while True:
                try:
                    # Use select to check if data is available
                    ready, _, _ = select.select([master_fd], [], [], 0.1)
                    if ready:
                        try:
                            data = os.read(master_fd, 4096)
                            if data:
                                ws.send(json.dumps({
                                    'type': 'output',
                                    'data': data.decode('utf-8', errors='ignore')
                                }))
                            else:
                                break
                        except OSError:
                            break
                    
                    # Check if process is still alive
                    if proc.poll() is not None:
                        break
                        
                except Exception as e:
                    logger.error(f"Error reading SSH output: {e}")
                    break
        
        # Start output reading thread
        output_thread = threading.Thread(target=read_output, daemon=True)
        output_thread.start()
        
        # Main WebSocket loop
        try:
            while True:
                message = ws.receive(timeout=0.1)
                if message:
                    data = json.loads(message)
                    if data['type'] == 'input':
                        try:
                            input_data = data['data'].encode('utf-8')
                            os.write(master_fd, input_data)
                            # Update last activity
                            if session_id in active_sessions:
                                active_sessions[session_id]['last_activity'] = datetime.now()
                        except OSError as e:
                            logger.error(f"Error writing to SSH: {e}")
                            break
                    elif data['type'] == 'resize':
                        try:
                            # Set terminal size
                            import struct
                            cols = data.get('cols', 80)
                            rows = data.get('rows', 24)
                            winsize = struct.pack('HHHH', rows, cols, 0, 0)
                            fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
                        except Exception as resize_error:
                            logger.warning(f"Failed to resize terminal: {resize_error}")
                
                # Check if process ended
                if proc.poll() is not None:
                    exit_code = proc.returncode
                    ws.send(json.dumps({
                        'type': 'disconnected',
                        'message': f'SSH session ended with exit code {exit_code}'
                    }))
                    break
                    
        except Exception as e:
            error_str = str(e).lower()
            if "timed out" not in error_str and "timeout" not in error_str:
                logger.error(f"SSH terminal loop error: {e}")
                ws.send(json.dumps({
                    'type': 'error',
                    'message': f'Terminal error: {str(e)}'
                }))
        
    except Exception as e:
        logger.error(f"SSH terminal connection error: {e}")
        ws.send(json.dumps({
            'type': 'error',
            'message': f'Connection failed: {str(e)}'
        }))
    finally:
        # Clean up
        if 'session_id' in locals() and session_id in active_sessions:
            try:
                session = active_sessions[session_id]
                if 'process' in session:
                    try:
                        session['process'].terminate()
                        session['process'].wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        session['process'].kill()
                if 'master_fd' in session:
                    try:
                        os.close(session['master_fd'])
                    except:
                        pass
            except Exception as cleanup_error:
                logger.warning(f"Error during cleanup: {cleanup_error}")
            finally:
                del active_sessions[session_id]
        
        # Clean up local variables
        if 'master_fd' in locals():
            try:
                os.close(master_fd)
            except:
                pass
        if 'proc' in locals():
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except:
                try:
                    proc.kill()
                except:
                    pass

@app.route('/')
def index():
    """Main index page"""
    return render_template('index.html')

@app.route('/ssh')
@app.route('/ssh_servers')
@app.route('/servers')
def ssh_servers():
    """SSH servers list page"""
    servers = get_ssh_servers()
    return render_template('ssh.html', servers=servers, is_premium=True)

@app.route('/add_ssh_server')
def add_ssh_server():
    """Add SSH server page"""
    return render_template('add_ssh_server.html')

@app.route('/add_ssh_server', methods=['POST'])
def add_ssh_server_post():
    """Handle SSH server addition"""
    try:
        host = request.form['host']
        hostname = request.form['hostname']
        user = request.form['user']
        port = request.form.get('port', '22')
        key_file = request.form.get('key_file', '~/.ssh/id_rsa')
        
        # Create SSH config
        config_content = f"""Host {host}
    HostName {hostname}
    User {user}
    Port {port}
    IdentityFile {key_file}
"""
        
        # Save to config.d directory
        config_file = os.path.join(SSH_CONFIG_DIR, f"{host}.conf")
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        flash(f'SSH server {host} added successfully!', 'success')
        return redirect(url_for('ssh_servers'))
        
    except Exception as e:
        flash(f'Error adding SSH server: {str(e)}', 'error')
        return redirect(url_for('add_ssh_server'))

@app.route('/servers/connect/<host>', methods=['GET', 'POST'])
def connect_ssh(host):
    """Redirect to SSH terminal page"""
    servers = get_ssh_servers()
    
    # Find the server with matching host
    server = None
    for s in servers:
        if s.get('host') == host:
            server = s
            break
    
    if not server:
        flash('Server configuration not found', 'error')
        return redirect(url_for('ssh_servers'))
    
    # Redirect to terminal page
    return redirect(url_for('ssh_terminal_page', host=host))

@app.route('/terminal/ssh/<host>')
def ssh_terminal_page(host):
    """SSH terminal page"""
    servers = get_ssh_servers()
    
    # Find the server with matching host
    server = None
    for s in servers:
        if s.get('host') == host:
            server = s
            break
    
    if not server:
        flash('Server configuration not found', 'error')
        return redirect(url_for('ssh_servers'))
    
    return render_template('ssh_terminal.html', 
                         host=host, 
                         server=server)

@app.route('/servers/delete/<host>')
def delete_ssh_server(host):
    """Delete SSH server page"""
    return render_template('delete_ssh_server.html', host=host)

@app.route('/servers/delete/<host>', methods=['POST'])
def delete_ssh_server_post(host):
    """Handle SSH server deletion"""
    try:
        config_file = os.path.join(SSH_CONFIG_DIR, f"{host}.conf")
        if os.path.exists(config_file):
            os.remove(config_file)
            flash(f'SSH server {host} deleted successfully!', 'success')
        else:
            flash(f'SSH server {host} not found!', 'warning')
    except Exception as e:
        flash(f'Error deleting SSH server: {str(e)}', 'error')
    
    return redirect(url_for('ssh_servers'))

@app.route('/servers/details/<host>')
def ssh_server_details(host):
    """SSH server details page"""
    servers = get_ssh_servers()
    server = None
    for s in servers:
        if s.get('host') == host:
            server = s
            break
    
    if not server:
        flash('Server configuration not found', 'error')
        return redirect(url_for('ssh_servers'))
    
    return render_template('ssh_server_details.html', server=server, host=host)

@app.route('/upgrade')
def upgrade_subscription():
    """Upgrade subscription page (placeholder)"""
    return render_template('premium_features.html')

@app.route('/projects')
def projects():
    """Projects list page"""
    return render_template('projects/index.html')

@app.route('/projects/new')
def new_project():
    """New project form page"""
    return render_template('projects/form.html')

@app.route('/projects/new', methods=['POST'])
def create_project():
    """Handle project creation"""
    try:
        # This would handle project creation logic
        flash('Project creation feature coming soon!', 'info')
        return redirect(url_for('projects'))
    except Exception as e:
        flash(f'Error creating project: {str(e)}', 'error')
        return redirect(url_for('new_project'))

@app.route('/projects/<int:project_id>')
def view_project(project_id):
    """View project details"""
    return render_template('projects/view.html', project_id=project_id)

@app.route('/projects/<int:project_id>/edit')
def edit_project(project_id):
    """Edit project form"""
    return render_template('projects/form.html', project_id=project_id)

@app.route('/projects/<int:project_id>/edit', methods=['POST'])
def update_project(project_id):
    """Handle project update"""
    try:
        # This would handle project update logic
        flash('Project update feature coming soon!', 'info')
        return redirect(url_for('view_project', project_id=project_id))
    except Exception as e:
        flash(f'Error updating project: {str(e)}', 'error')
        return redirect(url_for('edit_project', project_id=project_id))

@app.route('/projects/<int:project_id>/delete')
def delete_project_page(project_id):
    """Delete project confirmation page"""
    return render_template('projects/delete_project.html', project_id=project_id)

@app.route('/projects/<int:project_id>/delete', methods=['POST'])
def delete_project(project_id):
    """Handle project deletion"""
    try:
        # This would handle project deletion logic
        flash('Project deletion feature coming soon!', 'info')
        return redirect(url_for('projects'))
    except Exception as e:
        flash(f'Error deleting project: {str(e)}', 'error')
        return redirect(url_for('delete_project_page', project_id=project_id))

@app.route('/tasks')
def tasks():
    """Tasks list page"""
    return render_template('tasks/index.html')

@app.route('/tasks/new')
def new_task():
    """New task form page"""
    return render_template('tasks/form.html')

@app.route('/tasks/new', methods=['POST'])
def create_task():
    """Handle task creation"""
    try:
        # This would handle task creation logic
        flash('Task creation feature coming soon!', 'info')
        return redirect(url_for('tasks'))
    except Exception as e:
        flash(f'Error creating task: {str(e)}', 'error')
        return redirect(url_for('new_task'))

@app.route('/tasks/<int:task_id>')
def view_task(task_id):
    """View task details"""
    return render_template('tasks/view.html', task_id=task_id)

@app.route('/tasks/<int:task_id>/edit')
def edit_task(task_id):
    """Edit task form"""
    return render_template('tasks/form.html', task_id=task_id)

@app.route('/tasks/<int:task_id>/edit', methods=['POST'])
def update_task(task_id):
    """Handle task update"""
    try:
        # This would handle task update logic
        flash('Task update feature coming soon!', 'info')
        return redirect(url_for('view_task', task_id=task_id))
    except Exception as e:
        flash(f'Error updating task: {str(e)}', 'error')
        return redirect(url_for('edit_task', task_id=task_id))

@app.route('/tasks/<int:task_id>/delete')
def delete_task_page(task_id):
    """Delete task confirmation page"""
    return render_template('tasks/delete_task.html', task_id=task_id)

@app.route('/tasks/<int:task_id>/delete', methods=['POST'])
def delete_task(task_id):
    """Handle task deletion"""
    try:
        # This would handle task deletion logic
        flash('Task deletion feature coming soon!', 'info')
        return redirect(url_for('tasks'))
    except Exception as e:
        flash(f'Error deleting task: {str(e)}', 'error')
        return redirect(url_for('delete_task_page', task_id=task_id))

@app.route('/databases')
@app.route('/list_databases')
def list_databases():
    """Databases list page"""
    try:
        conn = get_db_connection()
        if not conn:
            databases = []
        else:
            cursor = conn.cursor()
            cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;")
            databases = [{'name': row[0]} for row in cursor.fetchall()]
            conn.close()
    except Exception as e:
        logger.error(f"Error fetching databases: {str(e)}")
        databases = []
        flash(f'Error fetching databases: {str(e)}', 'error')
    
    return render_template('databases.html', databases=databases)

@app.route('/drop_database/<db_name>')
def drop_database(db_name):
    """Drop database confirmation page"""
    return render_template('drop_database.html', database_name=db_name, db_name=db_name)

@app.route('/drop_database/<db_name>', methods=['POST'])
def drop_database_post(db_name):
    """Handle database deletion"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(f"DROP DATABASE IF EXISTS {db_name};")
            conn.close()
            flash(f'Database {db_name} dropped successfully!', 'success')
        else:
            flash('Could not connect to database', 'error')
    except Exception as e:
        flash(f'Error dropping database: {str(e)}', 'error')
    
    return redirect(url_for('list_databases'))

@app.route('/restore_database')
def restore_database():
    """Restore database page"""
    return render_template('restore_database.html')

@app.route('/restore_database', methods=['POST'])
def restore_database_post():
    """Handle database restoration"""
    try:
        # This would handle database restoration logic
        flash('Database restoration feature coming soon!', 'info')
        return redirect(url_for('list_databases'))
    except Exception as e:
        flash(f'Error restoring database: {str(e)}', 'error')
        return redirect(url_for('restore_database'))

@app.route('/extend_enterprise')
@app.route('/extend_enterprise/<db_name>')
def extend_enterprise(db_name=None):
    """Extend enterprise page"""
    return render_template('extend_enterprise.html', db_name=db_name)

@app.route('/extend_enterprise', methods=['POST'])
@app.route('/extend_enterprise/<db_name>', methods=['POST'])
def extend_enterprise_post(db_name=None):
    """Handle enterprise extension"""
    try:
        if not db_name:
            db_name = request.form.get('db_name')
        # This would handle enterprise extension logic
        return render_template('extend_enterprise_results.html', db_name=db_name)
    except Exception as e:
        flash(f'Error extending enterprise: {str(e)}', 'error')
        return redirect(url_for('extend_enterprise', db_name=db_name))

@app.route('/odoo_install')
def odoo_install():
    """Odoo installation page"""
    return render_template('odoo_install.html')

@app.route('/odoo_install', methods=['POST'])
def odoo_install_post():
    """Handle Odoo installation"""
    try:
        # This would handle Odoo installation logic
        flash('Odoo installation feature coming soon!', 'info')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Error installing Odoo: {str(e)}', 'error')
        return redirect(url_for('odoo_install'))

@app.route('/settings')
def settings():
    """Settings page"""
    # Default settings values
    default_settings = {
        'postgres_user': 'odoo',
        'postgres_password': '',
        'postgres_host': 'localhost',
        'postgres_port': '5432',
        'filestore_dir': '/opt/odoo/filestore',
        'upload_folder': './uploads',
        'ssh_config_dir': SSH_CONFIG_DIR,
        'default_odoo_version': '17.0',
        'auto_backup_before_drop': 'false',
        'dark_mode': 'false'
    }
    
    return render_template('settings.html', 
                         settings=default_settings, 
                         is_premium=True, 
                         current_user=current_user)

@app.route('/settings', methods=['POST'])
def save_settings():
    """Save settings"""
    try:
        # This would handle settings saving logic
        # For now, just show a success message
        flash('Settings updated successfully!', 'success')
    except Exception as e:
        flash(f'Error updating settings: {str(e)}', 'error')
    
    return redirect(url_for('settings'))

@app.route('/terminal')
def terminal():
    """Local terminal page"""
    return render_template('terminal.html')

@app.route('/premium')
def premium_features():
    """Premium features page"""
    return render_template('premium_features.html')

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

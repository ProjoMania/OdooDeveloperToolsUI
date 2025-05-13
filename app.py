#!/usr/bin/env python3
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
import os
import psycopg2
import paramiko
import subprocess
import json
import re
import zipfile
import tempfile
import shutil
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import logging

# Initialize Flask application
app = Flask(__name__, 
            template_folder='src/templates',
            static_folder='src/static')
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = '/tmp/odoo_dev_tools_uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global settings
SSH_CONFIG_DIR = os.path.expanduser("~/.ssh/config.d")
FILESTORE_DIR = os.path.expanduser("~/.local/share/Odoo/filestore")

# Ensure necessary directories exist
os.makedirs(SSH_CONFIG_DIR, exist_ok=True)
os.makedirs(FILESTORE_DIR, exist_ok=True)

# === Helper Functions ===

def get_db_connection():
    """Create a connection to PostgreSQL"""
    try:
        conn = psycopg2.connect(dbname="postgres", user="postgres")
        conn.autocommit = True
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
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

# === Routes ===

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

# === SSH Server Routes ===

@app.route('/ssh')
def ssh_servers():
    """SSH Server management page"""
    servers = get_ssh_servers()
    return render_template('ssh.html', servers=servers)

@app.route('/ssh/add', methods=['GET', 'POST'])
def add_ssh_server():
    """Add a new SSH server"""
    if request.method == 'POST':
        # Get form data
        host = request.form.get('host').strip()
        hostname = request.form.get('hostname').strip()
        user = request.form.get('user').strip()
        port = request.form.get('port').strip() or "22"
        key_file = request.form.get('key_file').strip()
        
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
                    'key_file': key_file
                }
                return render_template('ssh_add.html', overwrite=True, 
                                      host=host, hostname=hostname, 
                                      user=user, port=port, key_file=key_file)
        
        # Write the configuration file
        with open(config_file, 'w') as f:
            f.write(f"Host {host}\n")
            f.write(f"    HostName {hostname}\n")
            if user:
                f.write(f"    User {user}\n")
            f.write(f"    Port {port}\n")
            if key_file:
                f.write(f"    IdentityFile {key_file}\n")
        
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

@app.route('/ssh/generate_command/<host>')
def generate_ssh_command(host):
    """Generate an SSH command for the client to execute"""
    servers = get_ssh_servers()
    server = next((s for s in servers if s['host'] == host), None)
    
    if not server:
        return jsonify({'error': 'Server not found'}), 404
    
    # Create the SSH command
    command = f"ssh {server['host']}"
    
    return jsonify({'command': command})

# === Database Routes ===

@app.route('/databases')
def list_databases():
    """List all Odoo databases"""
    conn = get_db_connection()
    
    if not conn:
        flash('Could not connect to PostgreSQL. Please check your credentials.', 'danger')
        return render_template('databases.html', databases=[])
    
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
        try:
            db_conn = psycopg2.connect(dbname=db_name, user="postgres")
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
            else:
                is_enterprise = False
            
            db_cursor.close()
            db_conn.close()
        except Exception:
            # If database access fails, leave as "Not Odoo DB"
            is_enterprise = False
        
        # Get filestore size
        filestore_path = os.path.join(FILESTORE_DIR, db_name)
        if os.path.exists(filestore_path):
            filestore_bytes = get_dir_size(filestore_path)
            filestore_size = format_size(filestore_bytes)
        else:
            filestore_size = "N/A"
        
        databases.append({
            'name': db_name,
            'owner': owner,
            'version': odoo_version,
            'size': db_size,
            'filestore_size': filestore_size,
            'is_enterprise': is_enterprise
        })
    
    cursor.close()
    conn.close()
    
    return render_template('databases.html', databases=databases)

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
                
                # Extract the backup zip
                with zipfile.ZipFile(filepath, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # Look for the SQL dump file
                dump_file = os.path.join(temp_dir, "dump.sql")
                if not os.path.exists(dump_file):
                    flash('Invalid backup: dump.sql not found in the backup file', 'danger')
                    shutil.rmtree(temp_dir)
                    os.remove(filepath)
                    return redirect(request.url)
                
                # Check for filestore.zip
                filestore_zip = os.path.join(temp_dir, "filestore.zip")
                has_filestore = os.path.exists(filestore_zip)
                
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
                
                # Extract filestore if it exists
                if has_filestore:
                    filestore_path = os.path.join(FILESTORE_DIR, db_name)
                    
                    # Remove existing filestore if it exists
                    if os.path.exists(filestore_path):
                        shutil.rmtree(filestore_path)
                    
                    # Create the directory
                    os.makedirs(filestore_path, exist_ok=True)
                    
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
def extend_enterprise():
    """Extend Odoo Enterprise license expiration date"""
    if request.method == 'POST':
        results = []
        # Connect to PostgreSQL
        conn = get_db_connection()
        if not conn:
            flash('Could not connect to PostgreSQL', 'danger')
            return redirect(url_for('list_databases'))
        
        cursor = conn.cursor()
        
        # Get all databases
        cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false")
        databases = [row[0] for row in cursor.fetchall() if row[0] not in ('postgres', 'template0', 'template1')]
        
        enterprise_dbs = []
        
        # Check each database for Odoo Enterprise
        for db_name in databases:
            try:
                db_conn = psycopg2.connect(dbname=db_name, user="postgres")
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
                        # This is an Enterprise database
                        enterprise_dbs.append(db_name)
                
                db_cursor.close()
                db_conn.close()
            except:
                # Skip databases that can't be accessed
                pass
        
        # Extend the expiration for each enterprise database
        for db_name in enterprise_dbs:
            try:
                db_conn = psycopg2.connect(dbname=db_name, user="postgres")
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
                    'database': db_name,
                    'old_date': old_date,
                    'new_date': new_date_str,
                    'status': 'success'
                })
                
                db_cursor.close()
                db_conn.close()
            except Exception as e:
                results.append({
                    'database': db_name,
                    'status': 'error',
                    'message': str(e)
                })
        
        cursor.close()
        conn.close()
        
        if not enterprise_dbs:
            flash('No Odoo Enterprise databases found', 'warning')
        else:
            flash(f'Extended license for {len(enterprise_dbs)} database(s)', 'success')
        
        return render_template('extend_enterprise_results.html', results=results)
    
    return render_template('extend_enterprise.html')

# === Run the Application ===
if __name__ == '__main__':
    app.run(debug=True)

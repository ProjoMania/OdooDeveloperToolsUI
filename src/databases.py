"""
Database Management Blueprint
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required
import os
import logging
import psycopg2
import subprocess
import tempfile
import shutil
from typing import Optional, Dict, List, Any
from werkzeug.utils import secure_filename
from .utils import get_db_connection, get_db_connection_params, format_size, get_dir_size, validate_file_extension
from .models import db

databases_bp = Blueprint('databases', __name__, url_prefix='/databases')
logger = logging.getLogger(__name__)

@databases_bp.route('/')
@databases_bp.route('/list')
def list_databases():
    """Display list of Odoo databases"""
    try:
        conn = get_db_connection()
        if not conn:
            return render_template('databases.html', databases=[], error="Database connection failed")
        
        cursor = conn.cursor()
        
        # Get list of databases
        cursor.execute("""
            SELECT datname, pg_size_pretty(pg_database_size(datname)) as size,
                   pg_database_size(datname) as size_bytes
            FROM pg_database 
            WHERE datname NOT IN ('template0', 'template1', 'postgres')
            ORDER BY pg_database_size(datname) DESC
        """)
        
        databases = []
        for row in cursor.fetchall():
            db_name, size, size_bytes = row
            
            # Get filestore size
            filestore_path = os.path.join(current_app.config['FILESTORE_DIR'], db_name)
            filestore_size = get_dir_size(filestore_path) if os.path.exists(filestore_path) else 0
            
            # Try to get Odoo version from database
            odoo_version = get_odoo_version(cursor, db_name)
            
            databases.append({
                'name': db_name,
                'size': size,
                'size_bytes': size_bytes,
                'filestore_size': format_size(filestore_size),
                'filestore_size_bytes': filestore_size,
                'odoo_version': odoo_version
            })
        
        conn.close()
        
        return render_template('databases.html', databases=databases)
        
    except Exception as e:
        logger.error(f"Error listing databases: {str(e)}")
        flash(f'Error loading databases: {str(e)}', 'danger')
        return render_template('databases.html', databases=[])

@databases_bp.route('/drop/<db_name>')
def drop_database(db_name):
    """Display database drop confirmation"""
    return render_template('drop_database.html', db_name=db_name)

@databases_bp.route('/drop/<db_name>', methods=['POST'])
def drop_database_post(db_name):
    """Handle database deletion"""
    try:
        conn = get_db_connection()
        if not conn:
            flash('Could not connect to PostgreSQL', 'danger')
            return redirect(url_for('databases.list_databases'))
        
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
        if not cursor.fetchone():
            flash(f'Database "{db_name}" does not exist', 'warning')
            conn.close()
            return redirect(url_for('databases.list_databases'))
        
        # Drop the database
        cursor.execute(f"DROP DATABASE \"{db_name}\"")
        conn.close()
        
        # Remove filestore directory
        filestore_path = os.path.join(current_app.config['FILESTORE_DIR'], db_name)
        if os.path.exists(filestore_path):
            shutil.rmtree(filestore_path)
        
        flash(f'Database "{db_name}" and its filestore deleted successfully', 'success')
        return redirect(url_for('databases.list_databases'))
        
    except Exception as e:
        logger.error(f"Error dropping database {db_name}: {str(e)}")
        flash(f'Error dropping database: {str(e)}', 'danger')
        return redirect(url_for('databases.list_databases'))

@databases_bp.route('/restore')
def restore_database():
    """Display database restore form"""
    return render_template('restore_database.html')

@databases_bp.route('/restore', methods=['POST'])
def restore_database_post():
    """Handle database restoration"""
    try:
        if 'backup_file' not in request.files:
            flash('No backup file selected', 'danger')
            return redirect(url_for('databases.restore_database'))
        
        file = request.files['backup_file']
        if file.filename == '':
            flash('No backup file selected', 'danger')
            return redirect(url_for('databases.restore_database'))
        
        if not validate_file_extension(file.filename):
            flash('Invalid file type. Please upload a .sql, .zip, .tar, or .gz file', 'danger')
            return redirect(url_for('databases.restore_database'))
        
        db_name = request.form.get('db_name', '').strip()
        if not db_name:
            flash('Database name is required', 'danger')
            return redirect(url_for('databases.restore_database'))
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Restore database
        success = restore_database_from_file(db_name, file_path)
        
        # Clean up uploaded file
        if os.path.exists(file_path):
            os.remove(file_path)
        
        if success:
            flash(f'Database "{db_name}" restored successfully', 'success')
            return redirect(url_for('databases.list_databases'))
        else:
            flash('Failed to restore database', 'danger')
            return redirect(url_for('databases.restore_database'))
        
    except Exception as e:
        logger.error(f"Error restoring database: {str(e)}")
        flash(f'Error restoring database: {str(e)}', 'danger')
        return redirect(url_for('databases.restore_database'))

@databases_bp.route('/extend_enterprise')
@databases_bp.route('/extend_enterprise/<db_name>')
def extend_enterprise(db_name=None):
    """Display enterprise license extension form"""
    if db_name:
        return render_template('extend_enterprise.html', db_name=db_name)
    return render_template('extend_enterprise.html')

@databases_bp.route('/extend_enterprise', methods=['POST'])
@databases_bp.route('/extend_enterprise/<db_name>', methods=['POST'])
def extend_enterprise_post(db_name=None):
    """Handle enterprise license extension"""
    try:
        if not db_name:
            db_name = request.form.get('db_name', '').strip()
        
        if not db_name:
            flash('Database name is required', 'danger')
            return redirect(url_for('databases.extend_enterprise'))
        
        # Connect to the database
        conn_params = get_db_connection_params()
        conn = psycopg2.connect(
            dbname=db_name,
            user=conn_params['user'],
            password=conn_params['password'],
            host=conn_params['host'],
            port=conn_params['port']
        )
        
        cursor = conn.cursor()
        
        # Extend enterprise license
        cursor.execute("""
            UPDATE ir_config_parameter 
            SET value = '2099-12-31' 
            WHERE key = 'database.expiration_date'
        """)
        
        cursor.execute("""
            UPDATE ir_config_parameter 
            SET value = '2099-12-31' 
            WHERE key = 'database.expiration_reason'
        """)
        
        conn.commit()
        conn.close()
        
        flash(f'Enterprise license for database "{db_name}" extended successfully', 'success')
        return redirect(url_for('databases.list_databases'))
        
    except Exception as e:
        logger.error(f"Error extending enterprise license for {db_name}: {str(e)}")
        flash(f'Error extending enterprise license: {str(e)}', 'danger')
        return redirect(url_for('databases.extend_enterprise'))

def get_odoo_version(cursor, db_name: str) -> Optional[str]:
    """
    Get Odoo version from database
    
    Args:
        cursor: Database cursor
        db_name: Database name
    
    Returns:
        Odoo version or None if not found
    """
    try:
        # Try to connect to the specific database
        conn_params = get_db_connection_params()
        conn = psycopg2.connect(
            dbname=db_name,
            user=conn_params['user'],
            password=conn_params['password'],
            host=conn_params['host'],
            port=conn_params['port']
        )
        
        cursor = conn.cursor()
        
        # Check if ir_module_module table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'ir_module_module'
            )
        """)
        
        if not cursor.fetchone()[0]:
            conn.close()
            return None
        
        # Get Odoo version from base module
        cursor.execute("""
            SELECT latest_version 
            FROM ir_module_module 
            WHERE name = 'base' 
            AND state = 'installed'
        """)
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            return result[0]
        
        return None
        
    except Exception as e:
        logger.warning(f"Could not get Odoo version for {db_name}: {str(e)}")
        return None

def restore_database_from_file(db_name: str, file_path: str) -> bool:
    """
    Restore database from backup file
    
    Args:
        db_name: Target database name
        file_path: Path to backup file
    
    Returns:
        True if successful, False otherwise
    """
    try:
        conn_params = get_db_connection_params()
        
        # Create database if it doesn't exist
        conn = psycopg2.connect(
            dbname="postgres",
            user=conn_params['user'],
            password=conn_params['password'],
            host=conn_params['host'],
            port=conn_params['port']
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Drop database if it exists
        cursor.execute(f"DROP DATABASE IF EXISTS \"{db_name}\"")
        
        # Create new database
        cursor.execute(f"CREATE DATABASE \"{db_name}\"")
        conn.close()
        
        # Determine file type and restore
        if file_path.endswith('.sql'):
            # Direct SQL restore
            restore_command = [
                'psql',
                '-h', conn_params['host'],
                '-p', conn_params['port'],
                '-U', conn_params['user'],
                '-d', db_name,
                '-f', file_path
            ]
            
            if conn_params['password']:
                restore_command = ['PGPASSWORD=' + conn_params['password']] + restore_command
                result = subprocess.run(restore_command, capture_output=True, text=True, env={'PGPASSWORD': conn_params['password']})
            else:
                result = subprocess.run(restore_command, capture_output=True, text=True)
        
        elif file_path.endswith(('.zip', '.tar', '.gz')):
            # Extract and restore
            temp_dir = tempfile.mkdtemp()
            try:
                if file_path.endswith('.zip'):
                    import zipfile
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                elif file_path.endswith('.tar'):
                    import tarfile
                    with tarfile.open(file_path, 'r') as tar_ref:
                        tar_ref.extractall(temp_dir)
                elif file_path.endswith('.gz'):
                    import tarfile
                    with tarfile.open(file_path, 'r:gz') as tar_ref:
                        tar_ref.extractall(temp_dir)
                
                # Find SQL file in extracted directory
                sql_files = [f for f in os.listdir(temp_dir) if f.endswith('.sql')]
                if not sql_files:
                    raise Exception("No SQL file found in backup archive")
                
                sql_file = os.path.join(temp_dir, sql_files[0])
                
                # Restore from extracted SQL file
                restore_command = [
                    'psql',
                    '-h', conn_params['host'],
                    '-p', conn_params['port'],
                    '-U', conn_params['user'],
                    '-d', db_name,
                    '-f', sql_file
                ]
                
                if conn_params['password']:
                    result = subprocess.run(restore_command, capture_output=True, text=True, env={'PGPASSWORD': conn_params['password']})
                else:
                    result = subprocess.run(restore_command, capture_output=True, text=True)
            
            finally:
                shutil.rmtree(temp_dir)
        
        else:
            raise Exception("Unsupported file format")
        
        if result.returncode != 0:
            logger.error(f"Restore command failed: {result.stderr}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error restoring database from file: {str(e)}")
        return False 
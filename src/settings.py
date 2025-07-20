"""
Settings Management Blueprint
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
import logging
from datetime import datetime
from typing import Optional
from .models import Setting, db
from .utils import get_setting

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')
logger = logging.getLogger(__name__)

@settings_bp.route('/')
def settings():
    """Display settings page"""
    try:
        # Get current settings
        settings_data = {
            'postgres_user': get_setting('postgres_user', 'postgres'),
            'postgres_password': get_setting('postgres_password', ''),
            'postgres_host': get_setting('postgres_host', '127.0.0.1'),
            'postgres_port': get_setting('postgres_port', '5432'),
            'ssh_config_dir': get_setting('ssh_config_dir', current_app.config['SSH_CONFIG_DIR']),
            'filestore_dir': get_setting('filestore_dir', current_app.config['FILESTORE_DIR']),
            'upload_folder': get_setting('upload_folder', current_app.config['UPLOAD_FOLDER']),
            'max_file_size': get_setting('max_file_size', str(current_app.config['MAX_FILE_SIZE'])),
            'django_portal_url': get_setting('django_portal_url', current_app.config.get('DJANGO_PORTAL_URL', 'http://127.0.0.1:8000')),
            'api_timeout': get_setting('api_timeout', str(current_app.config.get('API_TIMEOUT', 30))),
            'items_per_page': get_setting('items_per_page', str(current_app.config.get('ITEMS_PER_PAGE', 20))),
            'log_level': get_setting('log_level', current_app.config.get('LOG_LEVEL', 'INFO'))
        }
        
        return render_template('settings.html', settings=settings_data)
        
    except Exception as e:
        logger.error(f"Error loading settings: {str(e)}")
        flash('Error loading settings', 'danger')
        return render_template('settings.html', settings={})

@settings_bp.route('/', methods=['POST'])
def save_settings():
    """Handle settings save"""
    try:
        # Get form data
        postgres_user = request.form.get('postgres_user', '').strip()
        postgres_password = request.form.get('postgres_password', '').strip()
        postgres_host = request.form.get('postgres_host', '').strip()
        postgres_port = request.form.get('postgres_port', '').strip()
        ssh_config_dir = request.form.get('ssh_config_dir', '').strip()
        filestore_dir = request.form.get('filestore_dir', '').strip()
        upload_folder = request.form.get('upload_folder', '').strip()
        max_file_size = request.form.get('max_file_size', '').strip()
        django_portal_url = request.form.get('django_portal_url', '').strip()
        api_timeout = request.form.get('api_timeout', '').strip()
        items_per_page = request.form.get('items_per_page', '').strip()
        log_level = request.form.get('log_level', '').strip()
        
        # Validation
        if not postgres_user:
            flash('PostgreSQL user is required', 'danger')
            return redirect(url_for('settings.settings'))
        
        if not postgres_host:
            flash('PostgreSQL host is required', 'danger')
            return redirect(url_for('settings.settings'))
        
        if not postgres_port:
            flash('PostgreSQL port is required', 'danger')
            return redirect(url_for('settings.settings'))
        
        # Validate port is numeric
        try:
            int(postgres_port)
        except ValueError:
            flash('PostgreSQL port must be a number', 'danger')
            return redirect(url_for('settings.settings'))
        
        # Validate numeric fields
        try:
            if max_file_size:
                int(max_file_size)
            if api_timeout:
                int(api_timeout)
            if items_per_page:
                int(items_per_page)
        except ValueError:
            flash('File size, API timeout, and items per page must be numbers', 'danger')
            return redirect(url_for('settings.settings'))
        
        # Validate log level
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if log_level and log_level not in valid_log_levels:
            flash('Invalid log level', 'danger')
            return redirect(url_for('settings.settings'))
        
        # Save settings
        settings_to_save = {
            'postgres_user': postgres_user,
            'postgres_password': postgres_password,
            'postgres_host': postgres_host,
            'postgres_port': postgres_port,
            'ssh_config_dir': ssh_config_dir,
            'filestore_dir': filestore_dir,
            'upload_folder': upload_folder,
            'max_file_size': max_file_size,
            'django_portal_url': django_portal_url,
            'api_timeout': api_timeout,
            'items_per_page': items_per_page,
            'log_level': log_level
        }
        
        for key, value in settings_to_save.items():
            if value:  # Only save non-empty values
                setting = Setting.query.filter_by(key=key).first()
                if setting:
                    setting.value = value
                    setting.updated_at = datetime.utcnow()
                else:
                    setting = Setting(
                        key=key,
                        value=value,
                        description=f'{key.replace("_", " ").title()} setting'
                    )
                    db.session.add(setting)
        
        db.session.commit()
        
        flash('Settings saved successfully', 'success')
        return redirect(url_for('settings.settings'))
        
    except Exception as e:
        logger.error(f"Error saving settings: {str(e)}")
        db.session.rollback()
        flash(f'Error saving settings: {str(e)}', 'danger')
        return redirect(url_for('settings.settings'))

@settings_bp.route('/test_connection')
def test_database_connection():
    """Test database connection"""
    try:
        from .utils import get_db_connection
        
        conn = get_db_connection()
        if conn:
            conn.close()
            return {'success': True, 'message': 'Database connection successful'}
        else:
            return {'success': False, 'message': 'Database connection failed'}
            
    except Exception as e:
        logger.error(f"Error testing database connection: {str(e)}")
        return {'success': False, 'message': f'Connection error: {str(e)}'}

@settings_bp.route('/reset')
def reset_settings():
    """Reset settings to defaults"""
    try:
        # Get default settings
        default_settings = {
            'postgres_user': 'postgres',
            'postgres_password': '',
            'postgres_host': '127.0.0.1',
            'postgres_port': '5432',
            'ssh_config_dir': current_app.config['SSH_CONFIG_DIR'],
            'filestore_dir': current_app.config['FILESTORE_DIR'],
            'upload_folder': current_app.config['UPLOAD_FOLDER'],
            'max_file_size': str(current_app.config['MAX_FILE_SIZE']),
            'django_portal_url': current_app.config.get('DJANGO_PORTAL_URL', 'http://127.0.0.1:8000'),
            'api_timeout': str(current_app.config.get('API_TIMEOUT', 30)),
            'items_per_page': str(current_app.config.get('ITEMS_PER_PAGE', 20)),
            'log_level': current_app.config.get('LOG_LEVEL', 'INFO')
        }
        
        # Update settings with defaults
        for key, value in default_settings.items():
            setting = Setting.query.filter_by(key=key).first()
            if setting:
                setting.value = value
                setting.updated_at = datetime.utcnow()
            else:
                setting = Setting(
                    key=key,
                    value=value,
                    description=f'{key.replace("_", " ").title()} setting'
                )
                db.session.add(setting)
        
        db.session.commit()
        
        flash('Settings reset to defaults successfully', 'success')
        return redirect(url_for('settings.settings'))
        
    except Exception as e:
        logger.error(f"Error resetting settings: {str(e)}")
        db.session.rollback()
        flash(f'Error resetting settings: {str(e)}', 'danger')
        return redirect(url_for('settings.settings'))

@settings_bp.route('/export')
def export_settings():
    """Export settings as JSON"""
    try:
        settings_list = Setting.query.all()
        settings_data = {setting.key: setting.value for setting in settings_list}
        
        from flask import jsonify
        return jsonify(settings_data)
        
    except Exception as e:
        logger.error(f"Error exporting settings: {str(e)}")
        return {'error': str(e)}, 500

@settings_bp.route('/import', methods=['POST'])
def import_settings():
    """Import settings from JSON"""
    try:
        if 'settings_file' not in request.files:
            flash('No settings file selected', 'danger')
            return redirect(url_for('settings.settings'))
        
        file = request.files['settings_file']
        if file.filename == '':
            flash('No settings file selected', 'danger')
            return redirect(url_for('settings.settings'))
        
        if not file.filename.endswith('.json'):
            flash('Please upload a JSON file', 'danger')
            return redirect(url_for('settings.settings'))
        
        import json
        settings_data = json.load(file)
        
        # Validate settings data
        if not isinstance(settings_data, dict):
            flash('Invalid settings file format', 'danger')
            return redirect(url_for('settings.settings'))
        
        # Import settings
        for key, value in settings_data.items():
            if isinstance(value, (str, int, float, bool)):
                setting = Setting.query.filter_by(key=key).first()
                if setting:
                    setting.value = str(value)
                    setting.updated_at = datetime.utcnow()
                else:
                    setting = Setting(
                        key=key,
                        value=str(value),
                        description=f'{key.replace("_", " ").title()} setting'
                    )
                    db.session.add(setting)
        
        db.session.commit()
        
        flash('Settings imported successfully', 'success')
        return redirect(url_for('settings.settings'))
        
    except Exception as e:
        logger.error(f"Error importing settings: {str(e)}")
        db.session.rollback()
        flash(f'Error importing settings: {str(e)}', 'danger')
        return redirect(url_for('settings.settings')) 
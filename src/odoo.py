"""
Odoo Installation and Management Blueprint
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required
import logging
import requests
from typing import Optional, Dict, Any
from .models import OdooInstallation, db
from datetime import datetime

odoo_bp = Blueprint('odoo', __name__, url_prefix='/odoo')
logger = logging.getLogger(__name__)

@odoo_bp.route('/install')
def odoo_install():
    """Display Odoo installation form"""
    return render_template('odoo_install.html')

@odoo_bp.route('/install', methods=['POST'])
def odoo_install_post():
    """Handle Odoo installation request"""
    try:
        # Get form data
        server_host = request.form.get('server_host', '').strip()
        server_username = request.form.get('server_username', '').strip()
        odoo_version = request.form.get('odoo_version', '').strip()
        odoo_user = request.form.get('odoo_user', 'odoo').strip()
        port = request.form.get('port', '8069').strip()
        install_nginx = 'install_nginx' in request.form
        is_enterprise = 'is_enterprise' in request.form
        admin_password = request.form.get('admin_password', '').strip()
        
        # Validation
        if not server_host:
            flash('Server host is required', 'danger')
            return redirect(url_for('odoo.odoo_install'))
        
        if not server_username:
            flash('Server username is required', 'danger')
            return redirect(url_for('odoo.odoo_install'))
        
        if not odoo_version:
            flash('Odoo version is required', 'danger')
            return redirect(url_for('odoo.odoo_install'))
        
        if not admin_password:
            flash('Admin password is required', 'danger')
            return redirect(url_for('odoo.odoo_install'))
        
        # Create installation record
        installation = OdooInstallation(
            user_id=1,  # TODO: Get actual user ID
            server_host=server_host,
            server_username=server_username,
            odoo_version=odoo_version,
            odoo_user=odoo_user,
            port=int(port),
            install_nginx=install_nginx,
            is_enterprise=is_enterprise,
            admin_password=admin_password,
            status='pending'
        )
        
        db.session.add(installation)
        db.session.commit()
        
        # Forward installation request to Django portal
        django_url = current_app.config.get('DJANGO_PORTAL_URL', 'http://127.0.0.1:8000')
        
        installation_data = {
            'installation_id': installation.id,
            'server_host': server_host,
            'server_username': server_username,
            'odoo_version': odoo_version,
            'odoo_user': odoo_user,
            'port': int(port),
            'install_nginx': install_nginx,
            'is_enterprise': is_enterprise,
            'admin_password': admin_password
        }
        
        try:
            response = requests.post(
                f'{django_url}/api/odoo/install/',
                json=installation_data,
                headers={'Content-Type': 'application/json'},
                timeout=current_app.config.get('API_TIMEOUT', 30)
            )
            
            if response.status_code == 200:
                flash('Odoo installation request submitted successfully', 'success')
            else:
                logger.error(f"Django portal error: {response.status_code} - {response.text}")
                flash('Error submitting installation request to Django portal', 'warning')
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error contacting Django portal: {str(e)}")
            flash('Could not contact Django portal. Installation request saved locally.', 'warning')
        
        return redirect(url_for('odoo.odoo_install'))
        
    except Exception as e:
        logger.error(f"Error creating Odoo installation: {str(e)}")
        db.session.rollback()
        flash(f'Error creating installation request: {str(e)}', 'danger')
        return redirect(url_for('odoo.odoo_install'))

@odoo_bp.route('/installations')
def list_installations():
    """Display list of Odoo installations"""
    try:
        installations = OdooInstallation.query.order_by(OdooInstallation.created_at.desc()).all()
        return render_template('odoo_installations.html', installations=installations)
    except Exception as e:
        logger.error(f"Error fetching installations: {str(e)}")
        flash('Error loading installations', 'danger')
        return render_template('odoo_installations.html', installations=[])

@odoo_bp.route('/installation/<int:installation_id>')
def view_installation(installation_id):
    """Display installation details"""
    try:
        installation = OdooInstallation.query.get_or_404(installation_id)
        return render_template('odoo_installation_details.html', installation=installation)
    except Exception as e:
        logger.error(f"Error viewing installation {installation_id}: {str(e)}")
        flash('Error loading installation', 'danger')
        return redirect(url_for('odoo.list_installations'))

@odoo_bp.route('/installation/<int:installation_id>/status')
def check_installation_status(installation_id):
    """Check installation status from Django portal"""
    try:
        installation = OdooInstallation.query.get_or_404(installation_id)
        
        django_url = current_app.config.get('DJANGO_PORTAL_URL', 'http://127.0.0.1:8000')
        
        response = requests.get(
            f'{django_url}/api/odoo/install/{installation_id}/status/',
            timeout=current_app.config.get('API_TIMEOUT', 30)
        )
        
        if response.status_code == 200:
            status_data = response.json()
            
            # Update local installation record
            installation.status = status_data.get('status', installation.status)
            installation.error_message = status_data.get('error_message', installation.error_message)
            installation.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'status': installation.status,
                'error_message': installation.error_message
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Error checking status: {response.status_code}'
            }), 500
            
    except Exception as e:
        logger.error(f"Error checking installation status {installation_id}: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@odoo_bp.route('/service', methods=['POST'])
def manage_odoo_service():
    """Manage Odoo service (start/stop/restart)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        action = data.get('action')
        server_host = data.get('server_host')
        
        if not action or not server_host:
            return jsonify({'success': False, 'message': 'Action and server_host are required'}), 400
        
        django_url = current_app.config.get('DJANGO_PORTAL_URL', 'http://127.0.0.1:8000')
        
        response = requests.post(
            f'{django_url}/api/odoo/service/',
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=current_app.config.get('API_TIMEOUT', 30)
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            logger.error(f"Django portal service error: {response.status_code} - {response.text}")
            return jsonify({
                'success': False,
                'message': 'Error managing Odoo service'
            }), 500
            
    except Exception as e:
        logger.error(f"Error managing Odoo service: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@odoo_bp.route('/service/status', methods=['GET'])
def get_service_status():
    """Get Odoo service status"""
    try:
        server_host = request.args.get('server_host')
        if not server_host:
            return jsonify({'success': False, 'message': 'server_host parameter is required'}), 400
        
        django_url = current_app.config.get('DJANGO_PORTAL_URL', 'http://127.0.0.1:8000')
        
        response = requests.get(
            f'{django_url}/api/odoo/service/status/',
            params={'server_host': server_host},
            timeout=current_app.config.get('API_TIMEOUT', 30)
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            logger.error(f"Django portal status error: {response.status_code} - {response.text}")
            return jsonify({
                'success': False,
                'message': 'Error getting service status'
            }), 500
            
    except Exception as e:
        logger.error(f"Error getting service status: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@odoo_bp.route('/git-update', methods=['POST'])
def git_update():
    """Update Odoo from Git repository"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        server_host = data.get('server_host')
        odoo_path = data.get('odoo_path')
        
        if not server_host or not odoo_path:
            return jsonify({'success': False, 'message': 'server_host and odoo_path are required'}), 400
        
        django_url = current_app.config.get('DJANGO_PORTAL_URL', 'http://127.0.0.1:8000')
        
        response = requests.post(
            f'{django_url}/api/odoo/git-update/',
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=current_app.config.get('API_TIMEOUT', 30)
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            logger.error(f"Django portal git-update error: {response.status_code} - {response.text}")
            return jsonify({
                'success': False,
                'message': 'Error updating Odoo from Git'
            }), 500
            
    except Exception as e:
        logger.error(f"Error updating Odoo from Git: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@odoo_bp.route('/module', methods=['POST'])
def manage_odoo_module():
    """Manage Odoo modules (install/uninstall/update)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        action = data.get('action')
        server_host = data.get('server_host')
        module_name = data.get('module_name')
        
        if not all([action, server_host, module_name]):
            return jsonify({'success': False, 'message': 'action, server_host, and module_name are required'}), 400
        
        django_url = current_app.config.get('DJANGO_PORTAL_URL', 'http://127.0.0.1:8000')
        
        response = requests.post(
            f'{django_url}/api/odoo/module/',
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=current_app.config.get('API_TIMEOUT', 30)
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            logger.error(f"Django portal module error: {response.status_code} - {response.text}")
            return jsonify({
                'success': False,
                'message': 'Error managing Odoo module'
            }), 500
            
    except Exception as e:
        logger.error(f"Error managing Odoo module: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@odoo_bp.route('/logs', methods=['GET'])
def view_odoo_logs():
    """View Odoo logs"""
    try:
        server_host = request.args.get('server_host')
        log_file = request.args.get('log_file', 'odoo.log')
        lines = request.args.get('lines', '100')
        
        if not server_host:
            return jsonify({'success': False, 'message': 'server_host parameter is required'}), 400
        
        django_url = current_app.config.get('DJANGO_PORTAL_URL', 'http://127.0.0.1:8000')
        
        response = requests.get(
            f'{django_url}/api/odoo/logs/',
            params={
                'server_host': server_host,
                'log_file': log_file,
                'lines': lines
            },
            timeout=current_app.config.get('API_TIMEOUT', 30)
        )
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            logger.error(f"Django portal logs error: {response.status_code} - {response.text}")
            return jsonify({
                'success': False,
                'message': 'Error retrieving Odoo logs'
            }), 500
            
    except Exception as e:
        logger.error(f"Error retrieving Odoo logs: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500 
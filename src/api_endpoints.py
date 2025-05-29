#!/usr/bin/env python3
# API Endpoints for Odoo Developer Tools UI

from flask import Blueprint, jsonify, request
import psycopg2
import requests
import logging
from flask_login import login_required, current_user
from src.database import db
from models import OdooInstallation
from src.odoo_installer.installer import OdooInstaller, OdooInstallConfig
import threading
import os
import json
from src.portal_auth import get_portal_user_status

# Create a blueprint for API endpoints
api_bp = Blueprint('api', __name__, url_prefix='/api')
logger = logging.getLogger(__name__)

# Configure Django portal URL
DJANGO_PORTAL_URL = os.getenv('DJANGO_PORTAL_URL', 'http://localhost:8000')

# API endpoint to get the record count for a database
@api_bp.route('/database/<db_name>/record_count', methods=['GET'])
def get_database_record_count(db_name):
    """Get the total number of records in an Odoo database"""
    try:
        from app import get_connection_params
        # Get the database connection settings
        conn_params = get_connection_params()
        
        # Connect to the database
        conn = psycopg2.connect(
            dbname=db_name,
            user=conn_params['user'],
            password=conn_params['password'],
            host=conn_params['host'],
            port=conn_params['port']
        )
        cursor = conn.cursor()
        
        # Count records in all Odoo models (tables that start with 'ir_' or 'res_')
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND 
                  (table_name LIKE 'ir_%' OR 
                   table_name LIKE 'res_%')
        """)
        
        tables = cursor.fetchall()
        total_records = 0
        
        # Count records in each table
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            total_records += count
        
        conn.close()
        
        return jsonify({
            'success': True,
            'record_count': total_records
        })
        
    except Exception as e:
        logger.error(f"Error counting records in database {db_name}: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Error counting records: {str(e)}"
        }), 500


# API endpoint to fetch all available Odoo versions
@api_bp.route('/odoo/versions', methods=['GET'])
def get_odoo_versions():
    """Fetch all available Odoo versions from GitHub using tags with pagination"""
    try:
        import re
        import requests
        
        GITHUB_API_URL = "https://api.github.com/repos/odoo/odoo/tags"
        NUMERIC_VERSION_PATTERN = re.compile(r'^\d+\.\d+$')
        
        # Get all numeric versions with pagination
        numeric_versions = []
        page = 1
        
        while True:
            response = requests.get(GITHUB_API_URL, params={"per_page": 100, "page": page})
            if response.status_code != 200:
                logger.warning(f"Failed to fetch page {page} of Odoo tags: {response.status_code}")
                break
                
            tags = response.json()
            if not tags:  # Empty page means we've reached the end
                break
                
            # Extract numeric versions from this page
            for tag in tags:
                tag_name = tag.get('name', '')
                if NUMERIC_VERSION_PATTERN.match(tag_name):
                    numeric_versions.append(tag_name)
                    
            # Move to next page
            page += 1
            
            # Safety exit if too many pages (unlikely but prevents infinite loops)
            if page > 10:  
                logger.warning("Reached maximum page limit when fetching Odoo versions")
                break
        
        # Remove duplicates (just in case)
        numeric_versions = list(set(numeric_versions))
        
        # Sort versions in descending order (newest first)
        numeric_versions.sort(reverse=True, key=lambda v: [int(x) for x in v.split('.')])
        
        return jsonify({
            'success': True, 
            'versions': numeric_versions
        })
    except Exception as e:
        logger.error(f"Error fetching Odoo versions: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f"Failed to fetch Odoo versions: {str(e)}"
        }), 500

# API endpoint to submit a migration quotation request
@api_bp.route('/migration/request', methods=['POST'])
def submit_migration_request():
    """Submit a migration quotation request to ProjoMania"""
    try:
        # Get the request data
        request_data = request.json
        
        # Validate required fields
        if not request_data or not all(k in request_data for k in ['database_info', 'migration_options', 'contact_info']):
            return jsonify({
                'success': False,
                'message': "Missing required fields"
            }), 400
            
        contact_info = request_data.get('contact_info', {})
        if not all(k in contact_info and contact_info[k] for k in ['name', 'email']):
            return jsonify({
                'success': False,
                'message': "Missing required contact information"
            }), 400
        
        # Format the data for the ProjoMania API
        api_data = {
            'source': 'odoo_developer_tools',
            'request_type': 'migration_quotation',
            'database_info': request_data.get('database_info', {}),
            'migration_options': request_data.get('migration_options', {}),
            'contact_info': contact_info
        }
        
        # For testing/demo purposes, let's simulate a successful response
        # In production, uncomment the following code to make the actual API call
        """
        response = requests.post(
            'https://projomania.com/api/migration/quotation',
            json=api_data,
            headers={'Content-Type': 'application/json'},
            timeout=10  # 10 second timeout
        )
        
        # Check if the request was successful
        if response.status_code == 200:
            response_data = response.json()
            return jsonify({
                'success': True,
                'message': "Migration quotation request submitted successfully",
                'reference_id': response_data.get('reference_id', '')
            })
        else:
            # Log the error but don't expose API details to client
            logger.error(f"Error from ProjoMania API: {response.text}")
            return jsonify({
                'success': False,
                'message': "Failed to submit request to ProjoMania server"
            }), 500
        """
        
        # Simulated success response for demo
        return jsonify({
            'success': True,
            'message': "Migration quotation request submitted successfully",
            'reference_id': "DEMO-12345"
        })
            
    except requests.exceptions.RequestException as e:
        # Handle network errors
        logger.error(f"Network error when contacting ProjoMania API: {str(e)}")
        return jsonify({
            'success': False,
            'message': "Connection error. Please try again later."
        }), 503
        
    except Exception as e:
        # Handle other errors
        logger.error(f"Error submitting migration request: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"An unexpected error occurred: {str(e)}"
        }), 500

@api_bp.route('/odoo/install', methods=['POST'])
def install_odoo():
    """Start Odoo installation on remote server via Django portal"""
    try:
        # Check if user is authenticated through portal
        portal_status = get_portal_user_status()
        if not portal_status or not portal_status.get('is_logged_in'):
            return jsonify({'success': False, 'message': 'Authentication required'}), 401
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        # Forward the installation request to Django portal
        django_response = requests.post(
            f'{DJANGO_PORTAL_URL}/api/odoo/install/',
            json=data,
            cookies=request.cookies,  # Forward cookies for session
            timeout=30
        )
        
        if django_response.status_code == 200:
            return jsonify(django_response.json())
        else:
            return jsonify({
                'success': False, 
                'message': f'Django portal error: {django_response.status_code}'
            }), 500
            
    except requests.RequestException as e:
        logger.error(f"Error communicating with Django portal: {str(e)}")
        return jsonify({
            'success': False, 
            'message': 'Unable to communicate with installation service'
        }), 500
    except Exception as e:
        logger.error(f"Error in install_odoo: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@api_bp.route('/odoo/install/<installation_id>/status', methods=['GET'])
def check_installation_status(installation_id):
    """Check the status of an Odoo installation"""
    try:
        # Check authentication
        portal_status = get_portal_user_status()
        if not portal_status or not portal_status.get('is_logged_in'):
            return jsonify({'success': False, 'message': 'Authentication required'}), 401
        
        # Get status from Django portal
        django_response = requests.get(
            f'{DJANGO_PORTAL_URL}/api/odoo/install/{installation_id}/status/',
            cookies=request.cookies,
            timeout=15
        )
        
        if django_response.status_code == 200:
            return jsonify(django_response.json())
        else:
            return jsonify({
                'status': 'unknown',
                'message': 'Unable to get installation status'
            }), 500
            
    except requests.RequestException as e:
        logger.error(f"Error checking installation status: {str(e)}")
        return jsonify({
            'status': 'unknown',
            'message': 'Communication error'
        }), 500
    except Exception as e:
        logger.error(f"Error in check_installation_status: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@api_bp.route('/odoo/service', methods=['POST'])
def manage_odoo_service():
    """Manage Odoo service (start/stop/restart) - Premium feature"""
    try:
        # Check premium authentication
        portal_status = get_portal_user_status()
        if not portal_status or not portal_status.get('is_premium'):
            return jsonify({'success': False, 'message': 'Premium subscription required'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        # Forward to Django portal
        django_response = requests.post(
            f'{DJANGO_PORTAL_URL}/api/odoo/service/',
            json=data,
            cookies=request.cookies,
            timeout=30
        )
        
        if django_response.status_code == 200:
            return jsonify(django_response.json())
        else:
            return jsonify({
                'success': False,
                'message': f'Service management error: {django_response.status_code}'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in manage_odoo_service: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@api_bp.route('/odoo/service/status', methods=['GET'])
def get_service_status():
    """Get Odoo service status - Premium feature"""
    try:
        # Check premium authentication
        portal_status = get_portal_user_status()
        if not portal_status or not portal_status.get('is_premium'):
            return jsonify({'success': False, 'message': 'Premium subscription required'}), 403
        
        host = request.args.get('host')
        if not host:
            return jsonify({'success': False, 'message': 'Host parameter required'}), 400
        
        # Get status from Django portal
        django_response = requests.get(
            f'{DJANGO_PORTAL_URL}/api/odoo/service/status/',
            params={'host': host},
            cookies=request.cookies,
            timeout=15
        )
        
        if django_response.status_code == 200:
            return jsonify(django_response.json())
        else:
            return jsonify({
                'status': 'unknown',
                'message': 'Unable to get service status'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in get_service_status: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@api_bp.route('/odoo/git-update', methods=['POST'])
def git_update():
    """Pull updates from GitHub for custom addons - Premium feature"""
    try:
        # Check premium authentication
        portal_status = get_portal_user_status()
        if not portal_status or not portal_status.get('is_premium'):
            return jsonify({'success': False, 'message': 'Premium subscription required'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        # Forward to Django portal
        django_response = requests.post(
            f'{DJANGO_PORTAL_URL}/api/odoo/git-update/',
            json=data,
            cookies=request.cookies,
            timeout=60  # Git operations might take longer
        )
        
        if django_response.status_code == 200:
            return jsonify(django_response.json())
        else:
            return jsonify({
                'success': False,
                'message': f'Git update error: {django_response.status_code}'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in git_update: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@api_bp.route('/odoo/databases', methods=['GET'])
def get_odoo_databases():
    """Get list of Odoo databases on server - Premium feature"""
    try:
        # Check premium authentication
        portal_status = get_portal_user_status()
        if not portal_status or not portal_status.get('is_premium'):
            return jsonify({'success': False, 'message': 'Premium subscription required'}), 403
        
        host = request.args.get('host')
        if not host:
            return jsonify({'success': False, 'message': 'Host parameter required'}), 400
        
        # Get databases from Django portal
        django_response = requests.get(
            f'{DJANGO_PORTAL_URL}/api/odoo/databases/',
            params={'host': host},
            cookies=request.cookies,
            timeout=15
        )
        
        if django_response.status_code == 200:
            return jsonify(django_response.json())
        else:
            return jsonify({
                'databases': [],
                'message': 'Unable to get database list'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in get_odoo_databases: {str(e)}")
        return jsonify({'databases': [], 'message': str(e)}), 500

@api_bp.route('/odoo/module', methods=['POST'])
def manage_odoo_module():
    """Install/upgrade/uninstall Odoo modules - Premium feature"""
    try:
        # Check premium authentication
        portal_status = get_portal_user_status()
        if not portal_status or not portal_status.get('is_premium'):
            return jsonify({'success': False, 'message': 'Premium subscription required'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        # Forward to Django portal
        django_response = requests.post(
            f'{DJANGO_PORTAL_URL}/api/odoo/module/',
            json=data,
            cookies=request.cookies,
            timeout=120  # Module operations can take time
        )
        
        if django_response.status_code == 200:
            return jsonify(django_response.json())
        else:
            return jsonify({
                'success': False,
                'message': f'Module management error: {django_response.status_code}'
            }), 500
            
    except Exception as e:
        logger.error(f"Error in manage_odoo_module: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@api_bp.route('/odoo/logs', methods=['GET'])
def view_odoo_logs():
    """View Odoo logs - Premium feature"""
    try:
        # Check premium authentication
        portal_status = get_portal_user_status()
        if not portal_status or not portal_status.get('is_premium'):
            return jsonify({'success': False, 'message': 'Premium subscription required'}), 403
        
        host = request.args.get('host')
        if not host:
            return jsonify({'success': False, 'message': 'Host parameter required'}), 400
        
        # Get logs from Django portal
        django_response = requests.get(
            f'{DJANGO_PORTAL_URL}/api/odoo/logs/',
            params={'host': host},
            cookies=request.cookies,
            timeout=30
        )
        
        if django_response.status_code == 200:
            # Return logs content directly
            return django_response.content, 200, {'Content-Type': 'text/plain'}
        else:
            return f"Unable to retrieve logs (Status: {django_response.status_code})", 500, {'Content-Type': 'text/plain'}
            
    except Exception as e:
        logger.error(f"Error in view_odoo_logs: {str(e)}")
        return f"Error retrieving logs: {str(e)}", 500, {'Content-Type': 'text/plain'}

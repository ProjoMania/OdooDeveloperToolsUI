#!/usr/bin/env python3
# API Endpoints for Odoo Developer Tools UI

from flask import Blueprint, jsonify, request
import psycopg2
import requests
import logging
import os
import json

# Create a blueprint for API endpoints
api_bp = Blueprint('api', __name__, url_prefix='/api')
logger = logging.getLogger(__name__)

# Configure Django portal URL
DJANGO_PORTAL_URL = os.getenv('DJANGO_PORTAL_URL', 'http://127.0.0.1:8000')

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

# All Odoo management endpoints forward to Django portal
@api_bp.route('/odoo/install', methods=['POST'])
def install_odoo():
    """Forward Odoo installation request to Django portal"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        # Log the request data for debugging
        logger.info(f"Sending installation request to Django: {data}")
        logger.info(f"Django Portal URL: {DJANGO_PORTAL_URL}")
        logger.info(f"Request cookies: {dict(request.cookies)}")
        
        # Forward the installation request to Django portal
        django_response = requests.post(
            f'{DJANGO_PORTAL_URL}/api/odoo/install/',
            json=data,
            cookies=request.cookies,  # Forward cookies for session
            headers={
                'User-Agent': 'OdooDevTools-Flask',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            timeout=30
        )
        
        # Log Django response details
        logger.info(f"Django response status: {django_response.status_code}")
        logger.info(f"Django response headers: {dict(django_response.headers)}")
        logger.info(f"Django response text: {django_response.text}")
        
        # Try to parse JSON response
        try:
            response_data = django_response.json()
            logger.info(f"Django response JSON: {response_data}")
        except ValueError:
            logger.error(f"Django returned non-JSON response: {django_response.text}")
            response_data = {
                'success': False,
                'message': f'Django returned invalid response (Status: {django_response.status_code})',
                'details': django_response.text
            }
        
        return jsonify(response_data), django_response.status_code
            
    except requests.RequestException as e:
        logger.error(f"Error communicating with Django portal: {str(e)}")
        return jsonify({
            'success': False, 
            'message': 'Unable to communicate with installation service',
            'details': str(e)
        }), 500
    except Exception as e:
        logger.error(f"Error in install_odoo: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@api_bp.route('/odoo/install/<installation_id>/status', methods=['GET'])
def check_installation_status(installation_id):
    """Forward installation status check to Django portal"""
    try:
        # Get status from Django portal
        django_response = requests.get(
            f'{DJANGO_PORTAL_URL}/api/odoo/install/{installation_id}/status/',
            cookies=request.cookies,
            headers={'User-Agent': 'OdooDevTools-Flask'},
            timeout=15
        )
        
        return jsonify(django_response.json()), django_response.status_code
            
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
    """Forward service management to Django portal"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        # Forward to Django portal
        django_response = requests.post(
            f'{DJANGO_PORTAL_URL}/api/odoo/service/',
            json=data,
            cookies=request.cookies,
            headers={'User-Agent': 'OdooDevTools-Flask'},
            timeout=30
        )
        
        return jsonify(django_response.json()), django_response.status_code
            
    except Exception as e:
        logger.error(f"Error in manage_odoo_service: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@api_bp.route('/odoo/service/status', methods=['GET'])
def get_service_status():
    """Forward service status check to Django portal"""
    try:
        host = request.args.get('host')
        if not host:
            return jsonify({'success': False, 'message': 'Host parameter required'}), 400
        
        # Get status from Django portal
        django_response = requests.get(
            f'{DJANGO_PORTAL_URL}/api/odoo/service/status/',
            params={'host': host},
            cookies=request.cookies,
            headers={'User-Agent': 'OdooDevTools-Flask'},
            timeout=15
        )
        
        return jsonify(django_response.json()), django_response.status_code
            
    except Exception as e:
        logger.error(f"Error in get_service_status: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@api_bp.route('/odoo/git-update', methods=['POST'])
def git_update():
    """Forward git update to Django portal"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        # Forward to Django portal
        django_response = requests.post(
            f'{DJANGO_PORTAL_URL}/api/odoo/git-update/',
            json=data,
            cookies=request.cookies,
            headers={'User-Agent': 'OdooDevTools-Flask'},
            timeout=60  # Git operations might take longer
        )
        
        return jsonify(django_response.json()), django_response.status_code
            
    except Exception as e:
        logger.error(f"Error in git_update: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@api_bp.route('/odoo/databases', methods=['GET'])
def get_odoo_databases():
    """Forward database list request to Django portal"""
    try:
        host = request.args.get('host')
        if not host:
            return jsonify({'success': False, 'message': 'Host parameter required'}), 400
        
        # Get databases from Django portal
        django_response = requests.get(
            f'{DJANGO_PORTAL_URL}/api/odoo/databases/',
            params={'host': host},
            cookies=request.cookies,
            headers={'User-Agent': 'OdooDevTools-Flask'},
            timeout=15
        )
        
        return jsonify(django_response.json()), django_response.status_code
            
    except Exception as e:
        logger.error(f"Error in get_odoo_databases: {str(e)}")
        return jsonify({'databases': [], 'message': str(e)}), 500

@api_bp.route('/odoo/module', methods=['POST'])
def manage_odoo_module():
    """Forward module management to Django portal"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        # Forward to Django portal
        django_response = requests.post(
            f'{DJANGO_PORTAL_URL}/api/odoo/module/',
            json=data,
            cookies=request.cookies,
            headers={'User-Agent': 'OdooDevTools-Flask'},
            timeout=120  # Module operations can take time
        )
        
        return jsonify(django_response.json()), django_response.status_code
            
    except Exception as e:
        logger.error(f"Error in manage_odoo_module: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@api_bp.route('/odoo/logs', methods=['GET'])
def view_odoo_logs():
    """Forward logs request to Django portal"""
    try:
        host = request.args.get('host')
        if not host:
            return jsonify({'success': False, 'message': 'Host parameter required'}), 400
        
        # Get logs from Django portal
        django_response = requests.get(
            f'{DJANGO_PORTAL_URL}/api/odoo/logs/',
            params={'host': host},
            cookies=request.cookies,
            headers={'User-Agent': 'OdooDevTools-Flask'},
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

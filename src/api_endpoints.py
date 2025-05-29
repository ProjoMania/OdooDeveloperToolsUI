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

# Create a blueprint for API endpoints
api_bp = Blueprint('api', __name__, url_prefix='/api')
logger = logging.getLogger(__name__)

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

@api_bp.route('/odoo/install/', methods=['POST'])
@login_required
def start_odoo_installation():
    """Start a new Odoo installation"""
    try:
        data = request.get_json()
        
        # Create installation record
        installation = OdooInstallation(
            user_id=current_user.id,
            server_host=data['server_host'],
            server_username=data['server_username'],
            odoo_version=data['odoo_version'],
            odoo_user=data.get('odoo_user', 'odoo'),
            port=data.get('port', 8069),
            install_nginx=data.get('install_nginx', False),
            is_enterprise=data.get('is_enterprise', False),
            admin_password=data['admin_password'],
            status='pending'
        )
        db.session.add(installation)
        db.session.commit()

        # Start installation in background thread
        thread = threading.Thread(
            target=perform_installation,
            args=(installation.id, data)
        )
        thread.start()

        return jsonify({
            'message': 'Installation started',
            'installation_id': installation.id
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def perform_installation(installation_id, data):
    """Perform the actual installation in a background thread"""
    try:
        installation = OdooInstallation.query.get(installation_id)
        if not installation:
            return

        installation.status = 'in_progress'
        db.session.commit()

        # Create installer configuration
        config = OdooInstallConfig(
            version=installation.odoo_version,
            user=installation.odoo_user,
            port=installation.port,
            install_nginx=installation.install_nginx,
            is_enterprise=installation.is_enterprise,
            admin_password=installation.admin_password
        )

        # Create installer instance
        installer = OdooInstaller(
            host=installation.server_host,
            username=installation.server_username,
            password=data.get('server_password')
        )

        # Perform installation
        success = installer.install_odoo(config)

        if success:
            installation.status = 'completed'
        else:
            installation.status = 'failed'
            installation.error_message = 'Installation failed'

    except Exception as e:
        installation.status = 'failed'
        installation.error_message = str(e)

    finally:
        db.session.commit()

@api_bp.route('/odoo/installations/<int:installation_id>/status/')
@login_required
def get_installation_status(installation_id):
    """Get the status of an installation"""
    try:
        installation = OdooInstallation.query.get_or_404(installation_id)
        if installation.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403

        return jsonify({
            'status': installation.status,
            'error_message': installation.error_message,
            'created_at': installation.created_at.isoformat(),
            'updated_at': installation.updated_at.isoformat()
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/odoo/installations/')
@login_required
def list_installations():
    """List all installations for the current user"""
    try:
        installations = OdooInstallation.query.filter_by(user_id=current_user.id).all()
        data = [{
            'id': inst.id,
            'odoo_version': inst.odoo_version,
            'server_host': inst.server_host,
            'status': inst.status,
            'created_at': inst.created_at.isoformat(),
            'updated_at': inst.updated_at.isoformat()
        } for inst in installations]
        return jsonify({'installations': data})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

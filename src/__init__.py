"""
Odoo Developer Tools UI - Flask Application Factory
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_sock import Sock
import logging
import os
from typing import Optional

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
sock = Sock()

def create_app(config_name: Optional[str] = None) -> Flask:
    """
    Application factory function
    
    Args:
        config_name: Configuration name to use (development, testing, production)
    
    Returns:
        Flask application instance
    """
    from config import get_config
    
    # Create Flask app
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')
    
    # Load configuration
    if config_name:
        app.config.from_object(f'config.{config_name.capitalize()}Config')
    else:
        app.config.from_object(get_config())
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    sock.init_app(app)
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # Setup logging
    setup_logging(app)
    
    # Create necessary directories
    create_directories(app)
    
    # Register blueprints
    register_blueprints(app)
    
    # Register template globals
    register_template_globals(app)
    
    # Create database tables
    with app.app_context():
        try:
            db.create_all()
            app.logger.info("Database tables created successfully")
        except Exception as e:
            app.logger.error(f"Error creating database tables: {str(e)}")
            raise
    
    return app

def setup_logging(app: Flask) -> None:
    """Setup application logging"""
    logging.basicConfig(
        level=getattr(logging, app.config.get('LOG_LEVEL', 'INFO')),
        format=app.config.get('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )

def create_directories(app: Flask) -> None:
    """Create necessary directories for the application"""
    directories = [
        app.config['UPLOAD_FOLDER'],
        app.config['SSH_CONFIG_DIR'],
        app.config['FILESTORE_DIR']
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

def register_blueprints(app: Flask) -> None:
    """Register Flask blueprints"""
    try:
        from .api_endpoints import api_bp
        app.register_blueprint(api_bp)
    except ImportError:
        app.logger.warning("API endpoints blueprint not available")
    
    try:
        from .auth import auth_bp
        app.register_blueprint(auth_bp)
    except ImportError:
        app.logger.warning("Auth blueprint not available")
    
    try:
        from .ssh import ssh_bp
        app.register_blueprint(ssh_bp)
    except ImportError:
        app.logger.warning("SSH blueprint not available")
    
    try:
        from .projects import projects_bp
        app.register_blueprint(projects_bp)
    except ImportError:
        app.logger.warning("Projects blueprint not available")
    
    try:
        from .tasks import tasks_bp
        app.register_blueprint(tasks_bp)
    except ImportError:
        app.logger.warning("Tasks blueprint not available")
    
    try:
        from .databases import databases_bp
        app.register_blueprint(databases_bp)
    except ImportError:
        app.logger.warning("Databases blueprint not available")
    
    try:
        from .odoo import odoo_bp
        app.register_blueprint(odoo_bp)
    except ImportError:
        app.logger.warning("Odoo blueprint not available")
    
    try:
        from .settings import settings_bp
        app.register_blueprint(settings_bp)
    except ImportError:
        app.logger.warning("Settings blueprint not available")
    
    try:
        from .websocket import websocket_bp, init_websocket
        init_websocket(app)
        app.register_blueprint(websocket_bp)
    except ImportError:
        app.logger.warning("WebSocket blueprint not available")

def register_template_globals(app: Flask) -> None:
    """Register template global functions"""
    try:
        from .utils import get_portal_user_status
        app.template_global()(get_portal_user_status)
    except ImportError:
        app.logger.warning("Utils module not available for template globals")

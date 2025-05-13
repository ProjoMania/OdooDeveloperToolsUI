import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24)
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload configuration
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or '/tmp/odoo_dev_tools_uploads'
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max upload
    
    # SSH configuration
    SSH_CONFIG_DIR = os.environ.get('SSH_CONFIG_DIR') or os.path.expanduser("~/.ssh/config.d")
    
    # Odoo configuration
    FILESTORE_DIR = os.environ.get('FILESTORE_DIR') or os.path.expanduser("~/.local/share/Odoo/filestore")
    
    # Logging configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'

# Odoo Developer Tools UI

A modern, refactored Flask-based desktop application for Odoo development and server management on Linux systems.

## 🚀 Features

### Core Functionality
- **Modern UI**: Elegant black and orange color scheme with responsive design
- **Project Management**: Create, manage, and track development projects
- **Task Management**: Organize tasks within projects with status tracking
- **SSH Server Management**: Configure and connect to remote servers
- **Database Management**: Manage Odoo databases with backup/restore capabilities
- **Odoo Installation**: Automated Odoo installation and management
- **Settings Management**: Centralized configuration management

### Technical Improvements
- **Modular Architecture**: Blueprint-based organization for better maintainability
- **Application Factory Pattern**: Proper Flask application initialization
- **Type Hints**: Full type annotation support for better code quality
- **Comprehensive Error Handling**: Consistent error handling throughout
- **Security Enhancements**: Improved authentication and authorization
- **Configuration Management**: Environment-based configuration system

## 🏗️ Architecture

### Project Structure
```
OdooDeveloperToolsUI/
├── app.py                 # Main application entry point
├── config.py             # Configuration management
├── models.py             # Database models
├── requirements.txt      # Python dependencies
├── src/                  # Source code package
│   ├── __init__.py       # Application factory
│   ├── auth.py           # Authentication blueprint
│   ├── ssh.py            # SSH management blueprint
│   ├── projects.py       # Project management blueprint
│   ├── tasks.py          # Task management blueprint
│   ├── databases.py      # Database management blueprint
│   ├── odoo.py           # Odoo installation blueprint
│   ├── settings.py       # Settings management blueprint
│   ├── api_endpoints.py  # API endpoints
│   ├── utils.py          # Utility functions
│   ├── database.py       # Database initialization
│   ├── portal_auth.py    # Portal authentication
│   ├── static/           # Static assets
│   └── templates/        # HTML templates
└── scripts/              # Installation and maintenance scripts
```

### Blueprint Organization
- **auth**: User authentication and authorization
- **ssh**: SSH server configuration and terminal access
- **projects**: Project creation, management, and tracking
- **tasks**: Task management within projects
- **databases**: Odoo database operations
- **odoo**: Odoo installation and service management
- **settings**: Application configuration management

## 🛠️ Installation

### Prerequisites
- Python 3.8 or higher
- PostgreSQL (for Odoo databases)
- SSH client tools
- Virtual environment (recommended)

### Quick Start
1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/OdooDeveloperToolsUI.git
   cd OdooDeveloperToolsUI
   ```

2. **Set up virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Initialize database**:
   ```bash
   python -c "from src import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
   ```

6. **Run the application**:
   ```bash
   python app.py
   ```

### Production Deployment
```bash
# Using the installation script
./install.sh

# Or manual deployment
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## ⚙️ Configuration

### Environment Variables
```bash
# Flask Configuration
FLASK_ENV=production
SECRET_KEY=your-secret-key-here

# Database Configuration
DATABASE_URL=sqlite:///dev_tools.db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432

# SSH Configuration
SSH_CONFIG_DIR=~/.ssh/config.d
SSH_DEFAULT_PORT=22
SSH_TIMEOUT=30

# Odoo Configuration
FILESTORE_DIR=~/.local/share/Odoo/filestore
ODOO_DEFAULT_PORT=8069

# API Configuration
DJANGO_PORTAL_URL=http://127.0.0.1:8000
API_TIMEOUT=30

# File Upload
UPLOAD_FOLDER=/tmp/odoo_dev_tools_uploads
MAX_CONTENT_LENGTH=524288000
```

### Configuration Classes
- **DevelopmentConfig**: Debug mode, detailed logging
- **ProductionConfig**: Optimized for production with security settings
- **TestingConfig**: In-memory database for testing

## 🔧 Development

### Code Quality
- **Type Hints**: All functions include proper type annotations
- **Docstrings**: Comprehensive documentation for all functions
- **Error Handling**: Consistent exception handling patterns
- **Logging**: Structured logging throughout the application

### Testing
```bash
# Run tests
python -m pytest tests/

# Run with coverage
python -m pytest --cov=src tests/
```

### Code Style
```bash
# Format code
black src/ app.py config.py models.py

# Lint code
flake8 src/ app.py config.py models.py

# Type checking
mypy src/ app.py config.py models.py
```

## 📚 API Documentation

### Authentication Endpoints
- `POST /auth/login` - User login
- `POST /auth/register` - User registration
- `GET /auth/logout` - User logout
- `GET /auth/profile` - User profile

### SSH Management
- `GET /ssh/` - List SSH servers
- `POST /ssh/add` - Add SSH server
- `GET /ssh/terminal/<host>` - SSH terminal page
- `DELETE /ssh/delete/<host>` - Delete SSH server

### Project Management
- `GET /projects/` - List projects
- `POST /projects/new` - Create project
- `GET /projects/<id>` - View project
- `PUT /projects/<id>` - Update project
- `DELETE /projects/<id>` - Delete project

### Database Management
- `GET /databases/` - List databases
- `POST /databases/restore` - Restore database
- `DELETE /databases/drop/<name>` - Drop database
- `POST /databases/extend_enterprise` - Extend enterprise license

## 🔒 Security Features

### Authentication & Authorization
- Flask-Login integration
- Password hashing with Werkzeug
- Session management
- Subscription-based access control

### Input Validation
- Form validation with WTForms
- File upload security
- SQL injection prevention
- XSS protection

### Configuration Security
- Environment variable configuration
- Secure session settings
- CSRF protection
- Secure headers

## 🚀 Deployment

### Systemd Service
```bash
# Install as system service
sudo ./install.sh

# Service management
sudo systemctl start odoo-developer-tools
sudo systemctl enable odoo-developer-tools
sudo systemctl status odoo-developer-tools
```

### Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Make your changes with proper tests
4. Ensure code quality checks pass
5. Submit a pull request

### Code Standards
- Follow PEP 8 style guidelines
- Include type hints for all functions
- Write comprehensive docstrings
- Add tests for new functionality
- Update documentation as needed

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Troubleshooting
- Check the logs: `sudo journalctl -u odoo-developer-tools`
- Verify database connectivity
- Check SSH configuration
- Review application logs

### Common Issues
1. **Database Connection**: Ensure PostgreSQL is running and accessible
2. **SSH Issues**: Verify SSH keys and permissions
3. **Permission Errors**: Check file and directory permissions
4. **Port Conflicts**: Ensure port 5000 is available

### Getting Help
- Create an issue on GitHub
- Check the documentation
- Review the logs for error details
- Test with minimal configuration

## 🔄 Migration from Old Version

If you're upgrading from the previous monolithic version:

1. **Backup your data**:
   ```bash
   cp dev_tools.db dev_tools.db.backup
   ```

2. **Update configuration**:
   - Review and update your `.env` file
   - Check new configuration options

3. **Run database migrations**:
   ```bash
   python -c "from src import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
   ```

4. **Test functionality**:
   - Verify all features work as expected
   - Check SSH connections
   - Test database operations

## 📈 Roadmap

### Planned Features
- [ ] Real-time collaboration
- [ ] Advanced project analytics
- [ ] Multi-server deployment
- [ ] Automated testing integration
- [ ] Mobile-responsive design
- [ ] API rate limiting
- [ ] Advanced backup strategies
- [ ] Performance monitoring

### Technical Improvements
- [ ] Async/await support
- [ ] GraphQL API
- [ ] Microservices architecture
- [ ] Container orchestration
- [ ] CI/CD pipeline
- [ ] Performance optimization
- [ ] Security audit tools

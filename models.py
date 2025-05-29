from src.database import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

# Project Model
class Project(db.Model):
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')  # active, archived, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    repository_url = db.Column(db.String(255))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    
    # Relationships
    tasks = db.relationship('Task', backref='project', lazy=True, cascade="all, delete-orphan")
    servers = db.relationship('ProjectServer', backref='project', lazy=True, cascade="all, delete-orphan")
    databases = db.relationship('ProjectDatabase', backref='project', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Project {self.name}>'

# Task Model
class Task(db.Model):
    __tablename__ = 'tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='todo')  # todo, in_progress, review, done
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, urgent
    due_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    # Foreign Keys
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    
    # Relationships
    notes = db.relationship('TaskNote', backref='task', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Task {self.title}>'
    
    def mark_complete(self):
        self.status = 'done'
        self.completed_at = datetime.utcnow()

# Task Notes
class TaskNote(db.Model):
    __tablename__ = 'task_notes'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Foreign Keys
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    
    def __repr__(self):
        return f'<TaskNote {self.id}>'

# Many-to-Many relationship between Projects and SSH Servers
class ProjectServer(db.Model):
    __tablename__ = 'project_servers'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    server_name = db.Column(db.String(100), nullable=False)
    server_role = db.Column(db.String(50))  # e.g., "production", "staging", "development"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ProjectServer {self.server_name} for Project {self.project_id}>'

# Many-to-Many relationship between Projects and Databases
class ProjectDatabase(db.Model):
    __tablename__ = 'project_databases'
    
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    database_name = db.Column(db.String(100), nullable=False)
    database_type = db.Column(db.String(50))  # e.g., "development", "testing", "production"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<ProjectDatabase {self.database_name} for Project {self.project_id}>'

# User Model
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # GitHub OAuth fields
    github_id = db.Column(db.String(100), unique=True)
    github_access_token = db.Column(db.String(255))
    github_username = db.Column(db.String(100))
    
    # Subscription fields
    subscription_id = db.Column(db.String(100), unique=True)
    subscription_status = db.Column(db.String(20), default='free')  # free, active, expired, cancelled
    subscription_tier = db.Column(db.String(20), default='free')  # free, basic, pro, enterprise
    subscription_expires_at = db.Column(db.DateTime)
    last_verification = db.Column(db.DateTime)
    
    @property
    def has_active_subscription(self):
        """Check if user has an active subscription"""
        if not self.subscription_status or self.subscription_status == 'free':
            return False
        if self.subscription_expires_at and self.subscription_expires_at < datetime.now():
            return False
        return True
    
    @property
    def can_access_premium_features(self):
        """Check if user can access premium features"""
        return self.has_active_subscription and self.subscription_tier in ['basic', 'pro', 'enterprise']
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

# Settings Model
class Setting(db.Model):
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Setting {self.key}>'

class OdooInstallation(db.Model):
    """Model for tracking Odoo installations"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    server_host = db.Column(db.String(255), nullable=False)
    server_username = db.Column(db.String(255), nullable=False)
    odoo_version = db.Column(db.String(10), nullable=False)
    odoo_user = db.Column(db.String(255), nullable=False, default='odoo')
    port = db.Column(db.Integer, nullable=False, default=8069)
    install_nginx = db.Column(db.Boolean, nullable=False, default=False)
    is_enterprise = db.Column(db.Boolean, nullable=False, default=False)
    admin_password = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('odoo_installations', lazy=True))

    def __repr__(self):
        return f'<OdooInstallation {self.id}>'

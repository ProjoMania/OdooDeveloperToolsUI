"""
Authentication and Authorization Blueprint
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
import logging
from typing import Optional
from .models import User, db

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
logger = logging.getLogger(__name__)

@auth_bp.route('/login')
def login():
    """Display login form"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('auth/login.html')

@auth_bp.route('/login', methods=['POST'])
def login_post():
    """Handle login form submission"""
    try:
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash('Username and password are required', 'danger')
            return redirect(url_for('auth.login'))
        
        # Find user
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            flash(f'Welcome back, {user.username}!', 'success')
            
            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')
            return redirect(url_for('auth.login'))
            
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        flash('An error occurred during login', 'danger')
        return redirect(url_for('auth.login'))

@auth_bp.route('/logout')
@login_required
def logout():
    """Handle user logout"""
    try:
        logout_user()
        flash('You have been logged out successfully', 'info')
        return redirect(url_for('auth.login'))
    except Exception as e:
        logger.error(f"Error during logout: {str(e)}")
        flash('An error occurred during logout', 'danger')
        return redirect(url_for('index'))

@auth_bp.route('/register')
def register():
    """Display registration form"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('auth/register.html')

@auth_bp.route('/register', methods=['POST'])
def register_post():
    """Handle registration form submission"""
    try:
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Validation
        if not username or not email or not password:
            flash('All fields are required', 'danger')
            return redirect(url_for('auth.register'))
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('auth.register'))
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'danger')
            return redirect(url_for('auth.register'))
        
        # Check if user already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists', 'danger')
            return redirect(url_for('auth.register'))
        
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash('Email already registered', 'danger')
            return redirect(url_for('auth.register'))
        
        # Create new user
        user = User(
            username=username,
            email=email,
            subscription_status='free',
            subscription_tier='free'
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))
        
    except Exception as e:
        logger.error(f"Error during registration: {str(e)}")
        db.session.rollback()
        flash('An error occurred during registration', 'danger')
        return redirect(url_for('auth.register'))

@auth_bp.route('/profile')
@login_required
def profile():
    """Display user profile"""
    return render_template('auth/profile.html', user=current_user)

@auth_bp.route('/profile', methods=['POST'])
@login_required
def update_profile():
    """Handle profile update"""
    try:
        email = request.form.get('email', '').strip()
        current_password = request.form.get('current_password', '').strip()
        new_password = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        # Update email if provided
        if email and email != current_user.email:
            existing_email = User.query.filter_by(email=email).first()
            if existing_email and existing_email.id != current_user.id:
                flash('Email already registered by another user', 'danger')
                return redirect(url_for('auth.profile'))
            
            current_user.email = email
        
        # Update password if provided
        if current_password and new_password:
            if not current_user.check_password(current_password):
                flash('Current password is incorrect', 'danger')
                return redirect(url_for('auth.profile'))
            
            if new_password != confirm_password:
                flash('New passwords do not match', 'danger')
                return redirect(url_for('auth.profile'))
            
            if len(new_password) < 6:
                flash('New password must be at least 6 characters long', 'danger')
                return redirect(url_for('auth.profile'))
            
            current_user.set_password(new_password)
        
        db.session.commit()
        flash('Profile updated successfully', 'success')
        return redirect(url_for('auth.profile'))
        
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        db.session.rollback()
        flash('An error occurred while updating profile', 'danger')
        return redirect(url_for('auth.profile'))

@auth_bp.route('/subscription')
@login_required
def subscription():
    """Display subscription information"""
    return render_template('auth/subscription.html', user=current_user)

@auth_bp.route('/upgrade')
@login_required
def upgrade_subscription():
    """Display subscription upgrade options"""
    return render_template('auth/upgrade.html')

# Decorators for subscription checks
def subscription_required(f):
    """Decorator to require active subscription"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        if not current_user.has_active_subscription:
            flash('This feature requires an active subscription', 'warning')
            return redirect(url_for('auth.upgrade_subscription'))
        
        return f(*args, **kwargs)
    
    return decorated_function

def premium_feature_required(f):
    """Decorator to require premium subscription"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        if not current_user.can_access_premium_features:
            flash('This feature requires a premium subscription', 'warning')
            return redirect(url_for('auth.upgrade_subscription'))
        
        return f(*args, **kwargs)
    
    return decorated_function

def get_subscription_portal_url():
    """Get subscription portal URL"""
    return current_app.config.get('SUBSCRIPTION_PORTAL_URL', 'https://projomania.com/subscription')

# User loader for Flask-Login
def load_user(user_id):
    """Load user for Flask-Login"""
    try:
        return User.query.get(int(user_id))
    except (ValueError, TypeError):
        return None 
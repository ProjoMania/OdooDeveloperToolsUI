import requests
from functools import wraps
from flask import current_app, redirect, url_for, flash, session
from datetime import datetime
import os

def check_subscription_status(user):
    """Check user's subscription status from Django portal"""
    try:
        # Get subscription status from Django portal
        portal_url = os.environ.get('SUBSCRIPTION_PORTAL_URL', 'http://127.0.0.1:8000')
        api_key = os.environ.get('SUBSCRIPTION_API_KEY', '')
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f"{portal_url}/api/check-subscription/{user.github_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            user.subscription_id = data.get('subscription_id')
            user.subscription_status = data.get('status', 'free')
            user.subscription_tier = data.get('tier', 'free')
            
            # Convert expiration date string to datetime
            expires_at = data.get('expires_at')
            if expires_at:
                user.subscription_expires_at = datetime.fromisoformat(expires_at)
            
            return True
        return False
    except Exception as e:
        current_app.logger.error(f"Error checking subscription status: {str(e)}")
        return False

def subscription_required(f):
    """Decorator to require an active subscription"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_app.login_manager.is_authenticated:
            return redirect(url_for('login'))
        
        user = current_app.login_manager.current_user
        if not user.has_active_subscription:
            flash('This feature requires an active subscription', 'warning')
            return redirect(url_for('upgrade_subscription'))
        
        return f(*args, **kwargs)
    return decorated_function

def premium_feature_required(f):
    """Decorator to require premium features access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_app.login_manager.is_authenticated:
            return redirect(url_for('login'))
        
        user = current_app.login_manager.current_user
        if not user.can_access_premium_features:
            flash('This feature requires a premium subscription', 'warning')
            return redirect(url_for('upgrade_subscription'))
        
        return f(*args, **kwargs)
    return decorated_function

def get_subscription_portal_url():
    """Get the subscription portal URL with proper protocol"""
    portal_url = os.environ.get('SUBSCRIPTION_PORTAL_URL', 'http://127.0.0.1:8000')
    if not portal_url.startswith(('http://', 'https://')):
        portal_url = f"http://{portal_url}"
    return portal_url 
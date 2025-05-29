import requests
from functools import wraps
from flask import current_app, redirect, url_for, flash, session
from datetime import datetime
import os
import hmac
import hashlib
import time
import json

def generate_verification_token(user_id, timestamp):
    """Generate a secure verification token"""
    secret = os.environ.get('SUBSCRIPTION_SECRET_KEY', '')
    message = f"{user_id}:{timestamp}"
    return hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

def verify_subscription_token(token, user_id, timestamp):
    """Verify the subscription token"""
    if not token or not user_id or not timestamp:
        return False
    
    # Token should be less than 5 minutes old
    if time.time() - float(timestamp) > 300:
        return False
    
    expected_token = generate_verification_token(user_id, timestamp)
    return hmac.compare_digest(token, expected_token)

def check_subscription_status(user):
    """Check user's subscription status from Django portal"""
    try:
        # Get subscription status from Django portal
        portal_url = os.environ.get('SUBSCRIPTION_PORTAL_URL', 'http://127.0.0.1:8000')
        api_key = os.environ.get('SUBSCRIPTION_API_KEY', '')
        
        # Generate verification token
        timestamp = str(time.time())
        token = generate_verification_token(user.github_id, timestamp)
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'X-Verification-Token': token,
            'X-Timestamp': timestamp
        }
        
        response = requests.get(
            f"{portal_url}/api/check-subscription/{user.github_id}",
            headers=headers,
            timeout=5  # Add timeout
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Verify response signature
            response_token = response.headers.get('X-Response-Token')
            if not verify_subscription_token(response_token, user.github_id, timestamp):
                current_app.logger.error("Invalid response token")
                return False
            
            # Update user subscription details
            user.subscription_id = data.get('subscription_id')
            user.subscription_status = data.get('status', 'free')
            user.subscription_tier = data.get('tier', 'free')
            
            # Convert expiration date string to datetime
            expires_at = data.get('expires_at')
            if expires_at:
                user.subscription_expires_at = datetime.fromisoformat(expires_at)
            
            # Store last verification timestamp
            user.last_verification = datetime.now()
            
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
        
        # Check if verification is needed (every 24 hours)
        if not user.last_verification or \
           (datetime.now() - user.last_verification).total_seconds() > 86400:
            if not check_subscription_status(user):
                flash('Could not verify subscription status', 'error')
                return redirect(url_for('settings'))
        
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
        
        # Check if verification is needed (every 24 hours)
        if not user.last_verification or \
           (datetime.now() - user.last_verification).total_seconds() > 86400:
            if not check_subscription_status(user):
                flash('Could not verify subscription status', 'error')
                return redirect(url_for('settings'))
        
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
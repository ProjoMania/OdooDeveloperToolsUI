import requests
from flask import request
from functools import wraps
from flask import redirect, url_for, flash

def get_portal_user_status():
    """Check user login and premium status from Django portal"""
    sessionid = request.cookies.get('sessionid')
    print(f"Django sessionid in Flask: {sessionid}")  # Debug print
    
    if not sessionid:
        print("No sessionid cookie found")
        return None
        
    try:
        resp = requests.get(
            "http://127.0.0.1:8000/api/user/status/",
            cookies={'sessionid': sessionid},
            timeout=3
        )
        print(f"Django API response: {resp.status_code} - {resp.text}")  # Debug print
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                print(f"Parsed JSON: {data}")  # Debug print
                return data
            except ValueError as e:
                print(f"JSON parse error: {e}")
                return None
        else:
            print(f"API returned status {resp.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Portal check failed: {e}")
        return None

def premium_required(f):
    """Decorator to protect premium routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        portal_status = get_portal_user_status()
        if not portal_status or not portal_status.get('is_premium'):
            flash("You need a premium account to access this feature.", "warning")
            return redirect(url_for('settings'))
        return f(*args, **kwargs)
    return decorated_function
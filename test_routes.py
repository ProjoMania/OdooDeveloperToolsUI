#!/usr/bin/env python3
"""
Simple route testing script for Odoo Developer Tools UI
Tests all the restored routes to ensure they match the develop branch structure
"""

import requests
import sys

def test_routes():
    """Test all the main routes"""
    base_url = "http://localhost:5001"
    
    routes_to_test = [
        "/",                    # Index page
        "/databases",           # Databases list
        "/list_databases",      # Databases list (alias)
        "/projects",            # Projects list
        "/tasks",               # Tasks list
        "/ssh_servers",         # SSH servers list
        "/settings",            # Settings page
        "/premium",             # Premium features
        "/odoo_install",        # Odoo installation
        "/add_ssh_server",      # Add SSH server form
        "/restore_database",    # Restore database form
        "/extend_enterprise",   # Extend enterprise form
    ]
    
    print("Testing restored routes...")
    print("=" * 50)
    
    success_count = 0
    total_count = len(routes_to_test)
    
    for route in routes_to_test:
        try:
            response = requests.get(f"{base_url}{route}", timeout=5)
            status = "✓ PASS" if response.status_code == 200 else f"✗ FAIL ({response.status_code})"
            print(f"{route:<25} {status}")
            if response.status_code == 200:
                success_count += 1
        except requests.exceptions.RequestException as e:
            print(f"{route:<25} ✗ ERROR ({str(e)})")
    
    print("=" * 50)
    print(f"Results: {success_count}/{total_count} routes working")
    
    if success_count == total_count:
        print("🎉 All routes restored successfully!")
        return True
    else:
        print("⚠️  Some routes need attention")
        return False

if __name__ == "__main__":
    success = test_routes()
    sys.exit(0 if success else 1) 
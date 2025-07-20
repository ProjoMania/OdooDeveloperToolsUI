#!/usr/bin/env python3
"""
Odoo Developer Tools UI - Main Application Entry Point
"""

from src import create_app, db, login_manager, sock
from src.auth import load_user
from src.models import Project, Task, User
from flask import render_template, request, jsonify, current_app
from datetime import datetime
import logging
import json

# Create Flask application
app = create_app()

# Configure user loader for Flask-Login
@login_manager.user_loader
def user_loader(user_id):
    return load_user(user_id)

# WebSocket functionality moved to src/websocket.py blueprint

# Main routes
@app.route('/')
def index():
    """Main dashboard"""
    try:
        # Get statistics
        stats = {
            'total_projects': Project.query.count(),
            'active_projects': Project.query.filter_by(status='active').count(),
            'total_tasks': Task.query.count(),
            'completed_tasks': Task.query.filter_by(status='done').count(),
            'pending_tasks': Task.query.filter_by(status='todo').count()
        }
        
        # Get recent projects
        recent_projects = Project.query.order_by(Project.created_at.desc()).limit(5).all()
        
        # Get recent tasks
        recent_tasks = Task.query.order_by(Task.created_at.desc()).limit(5).all()
        
        return render_template('index.html', 
                             stats=stats, 
                             recent_projects=recent_projects,
                             recent_tasks=recent_tasks)
    except Exception as e:
        current_app.logger.error(f"Error loading dashboard: {str(e)}")
        return render_template('index.html', 
                             stats={}, 
                             recent_projects=[],
                             recent_tasks=[])

@app.route('/terminal')
def terminal():
    """Terminal page"""
    return render_template('terminal.html')

@app.route('/premium')
def premium_features():
    """Premium features page"""
    return render_template('premium_features.html')

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('errors/403.html'), 403

# Context processors
@app.context_processor
def inject_now():
    """Inject current time into templates"""
    return {'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

@app.context_processor
def inject_user():
    """Inject user information into templates"""
    from flask_login import current_user
    return {'current_user': current_user}

# Health check endpoint
@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db.session.execute('SELECT 1')
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        current_app.logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

if __name__ == '__main__':
    app.run(debug=app.config.get('DEBUG', False), 
            host='0.0.0.0', 
            port=5000)

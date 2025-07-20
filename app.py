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

# Store active SSH sessions
active_sessions = {}

# WebSocket route for SSH terminal
@sock.route('/ws/ssh/<host>')
def ssh_terminal(ws, host):
    """WebSocket endpoint for SSH terminal"""
    from src.utils import create_ssh_client, get_ssh_config
    import paramiko
    import threading
    import time
    
    try:
        # Get SSH configuration
        server_config = get_ssh_config(host)
        if not server_config:
            ws.send(json.dumps({'error': 'SSH configuration not found'}))
            return
        
        # Create SSH client
        client = create_ssh_client(host)
        if not client:
            ws.send(json.dumps({'error': 'Failed to connect to SSH server'}))
            return
        
        # Get shell channel
        channel = client.invoke_shell()
        channel.settimeout(0.1)
        
        # Store session
        session_id = f"{host}_{int(time.time())}"
        active_sessions[session_id] = {
            'client': client,
            'channel': channel,
            'host': host
        }
        
        # Send connection success message
        ws.send(json.dumps({
            'type': 'connection',
            'status': 'connected',
            'host': host
        }))
        
        def read_output():
            """Read output from SSH channel and send to WebSocket"""
            try:
                while True:
                    if channel.recv_ready():
                        data = channel.recv(1024).decode('utf-8', errors='ignore')
                        if data:
                            ws.send(json.dumps({
                                'type': 'output',
                                'data': data
                            }))
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error reading SSH output: {str(e)}")
                ws.send(json.dumps({
                    'type': 'error',
                    'message': 'Connection lost'
                }))
        
        # Start output reading thread
        output_thread = threading.Thread(target=read_output)
        output_thread.daemon = True
        output_thread.start()
        
        # Handle incoming messages
        while True:
            try:
                message = ws.receive()
                if message is None:
                    break
                
                data = json.loads(message)
                command = data.get('command', '')
                
                if command:
                    channel.send(command)
                    
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {str(e)}")
                break
        
    except Exception as e:
        logger.error(f"Error in SSH terminal WebSocket: {str(e)}")
        ws.send(json.dumps({
            'type': 'error',
            'message': str(e)
        }))
    
    finally:
        # Clean up
        if session_id in active_sessions:
            session = active_sessions[session_id]
            try:
                session['channel'].close()
                session['client'].close()
            except:
                pass
            del active_sessions[session_id]

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

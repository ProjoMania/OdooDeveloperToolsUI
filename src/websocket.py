"""
WebSocket routes for Odoo Developer Tools UI
"""

from flask import Blueprint, current_app
from flask_sock import Sock
import json
import logging
import threading
import time
from typing import Dict, Any

# Create WebSocket blueprint
websocket_bp = Blueprint('websocket', __name__)
sock = Sock()

# Store active SSH sessions
active_sessions: Dict[str, Dict[str, Any]] = {}

@sock.route('/ws/ssh/<host>')
def ssh_terminal(ws, host):
    """WebSocket endpoint for SSH terminal"""
    from .utils import create_ssh_client, get_ssh_config
    import paramiko
    
    session_id = None
    logger = current_app.logger
    
    try:
        # Get SSH configuration
        server_config = get_ssh_config(host)
        if not server_config:
            ws.send(json.dumps({'type': 'error', 'message': 'SSH configuration not found'}))
            return
        
        # Create SSH client
        client = create_ssh_client(host)
        if not client:
            ws.send(json.dumps({'type': 'error', 'message': 'Failed to connect to SSH server'}))
            return
        
        # Get shell channel
        channel = client.invoke_shell()
        channel.settimeout(0.1)
        
        # Wait a moment for the shell to be ready
        time.sleep(0.5)
        
        # Store session
        session_id = f"{host}_{int(time.time())}"
        active_sessions[session_id] = {
            'client': client,
            'channel': channel,
            'host': host
        }
        
        # Send connection success message
        ws.send(json.dumps({
            'type': 'connected',
            'message': f'Connected to {host}'
        }))
        
        def read_output():
            """Read output from SSH channel and send to WebSocket"""
            try:
                while True:
                    if channel.recv_ready():
                        data = channel.recv(1024).decode('utf-8', errors='ignore')
                        if data:
                            try:
                                ws.send(json.dumps({
                                    'type': 'output',
                                    'data': data
                                }))
                            except Exception as e:
                                logger.error(f"Error sending output to WebSocket: {str(e)}")
                                break
                    elif channel.exit_status_ready():
                        logger.info("SSH channel closed")
                        break
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"Error reading SSH output: {str(e)}")
                try:
                    ws.send(json.dumps({
                        'type': 'error',
                        'message': 'Connection lost'
                    }))
                except:
                    pass
        
        # Start output reading thread
        output_thread = threading.Thread(target=read_output)
        output_thread.daemon = True
        output_thread.start()
        
        # Handle incoming messages
        while True:
            try:
                message = ws.receive()
                if message is None:
                    current_app.logger.info("WebSocket connection closed by client")
                    break
                
                # Parse the message
                try:
                    data = json.loads(message)
                except json.JSONDecodeError as e:
                    current_app.logger.error(f"Invalid JSON message: {str(e)}")
                    continue
                
                message_type = data.get('type', '')
                logger.debug(f"Received message type: {message_type}")
                
                if message_type == 'input':
                    # Handle terminal input
                    input_data = data.get('data', '')
                    if input_data:
                        try:
                            channel.send(input_data)
                            logger.debug(f"Sent input to SSH: {repr(input_data)}")
                        except Exception as e:
                            logger.error(f"Error sending input to SSH: {str(e)}")
                            break
                elif message_type == 'resize':
                    # Handle terminal resize - skip for now to avoid channel issues
                    cols = data.get('cols', 80)
                    rows = data.get('rows', 24)
                    logger.debug(f"Resize requested to {cols}x{rows} (ignored to prevent channel issues)")
                    # Don't call get_pty as it can close the channel
                    pass
                else:
                    logger.warning(f"Unknown message type: {message_type}")
                    
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {str(e)}")
                # Don't break immediately, try to continue
                try:
                    ws.send(json.dumps({
                        'type': 'error',
                        'message': f'Message handling error: {str(e)}'
                    }))
                except:
                    break
        
    except Exception as e:
        logger.error(f"Error in SSH terminal WebSocket: {str(e)}")
        try:
            ws.send(json.dumps({
                'type': 'error',
                'message': str(e)
            }))
        except:
            pass
    
    finally:
        # Clean up
        if session_id and session_id in active_sessions:
            session = active_sessions[session_id]
            try:
                session['channel'].close()
                session['client'].close()
            except:
                pass
            del active_sessions[session_id]

def init_websocket(app):
    """Initialize WebSocket extension"""
    sock.init_app(app) 
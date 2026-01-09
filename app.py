"""

Manual Calendar Editor - Backend API - Fase 3.1.2

Flask server with login, authentication, and calendar management

Version: 3.1.2

Date: January 9, 2026

"""

from flask import Flask, jsonify, request, send_file, send_from_directory, redirect, session, url_for
from flask_cors import CORS
from icalendar import Calendar, Event
import os
from pathlib import Path
from datetime import datetime, timedelta
import subprocess
import logging
from dotenv import load_dotenv
import json

# ============================================================================
# CONFIGURATION
# ============================================================================

load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)

# ⭐ IMPORTANTE: Usar FLASK_SECRET_KEY (sem expor valor real!)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Configuration
REPO_PATH = os.getenv('REPO_PATH', '.')
PORT = int(os.getenv('PORT', 5000))
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'localhost,127.0.0.1')

# Credenciais de login - valores vêm de environment, não do código!
ADMIN_USERNAME = os.getenv('WEB_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('WEB_PASSWORD', 'admin123')

# File paths
IMPORT_CALENDAR_PATH = os.path.join(REPO_PATH, 'import_calendar.ics')
MASTER_CALENDAR_PATH = os.path.join(REPO_PATH, 'master_calendar.ics')
MANUAL_CALENDAR_PATH = os.path.join(REPO_PATH, 'manual_calendar.ics')
SYNC_SCRIPT_PATH = os.path.join(REPO_PATH, 'sync_calendars.py')

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(REPO_PATH, 'sync.log')),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def log_info(msg):
    """Log info message"""
    logger.info(msg)
    print(f"[INFO] {msg}")

def log_error(msg):
    """Log error message"""
    logger.error(msg)
    print(f"[ERROR] {msg}")

def file_exists(filepath):
    """Check if file exists"""
    return os.path.isfile(filepath)

def is_authenticated():
    """Check if user is authenticated"""
    return session.get('authenticated', False)

def read_ics_file(filepath):
    """Read and parse ICS file"""
    try:
        if not file_exists(filepath):
            return None
        
        with open(filepath, 'rb') as f:
            cal = Calendar.from_ical(f.read())
            events = []
            
            for component in cal.walk():
                if component.name == "VEVENT":
                    event = {
                        'uid': str(component.get('uid', '')),
                        'summary': str(component.get('summary', '')),
                        'dtstart': component.get('dtstart'),
                        'dtend': component.get('dtend'),
                        'description': str(component.get('description', '')),
                        'categories': str(component.get('categories', '')),
                        'status': str(component.get('status', 'CONFIRMED'))
                    }
                    
                    # Convert dates to strings
                    if event['dtstart']:
                        event['dtstart'] = event['dtstart'].dt.isoformat() if hasattr(event['dtstart'].dt, 'isoformat') else str(event['dtstart'].dt)
                    if event['dtend']:
                        event['dtend'] = event['dtend'].dt.isoformat() if hasattr(event['dtend'].dt, 'isoformat') else str(event['dtend'].dt)
                    
                    events.append(event)
            
            return events
    
    except Exception as e:
        log_error(f"Error reading ICS file {filepath}: {str(e)}")
        return None

def save_manual_events(events):
    """Save manual events to manual_calendar.ics"""
    try:
        cal = Calendar()
        cal.add('prodid', '-//Rental Manual Calendar//PT')
        cal.add('version', '2.0')
        cal.add('calscale', 'GREGORIAN')
        cal.add('x-wr-calname', 'Manual Calendar Events')
        cal.add('x-wr-timezone', 'Europe/Lisbon')
        
        for event_data in events:
            event = Event()
            event.add('summary', event_data.get('summary', 'Manual Event'))
            event.add('dtstart', event_data.get('dtstart'))
            event.add('dtend', event_data.get('dtend'))
            event.add('uid', event_data.get('uid', f"manual-{datetime.now().timestamp()}@rental-calendar.com"))
            event.add('categories', event_data.get('categories', 'MANUAL'))
            event.add('description', event_data.get('description', ''))
            event.add('status', event_data.get('status', 'CONFIRMED'))
            event.add('transp', 'TRANSPARENT')
            event.add('created', datetime.now())
            
            cal.add_component(event)
        
        # Write to file
        with open(MANUAL_CALENDAR_PATH, 'wb') as f:
            f.write(cal.to_ical())
        
        log_info(f"Saved {len(events)} manual events to {MANUAL_CALENDAR_PATH}")
        return True
    
    except Exception as e:
        log_error(f"Error saving manual events: {str(e)}")
        return False

# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/')
def index():
    """Home - Redireciona para /login se não autenticado"""
    if is_authenticated():
        return redirect(url_for('manual_calendar'))
    else:
        return redirect(url_for('login_page'))

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """Página de login"""
    # Se já autenticado, ir para manual_calendar
    if is_authenticated():
        return redirect(url_for('manual_calendar'))
    
    if request.method == 'POST':
        # Login POST - autenticar
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        # Validar credenciais
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            # ✅ Login bem-sucedido
            session['authenticated'] = True
            session['username'] = username
            session.permanent = True
            app.permanent_session_lifetime = timedelta(hours=24)
            
            log_info(f"✅ User '{username}' logged in successfully")
            
            # ⭐ Redirecionar para /manual_calendar
            return redirect(url_for('manual_calendar'))
        else:
            # ❌ Login falhou
            log_error(f"❌ Failed login attempt for user '{username}'")
            return login_html(error="Utilizador ou password incorretos"), 401
    
    # GET - mostrar página de login
    return login_html()

@app.route('/logout')
def logout():
    """Logout - Limpar sessão e ir para login"""
    username = session.get('username', 'unknown')
    session.clear()
    
    log_info(f"User '{username}' logged out")
    
    return redirect(url_for('login_page'))

# ============================================================================
# PROTECTED ROUTES
# ============================================================================

@app.route('/manual_calendar')
@app.route('/manual_calendar.html')
def manual_calendar():
    """Página principal - protegida por autenticação"""
    # ⭐ Verificar autenticação
    if not is_authenticated():
        return redirect(url_for('login_page'))
    
    try:
        static_path = os.path.join(os.path.dirname(__file__), 'static', 'manual_calendar.html')
        if os.path.exists(static_path):
            return send_file(static_path)
        else:
            return jsonify({
                'status': 'error',
                'message': 'HTML file not found at /static/manual_calendar.html'
            }), 404
    except Exception as e:
        log_error(f"Error serving manual_calendar: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files - protegido por autenticação"""
    # ⭐ Proteger ficheiros estáticos (exceto login)
    public_files = ['login.html', 'css/login.css', 'css/style.css', 'js/login.js']
    
    if not is_authenticated() and filename not in public_files:
        return redirect(url_for('login_page'))
    
    try:
        return send_from_directory('static', filename)
    except Exception as e:
        log_info(f"Static file not found: {filename}")
        return jsonify({'status': 'error', 'message': f'File not found: {filename}'}), 404

# ============================================================================
# API ENDPOINTS (Protegidos)
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'environment': FLASK_ENV,
        'version': '3.1.2',
        'authenticated': is_authenticated()
    }), 200

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Verificar status de autenticação"""
    return jsonify({
        'authenticated': is_authenticated(),
        'username': session.get('username', None),
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/api/calendar/sync', methods=['GET', 'POST'])
def sync_calendars():
    """Execute calendar synchronization"""
    if not is_authenticated():
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        log_info("Starting calendar synchronization...")
        
        if not file_exists(SYNC_SCRIPT_PATH):
            return jsonify({
                'status': 'error',
                'message': f'Sync script not found: {SYNC_SCRIPT_PATH}'
            }), 404
        
        result = subprocess.run(
            [f'python {SYNC_SCRIPT_PATH}'],
            shell=True,
            cwd=REPO_PATH,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            log_error(f"Sync script error: {result.stderr}")
            return jsonify({
                'status': 'error',
                'message': 'Synchronization failed',
                'error': result.stderr
            }), 500
        
        log_info("Calendar synchronization completed successfully")
        
        return jsonify({
            'status': 'success',
            'message': 'Synchronization completed',
            'timestamp': datetime.now().isoformat()
        }), 200
    
    except subprocess.TimeoutExpired:
        log_error("Sync script timeout")
        return jsonify({'status': 'error', 'message': 'Synchronization timeout'}), 500
    
    except Exception as e:
        log_error(f"Sync error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/calendar/master', methods=['GET'])
def load_master_calendar():
    """Load master_calendar.ics"""
    if not is_authenticated():
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        if not file_exists(MASTER_CALENDAR_PATH):
            return jsonify({
                'status': 'error',
                'message': 'Master calendar not found',
                'events': []
            }), 404
        
        events = read_ics_file(MASTER_CALENDAR_PATH)
        
        return jsonify({
            'status': 'success',
            'file': 'master_calendar.ics',
            'events': events or [],
            'count': len(events) if events else 0,
            'timestamp': datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        log_error(f"Error loading master calendar: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'events': []
        }), 500

@app.route('/api/calendar/import', methods=['GET'])
def load_import_calendar():
    """Load import_calendar.ics"""
    if not is_authenticated():
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        if not file_exists(IMPORT_CALENDAR_PATH):
            return jsonify({
                'status': 'error',
                'message': 'Import calendar not found',
                'events': []
            }), 404
        
        events = read_ics_file(IMPORT_CALENDAR_PATH)
        
        return jsonify({
            'status': 'success',
            'file': 'import_calendar.ics',
            'events': events or [],
            'count': len(events) if events else 0,
            'timestamp': datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        log_error(f"Error loading import calendar: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'events': []
        }), 500

@app.route('/api/calendar/manual', methods=['GET'])
def load_manual_calendar():
    """Load manual_calendar.ics"""
    if not is_authenticated():
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        if not file_exists(MANUAL_CALENDAR_PATH):
            return jsonify({
                'status': 'success',
                'file': 'manual_calendar.ics',
                'events': [],
                'count': 0,
                'message': 'No manual events yet',
                'timestamp': datetime.now().isoformat()
            }), 200
        
        events = read_ics_file(MANUAL_CALENDAR_PATH)
        
        return jsonify({
            'status': 'success',
            'file': 'manual_calendar.ics',
            'events': events or [],
            'count': len(events) if events else 0,
            'timestamp': datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        log_error(f"Error loading manual calendar: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'events': []
        }), 500

@app.route('/api/calendar/save-manual', methods=['POST'])
def save_manual_calendar():
    """Save manual events"""
    if not is_authenticated():
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        
        if not data or 'events' not in data:
            return jsonify({
                'status': 'error',
                'message': 'No events provided'
            }), 400
        
        events = data['events']
        
        # Validate events
        if not isinstance(events, list):
            return jsonify({
                'status': 'error',
                'message': 'Events must be a list'
            }), 400
        
        # Save events to ICS file
        success = save_manual_events(events)
        
        if not success:
            return jsonify({
                'status': 'error',
                'message': 'Failed to save events'
            }), 500
        
        return jsonify({
            'status': 'success',
            'message': 'Manual events saved',
            'events_saved': len(events),
            'timestamp': datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        log_error(f"Error saving manual calendar: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/calendar/status', methods=['GET'])
def calendar_status():
    """Get status of calendar files"""
    if not is_authenticated():
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        status = {
            'import_calendar': {
                'exists': file_exists(IMPORT_CALENDAR_PATH),
                'path': IMPORT_CALENDAR_PATH
            },
            'master_calendar': {
                'exists': file_exists(MASTER_CALENDAR_PATH),
                'path': MASTER_CALENDAR_PATH
            },
            'manual_calendar': {
                'exists': file_exists(MANUAL_CALENDAR_PATH),
                'path': MANUAL_CALENDAR_PATH
            },
            'sync_script': {
                'exists': file_exists(SYNC_SCRIPT_PATH),
                'path': SYNC_SCRIPT_PATH
            }
        }
        
        # Get file sizes if they exist
        for key in status:
            if status[key]['exists']:
                try:
                    size = os.path.getsize(status[key]['path'])
                    status[key]['size_bytes'] = size
                    status[key]['size_kb'] = round(size / 1024, 2)
                except:
                    pass
        
        return jsonify({
            'status': 'success',
            'repo_path': REPO_PATH,
            'files': status,
            'timestamp': datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        log_error(f"Error getting status: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/calendar/export', methods=['GET'])
def export_calendar():
    """Export calendar file for download"""
    if not is_authenticated():
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    
    try:
        calendar_type = request.args.get('type', 'manual')
        
        if calendar_type == 'manual':
            filepath = MANUAL_CALENDAR_PATH
        elif calendar_type == 'master':
            filepath = MASTER_CALENDAR_PATH
        elif calendar_type == 'import':
            filepath = IMPORT_CALENDAR_PATH
        else:
            return jsonify({
                'status': 'error',
                'message': 'Invalid calendar type'
            }), 400
        
        if not file_exists(filepath):
            return jsonify({
                'status': 'error',
                'message': f'{calendar_type} calendar not found'
            }), 404
        
        return send_file(filepath, as_attachment=True, download_name=f'{calendar_type}_calendar.ics')
    
    except Exception as e:
        log_error(f"Error exporting calendar: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'status': 'error',
        'message': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors"""
    return jsonify({
        'status': 'error',
        'message': 'Internal server error'
    }), 500

# ============================================================================
# HTML TEMPLATES
# ============================================================================

def login_html(error=None):
    """Página de login HTML"""
    error_msg = f'<div class="error-message">{error}</div>' if error else ''
    
    return f'''
    <!DOCTYPE html>
    <html lang="pt">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🔐 Login - Calendar Management</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }}
            
            .login-container {{
                background: white;
                border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
                padding: 40px;
                width: 100%;
                max-width: 400px;
            }}
            
            h1 {{
                text-align: center;
                color: #333;
                margin-bottom: 10px;
                font-size: 28px;
            }}
            
            .subtitle {{
                text-align: center;
                color: #666;
                margin-bottom: 30px;
                font-size: 14px;
            }}
            
            .error-message {{
                background: #fee;
                border: 1px solid #fcc;
                border-radius: 6px;
                color: #c33;
                padding: 12px;
                margin-bottom: 20px;
                font-size: 14px;
            }}
            
            .form-group {{
                margin-bottom: 20px;
            }}
            
            label {{
                display: block;
                color: #333;
                font-weight: 500;
                margin-bottom: 8px;
                font-size: 14px;
            }}
            
            input {{
                width: 100%;
                padding: 12px;
                border: 1px solid #ddd;
                border-radius: 6px;
                font-size: 14px;
                transition: border-color 0.3s;
            }}
            
            input:focus {{
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }}
            
            button {{
                width: 100%;
                padding: 12px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s;
            }}
            
            button:hover {{
                transform: translateY(-2px);
            }}
            
            button:active {{
                transform: translateY(0);
            }}
        </style>
    </head>
    <body>
        <div class="login-container">
            <h1>🔐 Login</h1>
            <p class="subtitle">Calendar Management System</p>
            
            {error_msg}
            
            <form method="POST">
                <div class="form-group">
                    <label for="username">Utilizador</label>
                    <input type="text" id="username" name="username" required autofocus>
                </div>
                
                <div class="form-group">
                    <label for="password">Password</label>
                    <input type="password" id="password" name="password" required>
                </div>
                
                <button type="submit">Entrar →</button>
            </form>
        </div>
    </body>
    </html>
    '''

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    log_info(f"Starting Flask server on port {PORT}")
    log_info(f"Environment: {FLASK_ENV}")
    log_info(f"Authentication: ENABLED")
    log_info(f"Secret Key: {'Custom' if os.getenv('FLASK_SECRET_KEY') else 'Default (DEV ONLY)'}")
    log_info(f"Repository Path: {REPO_PATH}")
    
    # Create log file if it doesn't exist
    log_file = os.path.join(REPO_PATH, 'sync.log')
    if not os.path.exists(log_file):
        Path(log_file).touch()
    
    # Create static directory if it doesn't exist
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)
        log_info(f"Created static directory: {static_dir}")
    
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=(FLASK_ENV == 'development')
    )

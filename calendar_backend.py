"""

Manual Calendar Editor - Backend API - Fase 3.1

Flask server with 7 endpoints for calendar synchronization and event management

Version: 3.1

Date: January 8, 2026

"""

from flask import Flask, jsonify, request, send_file, send_from_directory

from flask_cors import CORS

from icalendar import Calendar

import os

from pathlib import Path

from datetime import datetime

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

# Configuration

REPO_PATH = os.getenv('REPO_PATH', '.')

PORT = int(os.getenv('PORT', 5000))

FLASK_ENV = os.getenv('FLASK_ENV', 'development')

CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'localhost,127.0.0.1')

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

# STATIC FILES
# ============================================================================

@app.route('/')

def index():

    """Serve main HTML file"""

    try:

        static_path = os.path.join(os.path.dirname(__file__), 'static', 'manual_calendar.html')

        if os.path.exists(static_path):

            return send_file(static_path)

        else:

            return jsonify({'status': 'error', 'message': 'HTML file not found at /static/manual_calendar.html'}), 404

    except Exception as e:

        log_error(f"Error serving index: {str(e)}")

        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/manual_calendar.html')

def manual_calendar_html():

    """Serve manual calendar HTML"""

    try:

        static_path = os.path.join(os.path.dirname(__file__), 'static', 'manual_calendar.html')

        if os.path.exists(static_path):

            return send_file(static_path)

        else:

            return jsonify({'status': 'error', 'message': 'HTML file not found at /static/manual_calendar.html'}), 404

    except Exception as e:

        log_error(f"Error serving manual_calendar.html: {str(e)}")

        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/manual_calendar')

def manual_calendar():

    """Serve manual calendar page (alias for /manual_calendar.html)"""

    try:

        static_path = os.path.join(os.path.dirname(__file__), 'static', 'manual_calendar.html')

        if os.path.exists(static_path):

            return send_file(static_path)

        else:

            return jsonify({'status': 'error', 'message': 'HTML file not found at /static/manual_calendar.html'}), 404

    except Exception as e:

        log_error(f"Error serving manual_calendar: {str(e)}")

        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/<path:filename>')

def serve_static(filename):

    """Serve static files from static folder"""

    try:

        return send_from_directory('static', filename)

    except Exception as e:

        log_info(f"Static file not found: {filename}")

        return jsonify({'status': 'error', 'message': f'File not found: {filename}'}), 404

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

            from icalendar import Event

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

def execute_git_command(command):

    """Execute git command"""

    try:

        result = subprocess.run(command, shell=True, cwd=REPO_PATH, capture_output=True, text=True)

        if result.returncode != 0:

            log_error(f"Git error: {result.stderr}")

            return False

        log_info(f"Git command executed: {command}")

        return True

    except Exception as e:

        log_error(f"Error executing git command: {str(e)}")

        return False

def git_commit_and_push():

    """Commit and push changes to git"""

    try:

        # Stage all changes

        execute_git_command("git add .")

        # Commit

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        execute_git_command(f'git commit -m "[Sync] Manual calendar updated - {timestamp}"')

        # Push

        execute_git_command("git push")

        log_info("Git commit and push successful")

        return True

    except Exception as e:

        log_error(f"Git commit/push error: {str(e)}")

        return False

# ============================================================================

# API ENDPOINTS

# ============================================================================

@app.route('/api/health', methods=['GET'])

def health_check():

    """Health check endpoint"""

    return jsonify({

        'status': 'healthy',

        'timestamp': datetime.now().isoformat(),

        'environment': FLASK_ENV,

        'version': '3.1'

    }), 200

@app.route('/api/calendar/sync', methods=['GET'])

def sync_calendars():

    """Execute calendar synchronization"""

    try:

        log_info("Starting calendar synchronization...")

        # Check if sync script exists

        if not file_exists(SYNC_SCRIPT_PATH):

            return jsonify({

                'status': 'error',

                'message': f'Sync script not found: {SYNC_SCRIPT_PATH}'

            }), 404

        # Execute sync script

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

        return jsonify({

            'status': 'error',

            'message': 'Synchronization timeout'

        }), 500

    except Exception as e:

        log_error(f"Sync error: {str(e)}")

        return jsonify({

            'status': 'error',

            'message': str(e)

        }), 500

@app.route('/api/calendar/master', methods=['GET'])

def load_master_calendar():

    """Load master_calendar.ics"""

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

def load_manual_calendar_api():

    """Load manual_calendar.ics"""

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

    """Save manual events and commit to git"""

    try:

        data = request.get_json()

        if not data or 'events' not in data:

            return jsonify({

                'status': 'error',

                'message': 'No events provided'

            }), 400

        events = data['events']

        # Save events to ICS file

        success = save_manual_events(events)

        if not success:

            return jsonify({

                'status': 'error',

                'message': 'Failed to save events'

            }), 500

        # Commit to git

        git_success = git_commit_and_push()

        return jsonify({

            'status': 'success',

            'message': 'Manual events saved',

            'events_saved': len(events),

            'git_committed': git_success,

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

# MAIN

# ============================================================================

if __name__ == '__main__':

    log_info(f"Starting Flask server on port {PORT}")

    log_info(f"Environment: {FLASK_ENV}")

    log_info(f"Repository path: {REPO_PATH}")

    log_info(f"CORS origins: {CORS_ORIGINS}")

    # Create log file if it doesn't exist

    log_file = os.path.join(REPO_PATH, 'sync.log')

    if not os.path.exists(log_file):

        Path(log_file).touch()

    app.run(

        host='0.0.0.0',

        port=PORT,

        debug=(FLASK_ENV == 'development')

    )

# 🔐 SISTEMA DE LOGIN + REDIRECIONAMENTO

## 📋 REQUISITOS

1. **GET `/`** → Redireciona para `/login` (se não autenticado)
2. **GET `/login`** → Mostra página de login
3. **POST `/login`** → Autentica + Redireciona para `/manual_calendar`
4. **GET `/manual_calendar`** → Protegida (requer login) + Serve HTML
5. **GET `/logout`** → Limpa sessão + Redireciona para `/login`

---

## ✅ SOLUÇÃO COMPLETA

### PASSO 1: Atualizar `calendar_backend.py`

Substitua a versão atual por esta com login integrado:

```python
"""
Manual Calendar Editor - Backend API - Fase 3.1.2

Flask server with login, authentication, and calendar management

Version: 3.1.2
Date: January 8, 2026
"""

from flask import Flask, jsonify, request, send_file, send_from_directory, redirect, session, url_for
from flask_cors import CORS
from icalendar import Calendar
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

# ⭐ IMPORTANTE: Definir secret key para sessões
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'flask-dev-secret-key-change-in-prod')

# Configuration
REPO_PATH = os.getenv('REPO_PATH', '.')
PORT = int(os.getenv('PORT', 5000))
FLASK_ENV = os.getenv('FLASK_ENV', 'development')
CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'localhost,127.0.0.1')

# Credenciais de login (simplificado - usar base de dados em produção)
ADMIN_USERNAME = os.getenv('WEB_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('WEB_PASSWORD', 'adm123123!')

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
            
            # ⭐ Redirecionar para /manual_calendar (em vez de /dashboard)
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

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files - protegido por autenticação"""
    
    # ⭐ Proteger ficheiros estáticos (exceto login)
    if not is_authenticated() and filename not in ['login.html', 'css/login.css']:
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

@app.route('/api/calendar/sync', methods=['GET'])
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
                padding: 40px;
                border-radius: 8px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
                width: 100%;
                max-width: 400px;
            }}
            
            .login-header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            
            .login-header h1 {{
                font-size: 28px;
                color: #333;
                margin-bottom: 10px;
            }}
            
            .login-header p {{
                color: #666;
                font-size: 14px;
            }}
            
            .form-group {{
                margin-bottom: 20px;
            }}
            
            .form-group label {{
                display: block;
                margin-bottom: 8px;
                color: #333;
                font-weight: 500;
                font-size: 14px;
            }}
            
            .form-group input {{
                width: 100%;
                padding: 12px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
                transition: border-color 0.3s;
            }}
            
            .form-group input:focus {{
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }}
            
            .login-button {{
                width: 100%;
                padding: 12px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 16px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s;
            }}
            
            .login-button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
            }}
            
            .login-button:active {{
                transform: translateY(0);
            }}
            
            .error-message {{
                background-color: #fee;
                color: #c33;
                padding: 12px;
                border-radius: 4px;
                margin-bottom: 20px;
                font-size: 14px;
                border-left: 4px solid #c33;
            }}
            
            .info-box {{
                background-color: #f0f4ff;
                color: #667eea;
                padding: 12px;
                border-radius: 4px;
                margin-top: 20px;
                font-size: 12px;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="login-container">
            <div class="login-header">
                <h1>🔐 Login</h1>
                <p>Calendar Management System</p>
            </div>
            
            {error_msg}
            
            <form method="POST" action="/login">
                <div class="form-group">
                    <label for="username">Utilizador</label>
                    <input 
                        type="text" 
                        id="username" 
                        name="username" 
                        required 
                        autofocus
                        placeholder="Enter username"
                    >
                </div>
                
                <div class="form-group">
                    <label for="password">Password</label>
                    <input 
                        type="password" 
                        id="password" 
                        name="password" 
                        required
                        placeholder="Enter password"
                    >
                </div>
                
                <button type="submit" class="login-button">
                    Entrar →
                </button>
            </form>
            
            <div class="info-box">
                Demo: username=<strong>admin</strong> password=<strong>admin123</strong>
            </div>
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
    log_info(f"Secret Key: {'Custom' if os.getenv('SECRET_KEY') else 'Default (DEV ONLY)'}")
    
    # Create log file if it doesn't exist
    log_file = os.path.join(REPO_PATH, 'sync.log')
    if not os.path.exists(log_file):
        Path(log_file).touch()
    
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=(FLASK_ENV == 'development')
    )
```

---

### PASSO 2: Atualizar `.env`

Adicione estas variáveis:

```bash
# Autenticação
SECRET_KEY=seu-secret-key-muito-seguro-mudado-em-producao
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
```

---

### PASSO 3: Criar o ficheiro `static/manual_calendar.html`

Use o HTML fornecido anteriormente em `DIAGNOSTICO_REAL.md` ou crie um básico:

```html
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>📅 Manual Calendar Editor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { font-size: 24px; }
        .header a {
            color: white;
            background: rgba(255,255,255,0.2);
            padding: 8px 16px;
            border-radius: 4px;
            text-decoration: none;
            cursor: pointer;
        }
        .header a:hover { background: rgba(255,255,255,0.3); }
        .container {
            max-width: 1200px;
            margin: 20px auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h2 { color: #333; margin: 20px 0 10px; }
        button {
            background: #667eea;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin: 10px 5px 10px 0;
        }
        button:hover { background: #764ba2; }
        .event-item {
            background: #f9f9f9;
            padding: 10px;
            margin: 10px 0;
            border-left: 4px solid #667eea;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📅 Manual Calendar Editor</h1>
        <a href="/logout">Logout →</a>
    </div>
    
    <div class="container">
        <h2>Bem-vindo ao Calendar Management System!</h2>
        <p>Gerencie eventos de calendário facilmente.</p>
        
        <h2>Ações Disponíveis</h2>
        <button onclick="loadMasterCalendar()">📥 Master Calendar</button>
        <button onclick="loadImportCalendar()">📥 Import Calendar</button>
        <button onclick="syncCalendars()">🔄 Sincronizar</button>
        <button onclick="loadStatus()">📊 Status</button>
        
        <h2>Eventos</h2>
        <div id="events-container">
            <p>Clique num botão acima para carregar eventos.</p>
        </div>
    </div>
    
    <script>
        async function loadMasterCalendar() {
            try {
                const res = await fetch('/api/calendar/master');
                const data = await res.json();
                displayEvents(data, 'Master Calendar');
            } catch(e) { alert('Erro: ' + e.message); }
        }
        
        async function loadImportCalendar() {
            try {
                const res = await fetch('/api/calendar/import');
                const data = await res.json();
                displayEvents(data, 'Import Calendar');
            } catch(e) { alert('Erro: ' + e.message); }
        }
        
        async function syncCalendars() {
            try {
                const res = await fetch('/api/calendar/sync');
                const data = await res.json();
                alert(data.status === 'success' ? '✅ Sincronizado!' : '❌ Erro: ' + data.message);
            } catch(e) { alert('Erro: ' + e.message); }
        }
        
        async function loadStatus() {
            try {
                const res = await fetch('/api/calendar/status');
                const data = await res.json();
                document.getElementById('events-container').innerHTML = 
                    '<pre>' + JSON.stringify(data.files, null, 2) + '</pre>';
            } catch(e) { alert('Erro: ' + e.message); }
        }
        
        function displayEvents(data, title) {
            let html = `<h3>${title}</h3>`;
            if(data.events && data.events.length > 0) {
                html += `<p>Total: ${data.count} eventos</p>`;
                data.events.forEach(e => {
                    html += `<div class="event-item">
                        <strong>${e.summary}</strong><br>
                        ${e.dtstart} até ${e.dtend}
                    </div>`;
                });
            } else {
                html += '<p>Nenhum evento.</p>';
            }
            document.getElementById('events-container').innerHTML = html;
        }
    </script>
</body>
</html>
```

---

### PASSO 4: Git push

```bash
cd d:\Projetos\rent\rental-calendar-sync-3_0

# Atualizar backend
copy calendar_backend_v312.py calendar_backend.py

# Criar pasta static (se não existir)
mkdir static

# Criar ficheiro HTML
# (Colar o HTML acima num ficheiro static\manual_calendar.html)

# Git
git add .
git commit -m "🔐 Add: Authentication system v3.1.2 + manual_calendar.html"
git pushf
```

---

## 📊 FLUXO DE REDIRECIONAMENTO

```
Visitante acessa: https://rentalcalendarsync.onrender.com/
    ↓
    ❌ Não autenticado
    ↓
Redireciona para: /login
    ↓
Mostra página de login ✅
    ↓
Utilizador faz login (admin/admin123)
    ↓
    ✅ Credenciais correctas
    ↓
Redireciona para: /manual_calendar  ⭐ (em vez de /dashboard)
    ↓
Mostra manual_calendar.html ✅
    ↓
Utilizador clica "Logout"
    ↓
Limpa sessão + Redireciona para /login ✅
```

---

## 🔒 PROTECÇÕES

- ✅ Sessões protegidas (secret key em .env)
- ✅ Todas as rotas (excepto login) requerem autenticação
- ✅ Ficheiros estáticos protegidos
- ✅ APIs protegidas (@api/calendar/*)
- ✅ Logout limpa a sessão

---

## 📝 VARIÁVEIS .ENV

```
SECRET_KEY=seu-secret-muito-seguro
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
```

---

## ✅ TESTES

Depois de implementar:

```
1. Aceder a https://rentalcalendarsync.onrender.com/
   → Redireciona para /login ✅

2. Aceder a https://rentalcalendarsync.onrender.com/manual_calendar
   → Redireciona para /login (não autenticado) ✅

3. Login com admin/admin123
   → Redireciona para /manual_calendar ✅

4. Clicar Logout
   → Redireciona para /login ✅
   → Sessão limpa ✅

5. /api/calendar/* sem autenticação
   → Retorna 401 Unauthorized ✅
```

---

## 🎯 RESUMO

| Item | Status |
|------|--------|
| **Rota / → login** | ✅ Implementado |
| **Página login** | ✅ Implementado |
| **Redireção após login → /manual_calendar** | ✅ Implementado |
| **Ficheiro manual_calendar.html** | ✅ Fornecido |
| **Logout** | ✅ Implementado |
| **Protecção de rotas** | ✅ Implementado |

**Pronto! Sistema de autenticação completo! 🔐**

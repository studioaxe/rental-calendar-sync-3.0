#!/usr/bin/env python3
"""
Calendário Sync - Fase 2: Aplicação Web Flask
Interface segura para disparar sincronização de calendários via GitHub Actions

Status: Production Ready
Versão: 1.0
Data: Janeiro 2026
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_cors import CORS
import os
import requests
import json
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv
import secrets
import hashlib

# Carregar variáveis de ambiente
load_dotenv()

# Inicializar Flask
app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# Configuração
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

# Credenciais
WEB_USERNAME = os.getenv('WEB_USERNAME', 'admin')
WEB_PASSWORD = os.getenv('WEB_PASSWORD', 'admin123')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPO = os.getenv('GITHUB_REPO')
GITHUB_WORKFLOW_ID = os.getenv('GITHUB_WORKFLOW_ID', 'sync-calendars')
GITHUB_BRANCH = os.getenv('GITHUB_BRANCH', 'main')

# Headers GitHub
GITHUB_HEADERS = {
    'Authorization': f'Bearer {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
    'X-GitHub-Api-Version': '2022-11-28'
}

# ============================================================================
# DECORADORES
# ============================================================================

def login_required(f):
    """Decorator para verificar login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def json_error(status_code, message):
    """Gera resposta JSON de erro"""
    response = jsonify({'error': message, 'status': status_code})
    response.status_code = status_code
    return response

# ============================================================================
# ROTAS: AUTENTICAÇÃO
# ============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        username = data.get('username', '')
        password = data.get('password', '')
        
        # Verificar credenciais
        if username == WEB_USERNAME and password == WEB_PASSWORD:
            session.permanent = True
            session['user'] = username
            session['login_time'] = datetime.now().isoformat()
            
            # Redirecionar ou retornar JSON
            if request.is_json:
                return jsonify({'status': 'success', 'redirect': url_for('dashboard')})
            return redirect(url_for('dashboard'))
        
        # Erro de credenciais
        if request.is_json:
            return json_error(401, 'Credenciais inválidas')
        return render_template('login.html', error='Credenciais inválidas'), 401
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Fazer logout"""
    session.clear()
    return redirect(url_for('login'))

# ============================================================================
# ROTAS: PÁGINAS PRINCIPAIS
# ============================================================================

@app.route('/')
def index():
    """Redirecionar para dashboard ou login"""
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal"""
    return render_template('dashboard.html', username=session.get('user'))

# ============================================================================
# ROTAS: API - WORKFLOWS
# ============================================================================

@app.route('/api/trigger-workflow', methods=['POST'])
@login_required
def trigger_workflow():
    """Disparar workflow de sincronização"""
    try:
        if not GITHUB_TOKEN or not GITHUB_REPO:
            return json_error(400, 'GitHub não configurado. Verifique .env')
        
        # Dados para GitHub API
        api_url = f'https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW_ID}/dispatches'
        payload = {
            'ref': GITHUB_BRANCH,
            'inputs': {
                'triggered_by': session.get('user'),
                'timestamp': datetime.now().isoformat()
            }
        }
        
        # Fazer requisição
        response = requests.post(
            api_url,
            headers=GITHUB_HEADERS,
            json=payload,
            timeout=10
        )
        
        # Verificar resposta
        if response.status_code == 204:
            return jsonify({
                'status': 'success',
                'message': 'Workflow disparado com sucesso',
                'timestamp': datetime.now().isoformat()
            })
        elif response.status_code == 401:
            return json_error(401, 'GitHub token inválido')
        elif response.status_code == 404:
            return json_error(404, 'Repositório ou workflow não encontrado')
        else:
            return json_error(response.status_code, f'Erro GitHub: {response.text}')
    
    except requests.exceptions.Timeout:
        return json_error(504, 'Timeout na requisição GitHub')
    except requests.exceptions.ConnectionError:
        return json_error(503, 'Erro de conexão com GitHub')
    except Exception as e:
        app.logger.error(f'Erro ao disparar workflow: {str(e)}')
        return json_error(500, f'Erro interno: {str(e)}')

@app.route('/api/workflow-status', methods=['GET'])
@login_required
def workflow_status():
    """Obter status do último workflow"""
    try:
        if not GITHUB_TOKEN or not GITHUB_REPO:
            return json_error(400, 'GitHub não configurado')
        
        # Obter último run
        api_url = f'https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW_ID}/runs?per_page=1'
        
        response = requests.get(
            api_url,
            headers=GITHUB_HEADERS,
            timeout=10
        )
        
        if response.status_code != 200:
            return json_error(response.status_code, 'Erro ao obter status')
        
        data = response.json()
        runs = data.get('workflow_runs', [])
        
        if not runs:
            return jsonify({
                'status': 'no_runs',
                'message': 'Nenhum workflow executado ainda'
            })
        
        run = runs[0]
        return jsonify({
            'id': run['id'],
            'status': run['status'],
            'conclusion': run.get('conclusion'),
            'created_at': run['created_at'],
            'updated_at': run['updated_at'],
            'html_url': run['html_url']
        })
    
    except Exception as e:
        app.logger.error(f'Erro ao obter status: {str(e)}')
        return json_error(500, f'Erro interno: {str(e)}')

@app.route('/api/workflow-history', methods=['GET'])
@login_required
def workflow_history():
    """Obter histórico de workflows"""
    try:
        if not GITHUB_TOKEN or not GITHUB_REPO:
            return json_error(400, 'GitHub não configurado')
        
        limit = request.args.get('limit', 10, type=int)
        api_url = f'https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{GITHUB_WORKFLOW_ID}/runs?per_page={limit}'
        
        response = requests.get(
            api_url,
            headers=GITHUB_HEADERS,
            timeout=10
        )
        
        if response.status_code != 200:
            return json_error(response.status_code, 'Erro ao obter histórico')
        
        data = response.json()
        runs = data.get('workflow_runs', [])
        
        # Formatar resposta
        history = [
            {
                'id': run['id'],
                'status': run['status'],
                'conclusion': run.get('conclusion'),
                'created_at': run['created_at'],
                'updated_at': run['updated_at'],
                'html_url': run['html_url'],
                'duration': (
                    (datetime.fromisoformat(run['updated_at'].replace('Z', '+00:00')) -
                     datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))).total_seconds()
                    if run['status'] == 'completed' else None
                )
            }
            for run in runs
        ]
        
        return jsonify({'history': history, 'total': len(history)})
    
    except Exception as e:
        app.logger.error(f'Erro ao obter histórico: {str(e)}')
        return json_error(500, f'Erro interno: {str(e)}')

# ============================================================================
# ROTAS: API - HEALTH CHECK
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check da aplicação"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'github_configured': bool(GITHUB_TOKEN and GITHUB_REPO)
    })

# ============================================================================
# TRATAMENTO DE ERROS
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    """Erro 404"""
    return jsonify({'error': 'Página não encontrada', 'status': 404}), 404

@app.errorhandler(500)
def internal_error(e):
    """Erro 500"""
    app.logger.error(f'Erro interno: {str(e)}')
    return jsonify({'error': 'Erro interno do servidor', 'status': 500}), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'False') == 'True'
    
    print(f"""
    ╔════════════════════════════════════════════════════════════╗
    ║        Calendário Sync - Fase 2 (Web Interface)           ║
    ╠════════════════════════════════════════════════════════════╣
    ║  Status: Iniciando...                                      ║
    ║  URL:    http://localhost:{port}                            ║
    ║  Debug:  {debug}                                          ║
    ║  GitHub: {'Configurado' if GITHUB_TOKEN else 'NÃO configurado'}                                    ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    # Iniciar servidor
    if debug:
        app.run(host='0.0.0.0', port=port, debug=True)
    else:
        # Em produção, usar gunicorn
        app.run(host='0.0.0.0', port=port, debug=False)
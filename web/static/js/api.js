/* ============================================================================
   Calendário Sync - API Helpers e Utilidades JavaScript
   Chamadas AJAX, manipulação DOM, event handlers
   
   Status: Production Ready
   Versão: 1.0
   Data: Janeiro 2026
   ============================================================================ */

/* ============================================================================
   API HELPERS
   ============================================================================ */

/**
 * Classe para interagir com a API do servidor
 */
class CalendarAPI {
    constructor(baseUrl = '/api') {
        this.baseUrl = baseUrl;
        this.timeout = 10000; // 10 segundos
    }

    /**
     * Fazer requisição HTTP genérica
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            },
            timeout: this.timeout
        };

        const finalOptions = { ...defaultOptions, ...options };

        try {
            const response = await fetch(url, finalOptions);

            // Parsear JSON
            let data;
            try {
                data = await response.json();
            } catch {
                data = { error: 'Invalid JSON response' };
            }

            // Verificar status HTTP
            if (!response.ok) {
                throw new Error(data.error || `HTTP ${response.status}`);
            }

            return { success: true, data };
        } catch (error) {
            return {
                success: false,
                error: error.message || 'Erro de conexão',
                status: error.status
            };
        }
    }

    /**
     * GET: Obter status do workflow
     */
    async getWorkflowStatus() {
        return this.request('/workflow-status');
    }

    /**
     * GET: Obter histórico de workflows
     */
    async getWorkflowHistory(limit = 10) {
        return this.request(`/workflow-history?limit=${limit}`);
    }

    /**
     * POST: Disparar workflow
     */
    async triggerWorkflow() {
        return this.request('/trigger-workflow', {
            method: 'POST'
        });
    }

    /**
     * GET: Health check
     */
    async healthCheck() {
        return this.request('/health');
    }
}

// Instância global da API
const api = new CalendarAPI();

/* ============================================================================
   DOM UTILITIES
   ============================================================================ */

/**
 * Utilidades para manipular DOM
 */
const DOM = {
    /**
     * Selecionar elemento por ID
     */
    byId(id) {
        return document.getElementById(id);
    },

    /**
     * Selecionar elemento por selector
     */
    query(selector) {
        return document.querySelector(selector);
    },

    /**
     * Selecionar múltiplos elementos
     */
    queryAll(selector) {
        return document.querySelectorAll(selector);
    },

    /**
     * Mostrar elemento
     */
    show(element) {
        if (typeof element === 'string') {
            element = this.byId(element);
        }
        if (element) {
            element.classList.remove('d-none');
        }
    },

    /**
     * Esconder elemento
     */
    hide(element) {
        if (typeof element === 'string') {
            element = this.byId(element);
        }
        if (element) {
            element.classList.add('d-none');
        }
    },

    /**
     * Toggle visibilidade
     */
    toggle(element) {
        if (typeof element === 'string') {
            element = this.byId(element);
        }
        if (element) {
            element.classList.toggle('d-none');
        }
    },

    /**
     * Adicionar classe
     */
    addClass(element, className) {
        if (typeof element === 'string') {
            element = this.byId(element);
        }
        if (element) {
            element.classList.add(className);
        }
    },

    /**
     * Remover classe
     */
    removeClass(element, className) {
        if (typeof element === 'string') {
            element = this.byId(element);
        }
        if (element) {
            element.classList.remove(className);
        }
    },

    /**
     * Setar texto
     */
    setText(element, text) {
        if (typeof element === 'string') {
            element = this.byId(element);
        }
        if (element) {
            element.textContent = text;
        }
    },

    /**
     * Setar HTML
     */
    setHTML(element, html) {
        if (typeof element === 'string') {
            element = this.byId(element);
        }
        if (element) {
            element.innerHTML = html;
        }
    },

    /**
     * Obter valor de input
     */
    getValue(element) {
        if (typeof element === 'string') {
            element = this.byId(element);
        }
        return element ? element.value : '';
    },

    /**
     * Setar atributo disabled
     */
    setDisabled(element, disabled = true) {
        if (typeof element === 'string') {
            element = this.byId(element);
        }
        if (element) {
            element.disabled = disabled;
        }
    }
};

/* ============================================================================
   FORMATADORES
   ============================================================================ */

/**
 * Utilidades de formatação
 */
const Format = {
    /**
     * Formatar data/hora para português
     */
    datetime(isoString) {
        if (!isoString) return '-';
        const date = new Date(isoString);
        return date.toLocaleString('pt-PT', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    },

    /**
     * Formatar data simples
     */
    date(isoString) {
        if (!isoString) return '-';
        const date = new Date(isoString);
        return date.toLocaleDateString('pt-PT', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        });
    },

    /**
     * Formatar hora simples
     */
    time(isoString) {
        if (!isoString) return '-';
        const date = new Date(isoString);
        return date.toLocaleTimeString('pt-PT', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    },

    /**
     * Formatar duração em segundos
     */
    duration(seconds) {
        if (!seconds) return '-';
        const s = Math.round(seconds);
        const mins = Math.floor(s / 60);
        const secs = s % 60;
        return `${mins}m ${secs}s`;
    },

    /**
     * Formatar status para badge CSS
     */
    statusBadge(status) {
        const badges = {
            'completed': '<span class="badge bg-success">Completo</span>',
            'in_progress': '<span class="badge bg-info">Em execução</span>',
            'queued': '<span class="badge bg-warning">Enfileirado</span>',
            'failed': '<span class="badge bg-danger">Falhou</span>'
        };
        return badges[status] || `<span class="badge bg-secondary">${status}</span>`;
    }
};

/* ============================================================================
   NOTIFICAÇÕES
   ============================================================================ */

/**
 * Sistema de notificações toast-like
 */
const Notify = {
    /**
     * Criar notificação
     */
    create(message, type = 'info', duration = 3000) {
        const alertClass = {
            'success': 'alert-success',
            'error': 'alert-danger',
            'warning': 'alert-warning',
            'info': 'alert-info'
        }[type] || 'alert-info';

        const alert = document.createElement('div');
        alert.className = `alert ${alertClass} alert-dismissible fade show`;
        alert.role = 'alert';
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        // Adicionar ao DOM
        const container = document.querySelector('main') || document.body;
        container.insertBefore(alert, container.firstChild);

        // Auto-remover após duration
        if (duration > 0) {
            setTimeout(() => alert.remove(), duration);
        }

        return alert;
    },

    /**
     * Notificação sucesso
     */
    success(message, duration = 3000) {
        return this.create(message, 'success', duration);
    },

    /**
     * Notificação erro
     */
    error(message, duration = 5000) {
        return this.create(message, 'error', duration);
    },

    /**
     * Notificação aviso
     */
    warning(message, duration = 4000) {
        return this.create(message, 'warning', duration);
    },

    /**
     * Notificação info
     */
    info(message, duration = 3000) {
        return this.create(message, 'info', duration);
    }
};

/* ============================================================================
   LOADING STATES
   ============================================================================ */

/**
 * Gerenciar estados de loading
 */
const Loading = {
    /**
     * Mostrar loading em elemento
     */
    show(element) {
        if (typeof element === 'string') {
            element = DOM.byId(element);
        }
        if (element) {
            DOM.show(element);
            element.innerHTML = `
                <div class="text-center">
                    <div class="spinner-border spinner-border-sm" role="status">
                        <span class="visually-hidden">Carregando...</span>
                    </div>
                    <p class="mt-2 text-muted">Carregando...</p>
                </div>
            `;
        }
    },

    /**
     * Esconder loading
     */
    hide(element) {
        if (typeof element === 'string') {
            element = DOM.byId(element);
        }
        if (element) {
            DOM.hide(element);
            element.innerHTML = '';
        }
    },

    /**
     * Desabilitar botão com loading
     */
    button(button, loading = true) {
        if (typeof button === 'string') {
            button = DOM.byId(button);
        }
        if (!button) return;

        if (loading) {
            button.disabled = true;
            button.innerHTML = `
                <span class="spinner-border spinner-border-sm me-2" role="status">
                    <span class="visually-hidden">Carregando...</span>
                </span>
                Carregando...
            `;
        } else {
            button.disabled = false;
            button.innerHTML = button.dataset.originalText || 'Enviar';
        }
    }
};

/* ============================================================================
   VALIDAÇÃO
   ============================================================================ */

/**
 * Utilidades de validação
 */
const Validate = {
    /**
     * Validar email
     */
    email(email) {
        const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return regex.test(email);
    },

    /**
     * Validar campo obrigatório
     */
    required(value) {
        return value && value.trim().length > 0;
    },

    /**
     * Validar comprimento mínimo
     */
    minLength(value, min) {
        return value && value.length >= min;
    },

    /**
     * Validar comprimento máximo
     */
    maxLength(value, max) {
        return !value || value.length <= max;
    },

    /**
     * Validar número
     */
    number(value) {
        return !isNaN(value) && value !== '';
    }
};

/* ============================================================================
   LOCAL STORAGE HELPERS
   ============================================================================ */

/**
 * Utilidades para localStorage
 */
const Storage = {
    /**
     * Setar item
     */
    set(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch (e) {
            console.error('Erro ao guardar em localStorage:', e);
            return false;
        }
    },

    /**
     * Obter item
     */
    get(key, defaultValue = null) {
        try {
            const item = localStorage.getItem(key);
            return item ? JSON.parse(item) : defaultValue;
        } catch (e) {
            console.error('Erro ao ler de localStorage:', e);
            return defaultValue;
        }
    },

    /**
     * Remover item
     */
    remove(key) {
        try {
            localStorage.removeItem(key);
            return true;
        } catch (e) {
            console.error('Erro ao remover de localStorage:', e);
            return false;
        }
    },

    /**
     * Limpar tudo
     */
    clear() {
        try {
            localStorage.clear();
            return true;
        } catch (e) {
            console.error('Erro ao limpar localStorage:', e);
            return false;
        }
    }
};

/* ============================================================================
   INICIALIZAÇÃO
   ============================================================================ */

// Inicializar quando DOM estiver pronto
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    initializeApp();
}

function initializeApp() {
    // Setup inicial se necessário
    console.log('✓ App inicializado');
}

/* ============================================================================
   EXPORT (para uso em módulos)
   ============================================================================ */

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        CalendarAPI,
        api,
        DOM,
        Format,
        Notify,
        Loading,
        Validate,
        Storage
    };
}
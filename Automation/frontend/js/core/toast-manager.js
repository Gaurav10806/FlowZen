/**
 * ToastManager - Premium Glassmorphism Notifications
 * Replaces native alerts with beautiful, animated toasts.
 */
class ToastManager {
    constructor() {
        if (document.querySelector('.toast-container')) {
            return; // Singleton
        }

        this.container = document.createElement('div');
        this.container.className = 'toast-container';
        document.body.appendChild(this.container);

        // Inject styles directly (or could be in main.css)
        this.injectStyles();
    }

    injectStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .toast-container {
                position: fixed;
                bottom: 24px;
                right: 24px;
                display: flex;
                flex-direction: column;
                gap: 12px;
                z-index: 10000;
                pointer-events: none;
            }
            
            .toast {
                display: flex;
                align-items: center;
                width: 350px;
                padding: 16px 20px;
                background: rgba(255, 255, 255, 0.9);
                backdrop-filter: blur(12px);
                border-left: 4px solid #ccc;
                border-radius: 12px;
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
                color: #1e293b;
                font-family: 'Inter', sans-serif;
                font-size: 0.95rem;
                font-weight: 500;
                pointer-events: auto;
                opacity: 0;
                transform: translateX(100%);
                transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
                overflow: hidden;
            }
            
            .toast.visible {
                opacity: 1;
                transform: translateX(0);
            }
            
            .toast.hiding {
                opacity: 0;
                transform: translateX(20px) scale(0.95);
            }
            
            .toast-icon {
                margin-right: 16px;
                font-size: 1.25rem;
                display: flex;
                align-items: center;
            }
            
            .toast-content {
                flex: 1;
            }
            
            .toast-title {
                font-weight: 700;
                margin-bottom: 2px;
                display: block;
            }
            
            .toast-message {
                font-size: 0.85rem;
                color: #64748b;
                line-height: 1.4;
            }
            
            .toast-close {
                background: none;
                border: none;
                color: #94a3b8;
                cursor: pointer;
                padding: 4px;
                margin-left: 12px;
                transition: color 0.2s;
            }
            
            .toast-close:hover {
                color: #1e293b;
            }
            
            /* Types */
            .toast-success { border-left-color: #10b981; }
            .toast-success .toast-icon { color: #10b981; }
            
            .toast-error { border-left-color: #ef4444; }
            .toast-error .toast-icon { color: #ef4444; }
            
            .toast-warning { border-left-color: #f59e0b; }
            .toast-warning .toast-icon { color: #f59e0b; }
            
            .toast-info { border-left-color: #3b82f6; }
            .toast-info .toast-icon { color: #3b82f6; }
            
            .toast-loading { border-left-color: #6366f1; }
            .toast-loading .toast-icon { 
                color: #6366f1;
                animation: spin 1s linear infinite;
            }
            
            @keyframes spin { 100% { transform: rotate(360deg); } }
        `;
        document.head.appendChild(style);
    }

    show(type, title, message, duration = 4000) {
        // Icons map
        const icons = {
            success: 'fas fa-check-circle',
            error: 'fas fa-exclamation-circle',
            warning: 'fas fa-exclamation-triangle',
            info: 'fas fa-info-circle',
            loading: 'fas fa-spinner'
        };

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        toast.innerHTML = `
            <div class="toast-icon">
                <i class="${icons[type] || icons.info}"></i>
            </div>
            <div class="toast-content">
                <span class="toast-title">${title}</span>
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close">
                <i class="fas fa-times"></i>
            </button>
        `;

        // Close handler
        const closeBtn = toast.querySelector('.toast-close');
        closeBtn.onclick = () => this.hide(toast);

        // Safety check: ensure container exists
        if (!this.container) {
            console.error('Toast container not initialized');
            return null;
        }

        this.container.appendChild(toast);

        // Trigger reflow for animation
        requestAnimationFrame(() => {
            toast.classList.add('visible');
        });

        // Auto remove
        if (duration > 0) {
            setTimeout(() => {
                this.hide(toast);
            }, duration);
        }

        return toast;
    }

    hide(toast) {
        if (!toast || !toast.parentNode) return;

        toast.classList.remove('visible');
        toast.classList.add('hiding');

        toast.addEventListener('transitionend', () => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        });
    }

    // Quick helpers
    success(title, message) { return this.show('success', title, message); }
    error(title, message) { return this.show('error', title, message, 6000); }
    warning(title, message) { return this.show('warning', title, message); }
    info(title, message) { return this.show('info', title, message); }
    loading(title, message) { return this.show('loading', title, message, 0); }
}

// Attach to window
window.Toast = new ToastManager();

// Compatibility Adapter for EnhancedMain
window.notificationManager = {
    success: (message, options = {}) => {
        window.Toast.success(options.title || "Success", message);
    },
    error: (message, options = {}) => {
        // Handle options.actions if needed (basic support for now)
        window.Toast.error(options.title || "Error", message);
    },
    warning: (message, options = {}) => {
        window.Toast.warning(options.title || "Warning", message);
    },
    info: (message, options = {}) => {
        window.Toast.info(options.title || "Info", message);
    }
};

// Universal Toast Helper (User Requested)
window.showToast = function (message, type = "success") {
    // Map 'error' to 'error', 'success' to 'success', etc.
    // ToastManager uses .show(type, title, message)
    const titleMap = {
        "success": "Success",
        "error": "Error",
        "warning": "Warning",
        "info": "Info"
    };
    window.Toast.show(type, titleMap[type] || "Notification", message);
};

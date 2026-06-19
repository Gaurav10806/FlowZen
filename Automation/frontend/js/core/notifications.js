// Enhanced Notification System with Animations
class NotificationManager {
    constructor() {
        this.notifications = new Map();
        this.container = null;
        this.animationManager = null;
        this.maxNotifications = 5;
        this.defaultDuration = 5000;
        
        this.init();
    }
    
    init() {
        this.createContainer();
        this.setupStyles();
        
        // Initialize animation manager if available
        if (window.AnimationManager) {
            this.animationManager = new AnimationManager();
        }
    }
    
    createContainer() {
        this.container = document.createElement('div');
        this.container.className = 'toast-container';
        this.container.id = 'notification-container';
        document.body.appendChild(this.container);
    }
    
    setupStyles() {
        if (document.getElementById('notification-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            .notification-enter {
                animation: notificationSlideIn 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
            }
            
            .notification-exit {
                animation: notificationSlideOut 0.3s ease-in forwards;
            }
            
            @keyframes notificationSlideIn {
                0% {
                    opacity: 0;
                    transform: translateX(100%) scale(0.9) rotate(5deg);
                }
                100% {
                    opacity: 1;
                    transform: translateX(0) scale(1) rotate(0deg);
                }
            }
            
            @keyframes notificationSlideOut {
                0% {
                    opacity: 1;
                    transform: translateX(0) scale(1);
                    max-height: 200px;
                }
                100% {
                    opacity: 0;
                    transform: translateX(100%) scale(0.9);
                    max-height: 0;
                    margin: 0;
                    padding: 0;
                }
            }
            
            .notification-progress {
                position: absolute;
                bottom: 0;
                left: 0;
                height: 3px;
                background: currentColor;
                opacity: 0.3;
                transition: width linear;
            }
            
            .notification-icon-bounce {
                animation: iconBounce 0.6s ease-out;
            }
            
            @keyframes iconBounce {
                0%, 100% { transform: scale(1); }
                50% { transform: scale(1.2); }
            }
        `;
        document.head.appendChild(style);
    }
    
    show(message, type = 'info', options = {}) {
        const notification = this.createNotification(message, type, options);
        
        // Limit number of notifications
        if (this.notifications.size >= this.maxNotifications) {
            const oldestId = this.notifications.keys().next().value;
            this.hide(oldestId);
        }
        
        this.container.appendChild(notification.element);
        this.notifications.set(notification.id, notification);
        
        // Animate in
        requestAnimationFrame(() => {
            notification.element.classList.add('notification-enter');
            
            if (this.animationManager) {
                this.animationManager.animateToast(notification.element);
            }
        });
        
        // Auto-hide if duration is set
        if (notification.duration > 0) {
            notification.timer = setTimeout(() => {
                this.hide(notification.id);
            }, notification.duration);
            
            // Start progress bar animation
            if (notification.progressBar) {
                requestAnimationFrame(() => {
                    notification.progressBar.style.width = '0%';
                    notification.progressBar.style.transitionDuration = `${notification.duration}ms`;
                });
            }
        }
        
        return notification.id;
    }
    
    createNotification(message, type, options) {
        const id = Date.now() + Math.random();
        const duration = options.duration !== undefined ? options.duration : this.defaultDuration;
        const persistent = options.persistent || false;
        const actions = options.actions || [];
        
        const element = document.createElement('div');
        element.className = `toast ${type}`;
        element.dataset.notificationId = id;
        
        const config = this.getTypeConfig(type);
        
        element.innerHTML = `
            <div class="toast-header">
                <i class="toast-icon ${config.icon} notification-icon-bounce"></i>
                <span class="toast-title">${config.title}</span>
                ${!persistent ? '<button class="toast-close" aria-label="Close">&times;</button>' : ''}
            </div>
            <div class="toast-message">${message}</div>
            ${actions.length > 0 ? this.createActionButtons(actions, id) : ''}
            ${duration > 0 ? '<div class="notification-progress"></div>' : ''}
        `;
        
        // Setup close button
        if (!persistent) {
            const closeBtn = element.querySelector('.toast-close');
            closeBtn.addEventListener('click', () => this.hide(id));
        }
        
        // Setup action buttons
        actions.forEach((action, index) => {
            const btn = element.querySelector(`[data-action="${index}"]`);
            if (btn) {
                btn.addEventListener('click', () => {
                    action.callback();
                    if (action.closeOnClick !== false) {
                        this.hide(id);
                    }
                });
            }
        });
        
        const progressBar = element.querySelector('.notification-progress');
        
        return {
            id,
            element,
            duration,
            timer: null,
            progressBar,
            type
        };
    }
    
    createActionButtons(actions, notificationId) {
        const buttonsHtml = actions.map((action, index) => `
            <button class="btn btn-sm ${action.class || 'btn-outline-primary'}" 
                    data-action="${index}">
                ${action.icon ? `<i class="${action.icon}"></i> ` : ''}
                ${action.text}
            </button>
        `).join(' ');
        
        return `<div class="toast-actions mt-2">${buttonsHtml}</div>`;
    }
    
    getTypeConfig(type) {
        const configs = {
            success: {
                title: 'Success',
                icon: 'fas fa-check-circle'
            },
            error: {
                title: 'Error',
                icon: 'fas fa-exclamation-circle'
            },
            warning: {
                title: 'Warning',
                icon: 'fas fa-exclamation-triangle'
            },
            info: {
                title: 'Info',
                icon: 'fas fa-info-circle'
            },
            loading: {
                title: 'Loading',
                icon: 'fas fa-spinner fa-spin'
            }
        };
        
        return configs[type] || configs.info;
    }
    
    hide(id) {
        const notification = this.notifications.get(id);
        if (!notification) return;
        
        // Clear timer
        if (notification.timer) {
            clearTimeout(notification.timer);
        }
        
        // Animate out
        notification.element.classList.add('notification-exit');
        
        setTimeout(() => {
            if (notification.element.parentNode) {
                notification.element.parentNode.removeChild(notification.element);
            }
            this.notifications.delete(id);
        }, 300);
    }
    
    hideAll() {
        this.notifications.forEach((notification, id) => {
            this.hide(id);
        });
    }
    
    // Convenience methods
    success(message, options = {}) {
        return this.show(message, 'success', options);
    }
    
    error(message, options = {}) {
        return this.show(message, 'error', options);
    }
    
    warning(message, options = {}) {
        return this.show(message, 'warning', options);
    }
    
    info(message, options = {}) {
        return this.show(message, 'info', options);
    }
    
    loading(message, options = {}) {
        return this.show(message, 'loading', { 
            duration: 0, 
            persistent: true, 
            ...options 
        });
    }
    
    // Update existing notification
    update(id, message, type) {
        const notification = this.notifications.get(id);
        if (!notification) return;
        
        const messageElement = notification.element.querySelector('.toast-message');
        const iconElement = notification.element.querySelector('.toast-icon');
        const titleElement = notification.element.querySelector('.toast-title');
        
        if (messageElement) {
            messageElement.textContent = message;
        }
        
        if (type && type !== notification.type) {
            const config = this.getTypeConfig(type);
            
            // Update classes
            notification.element.className = `toast ${type}`;
            
            // Update icon and title
            if (iconElement) {
                iconElement.className = `toast-icon ${config.icon}`;
            }
            if (titleElement) {
                titleElement.textContent = config.title;
            }
            
            notification.type = type;
        }
    }
    
    // Show confirmation dialog
    confirm(message, options = {}) {
        return new Promise((resolve) => {
            const actions = [
                {
                    text: options.confirmText || 'Confirm',
                    class: 'btn-primary',
                    icon: 'fas fa-check',
                    callback: () => resolve(true)
                },
                {
                    text: options.cancelText || 'Cancel',
                    class: 'btn-outline-secondary',
                    icon: 'fas fa-times',
                    callback: () => resolve(false)
                }
            ];
            
            this.show(message, 'warning', {
                duration: 0,
                persistent: true,
                actions
            });
        });
    }
    
    // Show progress notification
    progress(message, options = {}) {
        const id = this.show(message, 'loading', {
            duration: 0,
            persistent: true,
            ...options
        });
        
        return {
            id,
            update: (progress, newMessage) => {
                const notification = this.notifications.get(id);
                if (notification && notification.progressBar) {
                    notification.progressBar.style.width = `${progress}%`;
                    
                    if (newMessage) {
                        this.update(id, newMessage);
                    }
                }
            },
            complete: (message) => {
                this.update(id, message || 'Complete!', 'success');
                setTimeout(() => this.hide(id), 2000);
            },
            error: (message) => {
                this.update(id, message || 'Failed!', 'error');
                setTimeout(() => this.hide(id), 3000);
            },
            hide: () => this.hide(id)
        };
    }
    
    // Cleanup
    destroy() {
        this.hideAll();
        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }
        
        const styles = document.getElementById('notification-styles');
        if (styles && styles.parentNode) {
            styles.parentNode.removeChild(styles);
        }
    }
}

// Export for use in other modules
window.NotificationManager = NotificationManager;

// Create global instance
if (!window.notifications) {
    window.notifications = new NotificationManager();
}
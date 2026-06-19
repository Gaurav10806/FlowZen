/**
 * ContextMenuManager - Custom Right-Click Menu for Canvas
 * 
 * Provides: Edit, Delete, Duplicate, Execute Node options on right-click.
 */
class ContextMenuManager {
    constructor() {
        this.menu = null;
        this.activeTarget = null;
        this.init();
    }

    init() {
        // Create Menu Element
        this.menu = document.createElement('div');
        this.menu.className = 'context-menu';
        this.menu.style.display = 'none';
        document.body.appendChild(this.menu);

        // Inject Styles
        const style = document.createElement('style');
        style.textContent = `
            .context-menu {
                position: fixed;
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
                min-width: 180px;
                z-index: 10000;
                padding: 6px;
                animation: scaleIn 0.15s ease-out;
                transform-origin: top left;
            }
            @keyframes scaleIn {
                from { opacity: 0; transform: scale(0.9); }
                to { opacity: 1; transform: scale(1); }
            }
            .context-menu-item {
                display: flex;
                align-items: center;
                gap: 10px;
                padding: 8px 12px;
                cursor: pointer;
                border-radius: 6px;
                color: #1e293b;
                font-size: 0.9rem;
                font-weight: 500;
                transition: background 0.2s;
            }
            .context-menu-item:hover {
                background: #f1f5f9;
                color: #4f46e5;
            }
            .context-menu-item i {
                width: 20px;
                text-align: center;
                color: #64748b;
            }
            .context-menu-item:hover i {
                color: #4f46e5;
            }
            .context-menu-divider {
                height: 1px;
                background: #e2e8f0;
                margin: 4px 0;
            }
            .context-menu-item.danger {
                color: #ef4444;
            }
            .context-menu-item.danger:hover {
                background: #fee2e2;
            }
            .context-menu-item.danger i {
                color: #ef4444;
            }
        `;
        document.head.appendChild(style);

        // Global Click Listener (Hide)
        document.addEventListener('click', () => this.hide());
        document.addEventListener('contextmenu', (e) => {
            if (!this.activeTarget) this.hide(); // Hide if clicking outside target
        }); // Native menu blocked only on targets
    }

    show(x, y, targetType, targetId, callbacks = {}) {
        this.menu.style.left = `${x}px`;
        this.menu.style.top = `${y}px`;

        let html = '';

        if (targetType === 'node') {
            html += `
                <div class="context-menu-item" data-action="edit">
                    <i class="fas fa-cog"></i> Edit Properties
                </div>
                <div class="context-menu-item" data-action="duplicate">
                    <i class="fas fa-clone"></i> Duplicate
                </div>
                <div class="context-menu-divider"></div>
                <div class="context-menu-item" data-action="execute">
                    <i class="fas fa-play"></i> Execute Node
                </div>
                <div class="context-menu-divider"></div>
                <div class="context-menu-item danger" data-action="delete">
                    <i class="fas fa-trash"></i> Delete
                </div>
            `;
        } else if (targetType === 'edge') {
            html += `
                <div class="context-menu-item danger" data-action="delete">
                    <i class="fas fa-cut"></i> Delete Connection
                </div>
            `;
        } else if (targetType === 'canvas') {
            html += `
                <div class="context-menu-item" data-action="paste">
                    <i class="fas fa-paste"></i> Paste
                </div>
                <div class="context-menu-item" data-action="fit">
                    <i class="fas fa-compress-arrows-alt"></i> Fit to Screen
                </div>
            `;
        }

        this.menu.innerHTML = html;
        this.menu.style.display = 'block';

        // Bind actions
        this.menu.querySelectorAll('.context-menu-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.stopPropagation();
                const action = item.dataset.action;
                if (callbacks[action]) callbacks[action](targetId);
                this.hide();
            });
        });
    }

    hide() {
        this.menu.style.display = 'none';
        this.activeTarget = null;
    }

    // Connect to Canvas (to be called from canvas.js or main.js)
    attachToNode(nodeElement, nodeId, callbacks) {
        nodeElement.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.show(e.clientX, e.clientY, 'node', nodeId, callbacks);
        });
    }
}

// Initialize
window.ContextMenu = new ContextMenuManager();

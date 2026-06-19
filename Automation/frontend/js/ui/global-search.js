/**
 * Global Search Palette (Command K)
 */
class GlobalSearch {
    constructor() {
        this.isOpen = false;
        this.container = null;
        this.input = null;
        this.results = null;
        this.commands = [
            { id: 'new-workflow', label: 'Create New Workflow', icon: 'fas fa-plus', action: () => window.app.newWorkflow() },
            { id: 'save-workflow', label: 'Save Workflow', icon: 'fas fa-save', action: () => window.app.saveWorkflow() },
            { id: 'settings', label: 'Open Settings', icon: 'fas fa-cog', action: () => window.location.href = '/settings/' },
            { id: 'dashboard', label: 'Go to Dashboard', icon: 'fas fa-home', action: () => window.location.href = '/dashboard/' },
            { id: 'toggle-theme', label: 'Toggle Theme', icon: 'fas fa-moon', action: () => window.app.toggleTheme() },
            { id: 'docs', label: 'Documentation', icon: 'fas fa-book', action: () => window.open('/docs/', '_blank') }
        ];

        this.init();
    }

    init() {
        this.createUI();
        this.setupShortcuts();
    }

    createUI() {
        this.container = document.createElement('div');
        this.container.id = 'global-search-overlay';
        this.container.style.display = 'none';
        this.container.innerHTML = `
            <div class="search-modal">
                <div class="search-header">
                    <i class="fas fa-search"></i>
                    <input type="text" placeholder="Type a command or search..." autofocus>
                    <span class="esc-hint">ESC</span>
                </div>
                <div class="search-results"></div>
                <div class="search-footer">
                    <span><kbd>↑</kbd> <kbd>↓</kbd> to navigate</span>
                    <span><kbd>↵</kbd> to select</span>
                </div>
            </div>
        `;
        document.body.appendChild(this.container);

        this.input = this.container.querySelector('input');
        this.results = this.container.querySelector('.search-results');

        this.input.addEventListener('input', (e) => this.filterResults(e.target.value));
        this.container.addEventListener('click', (e) => {
            if (e.target === this.container) this.close();
        });
    }

    setupShortcuts() {
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                this.toggle();
            }
            if (e.key === 'Escape' && this.isOpen) {
                this.close();
            }
        });
    }

    toggle() {
        if (this.isOpen) this.close();
        else this.open();
    }

    open() {
        this.isOpen = true;
        this.container.style.display = 'flex';
        this.input.value = '';
        this.input.focus();
        this.filterResults('');
    }

    close() {
        this.isOpen = false;
        this.container.style.display = 'none';
    }

    filterResults(query) {
        const q = query.toLowerCase();
        // search nodes if window.NODE_REGISTRY exists
        const nodeResults = [];
        if (window.NODE_REGISTRY) {
            Object.values(window.NODE_REGISTRY).forEach(node => {
                if (node.label.toLowerCase().includes(q) || node.type.includes(q)) {
                    nodeResults.push({
                        id: `add-node-${node.type}`,
                        label: `Add Node: ${node.label}`,
                        icon: node.icon || 'fas fa-cube',
                        action: () => {
                            // Assuming Add Node logic
                            if (window.advancedCanvas) window.advancedCanvas.addNode(node.type, { x: 100, y: 100 });
                        }
                    });
                }
            });
        }

        const filteredCommands = this.commands.filter(c => c.label.toLowerCase().includes(q));
        const allResults = [...filteredCommands, ...nodeResults].slice(0, 10);

        this.renderResults(allResults);
    }

    renderResults(items) {
        this.results.innerHTML = '';
        if (items.length === 0) {
            this.results.innerHTML = '<div class="no-results">No results found</div>';
            return;
        }

        items.forEach((item, index) => {
            const el = document.createElement('div');
            el.className = 'search-item';
            el.innerHTML = `<i class="${item.icon}"></i> <span>${item.label}</span>`;
            el.onclick = () => {
                item.action();
                this.close();
            };
            this.results.appendChild(el);
        });
    }
}

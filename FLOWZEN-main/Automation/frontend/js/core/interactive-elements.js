// Interactive UI Elements - Tooltips, Dropdowns, Modals, Progress
class InteractiveElements {
    constructor() {
        this.tooltips = new Map();
        this.dropdowns = new Map();
        this.progressBars = new Map();
        
        this.init();
    }
    
    init() {
        this.setupStyles();
        this.setupGlobalEvents();
    }
    
    setupStyles() {
        const style = document.createElement('style');
        style.textContent = `
            /* Tooltip Styles */
            .tooltip {
                position: absolute;
                background: #1f2937;
                color: white;
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
                white-space: nowrap;
                z-index: 10000;
                opacity: 0;
                visibility: hidden;
                transform: translateY(-5px);
                transition: all 0.2s ease;
                pointer-events: none;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            }
            
            .tooltip::after {
                content: '';
                position: absolute;
                top: 100%;
                left: 50%;
                transform: translateX(-50%);
                border: 5px solid transparent;
                border-top-color: #1f2937;
            }
            
            .tooltip.show {
                opacity: 1;
                visibility: visible;
                transform: translateY(0);
            }
            
            .tooltip.bottom::after {
                top: -10px;
                border-top-color: transparent;
                border-bottom-color: #1f2937;
            }
            
            .tooltip.left::after {
                top: 50%;
                left: 100%;
                transform: translateY(-50%);
                border-left-color: #1f2937;
                border-top-color: transparent;
            }
            
            .tooltip.right::after {
                top: 50%;
                left: -10px;
                transform: translateY(-50%);
                border-right-color: #1f2937;
                border-top-color: transparent;
            }
            
            /* Dropdown Styles */
            .dropdown {
                position: relative;
                display: inline-block;
            }
            
            .dropdown-menu {
                position: absolute;
                top: 100%;
                left: 0;
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
                min-width: 200px;
                z-index: 1000;
                opacity: 0;
                visibility: hidden;
                transform: translateY(-10px);
                transition: all 0.2s ease;
                max-height: 300px;
                overflow-y: auto;
            }
            
            .dropdown-menu.show {
                opacity: 1;
                visibility: visible;
                transform: translateY(0);
            }
            
            .dropdown-item {
                display: flex;
                align-items: center;
                padding: 12px 16px;
                color: #374151;
                text-decoration: none;
                font-size: 14px;
                cursor: pointer;
                transition: background-color 0.15s ease;
                border: none;
                background: none;
                width: 100%;
                text-align: left;
            }
            
            .dropdown-item:hover {
                background: #f3f4f6;
            }
            
            .dropdown-item:active {
                background: #e5e7eb;
            }
            
            .dropdown-item.disabled {
                color: #9ca3af;
                cursor: not-allowed;
            }
            
            .dropdown-item.disabled:hover {
                background: transparent;
            }
            
            .dropdown-item i {
                margin-right: 8px;
                width: 16px;
                text-align: center;
            }
            
            .dropdown-divider {
                height: 1px;
                background: #e5e7eb;
                margin: 4px 0;
            }
            
            /* Progress Bar Styles */
            .progress-container {
                background: #f3f4f6;
                border-radius: 10px;
                overflow: hidden;
                height: 8px;
                position: relative;
            }
            
            .progress-bar {
                height: 100%;
                background: linear-gradient(90deg, #4f46e5, #7c3aed);
                border-radius: 10px;
                transition: width 0.3s ease;
                position: relative;
                overflow: hidden;
            }
            
            .progress-bar.animated::after {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: linear-gradient(
                    90deg,
                    transparent,
                    rgba(255, 255, 255, 0.3),
                    transparent
                );
                animation: progress-shine 2s infinite;
            }
            
            @keyframes progress-shine {
                0% { transform: translateX(-100%); }
                100% { transform: translateX(100%); }
            }
            
            .progress-text {
                font-size: 12px;
                color: #6b7280;
                margin-top: 4px;
                text-align: center;
            }
            
            /* Loading Spinner */
            .spinner {
                width: 20px;
                height: 20px;
                border: 2px solid #f3f4f6;
                border-top: 2px solid #4f46e5;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                display: inline-block;
            }
            
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            
            .spinner.large {
                width: 40px;
                height: 40px;
                border-width: 4px;
            }
            
            /* Button Loading State */
            .btn-loading {
                position: relative;
                color: transparent !important;
                pointer-events: none;
            }
            
            .btn-loading::after {
                content: '';
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 16px;
                height: 16px;
                border: 2px solid transparent;
                border-top: 2px solid currentColor;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
            
            /* Skeleton Loading */
            .skeleton {
                background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
                background-size: 200px 100%;
                animation: skeleton-loading 1.5s infinite;
                border-radius: 4px;
            }
            
            @keyframes skeleton-loading {
                0% { background-position: -200px 0; }
                100% { background-position: calc(200px + 100%) 0; }
            }
            
            .skeleton-text {
                height: 16px;
                margin-bottom: 8px;
            }
            
            .skeleton-text:last-child {
                margin-bottom: 0;
                width: 60%;
            }
            
            /* Context Menu */
            .context-menu {
                position: fixed;
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
                z-index: 10000;
                opacity: 0;
                visibility: hidden;
                transform: scale(0.95);
                transition: all 0.15s ease;
                min-width: 180px;
            }
            
            .context-menu.show {
                opacity: 1;
                visibility: visible;
                transform: scale(1);
            }
            
            .context-menu-item {
                display: flex;
                align-items: center;
                padding: 10px 16px;
                color: #374151;
                font-size: 13px;
                cursor: pointer;
                transition: background-color 0.15s ease;
                border: none;
                background: none;
                width: 100%;
                text-align: left;
            }
            
            .context-menu-item:hover {
                background: #f3f4f6;
            }
            
            .context-menu-item:first-child {
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            
            .context-menu-item:last-child {
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }
            
            .context-menu-item i {
                margin-right: 10px;
                width: 14px;
                text-align: center;
                font-size: 12px;
            }
            
            .context-menu-item.danger {
                color: #ef4444;
            }
            
            .context-menu-item.danger:hover {
                background: #fef2f2;
            }
            
            /* Badge */
            .badge {
                display: inline-flex;
                align-items: center;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 600;
                border-radius: 12px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            .badge.success {
                background: #d1fae5;
                color: #065f46;
            }
            
            .badge.error {
                background: #fee2e2;
                color: #991b1b;
            }
            
            .badge.warning {
                background: #fef3c7;
                color: #92400e;
            }
            
            .badge.info {
                background: #dbeafe;
                color: #1e40af;
            }
            
            .badge.neutral {
                background: #f3f4f6;
                color: #374151;
            }
        `;
        document.head.appendChild(style);
    }
    
    setupGlobalEvents() {
        // Close dropdowns and context menus on outside click
        document.addEventListener('click', (e) => {
            this.closeAllDropdowns(e);
            this.closeContextMenu();
        });
        
        // Handle tooltip triggers
        document.addEventListener('mouseenter', (e) => {
            if (e.target.hasAttribute('data-tooltip')) {
                this.showTooltip(e.target);
            }
        }, true);
        
        document.addEventListener('mouseleave', (e) => {
            if (e.target.hasAttribute('data-tooltip')) {
                this.hideTooltip(e.target);
            }
        }, true);
        
        // Prevent context menu on right click for custom handling
        document.addEventListener('contextmenu', (e) => {
            if (e.target.hasAttribute('data-context-menu')) {
                e.preventDefault();
                this.showContextMenu(e, e.target);
            }
        });
    }
    
    // Tooltip Management
    showTooltip(element) {
        const text = element.getAttribute('data-tooltip');
        const position = element.getAttribute('data-tooltip-position') || 'top';
        
        if (!text) return;
        
        const tooltip = document.createElement('div');
        tooltip.className = `tooltip ${position}`;
        tooltip.textContent = text;
        
        document.body.appendChild(tooltip);
        
        const rect = element.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();
        
        let left, top;
        
        switch (position) {
            case 'bottom':
                left = rect.left + (rect.width - tooltipRect.width) / 2;
                top = rect.bottom + 10;
                break;
            case 'left':
                left = rect.left - tooltipRect.width - 10;
                top = rect.top + (rect.height - tooltipRect.height) / 2;
                break;
            case 'right':
                left = rect.right + 10;
                top = rect.top + (rect.height - tooltipRect.height) / 2;
                break;
            default: // top
                left = rect.left + (rect.width - tooltipRect.width) / 2;
                top = rect.top - tooltipRect.height - 10;
        }
        
        tooltip.style.left = `${Math.max(10, left)}px`;
        tooltip.style.top = `${Math.max(10, top)}px`;
        
        requestAnimationFrame(() => {
            tooltip.classList.add('show');
        });
        
        this.tooltips.set(element, tooltip);
    }
    
    hideTooltip(element) {
        const tooltip = this.tooltips.get(element);
        if (tooltip) {
            tooltip.classList.remove('show');
            setTimeout(() => {
                if (tooltip.parentNode) {
                    tooltip.parentNode.removeChild(tooltip);
                }
            }, 200);
            this.tooltips.delete(element);
        }
    }
    
    // Dropdown Management
    createDropdown(trigger, items, options = {}) {
        const dropdown = document.createElement('div');
        dropdown.className = 'dropdown-menu';
        
        items.forEach(item => {
            if (item.divider) {
                const divider = document.createElement('div');
                divider.className = 'dropdown-divider';
                dropdown.appendChild(divider);
            } else {
                const menuItem = document.createElement('button');
                menuItem.className = `dropdown-item ${item.disabled ? 'disabled' : ''}`;
                menuItem.innerHTML = `
                    ${item.icon ? `<i class="${item.icon}"></i>` : ''}
                    ${item.label}
                `;
                
                if (!item.disabled && item.handler) {
                    menuItem.addEventListener('click', (e) => {
                        e.stopPropagation();
                        item.handler();
                        this.hideDropdown(trigger);
                    });
                }
                
                dropdown.appendChild(menuItem);
            }
        });
        
        document.body.appendChild(dropdown);
        this.dropdowns.set(trigger, dropdown);
        
        return dropdown;
    }
    
    showDropdown(trigger) {
        const dropdown = this.dropdowns.get(trigger);
        if (!dropdown) return;
        
        const rect = trigger.getBoundingClientRect();
        dropdown.style.left = `${rect.left}px`;
        dropdown.style.top = `${rect.bottom + 5}px`;
        
        requestAnimationFrame(() => {
            dropdown.classList.add('show');
        });
    }
    
    hideDropdown(trigger) {
        const dropdown = this.dropdowns.get(trigger);
        if (dropdown) {
            dropdown.classList.remove('show');
        }
    }
    
    closeAllDropdowns(event) {
        this.dropdowns.forEach((dropdown, trigger) => {
            if (!trigger.contains(event.target) && !dropdown.contains(event.target)) {
                this.hideDropdown(trigger);
            }
        });
    }
    
    // Progress Bar Management
    createProgressBar(container, options = {}) {
        const {
            value = 0,
            max = 100,
            animated = false,
            showText = false,
            color = '#4f46e5'
        } = options;
        
        const progressContainer = document.createElement('div');
        progressContainer.className = 'progress-container';
        
        const progressBar = document.createElement('div');
        progressBar.className = `progress-bar ${animated ? 'animated' : ''}`;
        progressBar.style.width = `${(value / max) * 100}%`;
        progressBar.style.background = color;
        
        progressContainer.appendChild(progressBar);
        
        if (showText) {
            const progressText = document.createElement('div');
            progressText.className = 'progress-text';
            progressText.textContent = `${Math.round((value / max) * 100)}%`;
            progressContainer.appendChild(progressText);
        }
        
        container.appendChild(progressContainer);
        
        const progressId = Date.now() + Math.random();
        this.progressBars.set(progressId, {
            container: progressContainer,
            bar: progressBar,
            text: showText ? progressContainer.querySelector('.progress-text') : null,
            max
        });
        
        return progressId;
    }
    
    updateProgress(progressId, value) {
        const progress = this.progressBars.get(progressId);
        if (progress) {
            const percentage = Math.min(100, Math.max(0, (value / progress.max) * 100));
            progress.bar.style.width = `${percentage}%`;
            
            if (progress.text) {
                progress.text.textContent = `${Math.round(percentage)}%`;
            }
        }
    }
    
    // Context Menu
    showContextMenu(event, element) {
        const menuItems = JSON.parse(element.getAttribute('data-context-menu') || '[]');
        
        const contextMenu = document.createElement('div');
        contextMenu.className = 'context-menu';
        
        menuItems.forEach(item => {
            const menuItem = document.createElement('button');
            menuItem.className = `context-menu-item ${item.type || ''}`;
            menuItem.innerHTML = `
                ${item.icon ? `<i class="${item.icon}"></i>` : ''}
                ${item.label}
            `;
            
            if (item.handler) {
                menuItem.addEventListener('click', () => {
                    window[item.handler](element);
                    this.closeContextMenu();
                });
            }
            
            contextMenu.appendChild(menuItem);
        });
        
        document.body.appendChild(contextMenu);
        
        contextMenu.style.left = `${event.clientX}px`;
        contextMenu.style.top = `${event.clientY}px`;
        
        requestAnimationFrame(() => {
            contextMenu.classList.add('show');
        });
        
        this.activeContextMenu = contextMenu;
    }
    
    closeContextMenu() {
        if (this.activeContextMenu) {
            this.activeContextMenu.classList.remove('show');
            setTimeout(() => {
                if (this.activeContextMenu && this.activeContextMenu.parentNode) {
                    this.activeContextMenu.parentNode.removeChild(this.activeContextMenu);
                }
                this.activeContextMenu = null;
            }, 150);
        }
    }
    
    // Loading States
    setLoading(element, loading = true) {
        if (loading) {
            element.classList.add('btn-loading');
            element.disabled = true;
        } else {
            element.classList.remove('btn-loading');
            element.disabled = false;
        }
    }
    
    // Create skeleton loader
    createSkeleton(container, lines = 3) {
        container.innerHTML = '';
        
        for (let i = 0; i < lines; i++) {
            const skeleton = document.createElement('div');
            skeleton.className = 'skeleton skeleton-text';
            container.appendChild(skeleton);
        }
    }
    
    // Create badge
    createBadge(text, type = 'neutral') {
        const badge = document.createElement('span');
        badge.className = `badge ${type}`;
        badge.textContent = text;
        return badge;
    }
}

// Create global instance
window.interactiveElements = new InteractiveElements();
/**
 * KeyboardManager - Handle Global Shortcuts
 * 
 * Ctrl+S: Save Workflow
 * Ctrl+E: Execute Workflow
 * Ctrl+K: Command Palette (Placeholder)
 * Delete/Backspace: Delete Selected Node(s)
 */
class KeyboardManager {
    constructor() {
        this.init();
    }

    init() {
        document.addEventListener('keydown', (e) => {
            // META KEYS (Ctrl/Cmd)
            if (e.ctrlKey || e.metaKey) {
                switch (e.key.toLowerCase()) {
                    case 's':
                        e.preventDefault();
                        this.triggerAction('save');
                        break;
                    case 'e': // Execute
                    case 'enter': // Ctrl+Enter also executes
                        e.preventDefault();
                        this.triggerAction('execute');
                        break;
                    case 'k': // Command Palette
                        e.preventDefault();
                        this.triggerAction('search');
                        break;
                }
            }

            // DELETE
            if (e.key === 'Delete' || e.key === 'Backspace') {
                // Ignore if typing in an input
                if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) return;

                // If monaco editor is focused, ignore
                if (document.activeElement.closest('.monaco-editor')) return;

                this.triggerAction('delete_selection');
            }
        });
    }

    triggerAction(action) {
        console.log(`Command triggered: ${action}`);

        switch (action) {
            case 'save':
                const saveBtn = document.getElementById('save-workflow-btn');
                if (saveBtn) {
                    saveBtn.click();
                    if (window.Toast) window.Toast.info("Saving...", "Shortcut triggered");
                }
                break;

            case 'execute':
                const runBtn = document.getElementById('execute-workflow-btn');
                if (runBtn) {
                    runBtn.click();
                    if (window.Toast) window.Toast.info("Executing...", "Shortcut triggered");
                }
                break;

            case 'search':
                // Focus sidebar search
                const search = document.querySelector('.search-input');
                if (search) {
                    search.focus();
                    // Expand sidebar if needed
                    const lib = document.querySelector('.node-library');
                    if (lib && lib.classList.contains('collapsed')) {
                        // Logic to expand would go here
                    }
                }
                break;

            case 'delete_selection':
                // Call global deletion logic
                if (window.deleteSelectedNode) {
                    window.deleteSelectedNode();
                } else if (window.mainController && window.mainController.handleDelete) {
                    window.mainController.handleDelete();
                }
                break;
        }
    }
}

// Initialize
window.Keyboard = new KeyboardManager();

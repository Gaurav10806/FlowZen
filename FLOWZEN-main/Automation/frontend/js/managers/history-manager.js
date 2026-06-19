/**
 * History Manager - Handles Undo/Redo for the Workflow Builder
 */
class HistoryManager {
    constructor(canvasManager) {
        this.canvasManager = canvasManager;
        this.undoStack = [];
        this.redoStack = [];
        this.maxHistory = 50;
        this.isLocked = false;

        // Initial snapshot
        this.saveState('Initial State');
    }

    /**
     * Save current state to history
     * @param {string} description - Action description for debugging
     */
    togglePanel() {
        if (!this.panel) {
            this.createPanel();
        }
        this.panel.style.display = this.panel.style.display === 'none' ? 'block' : 'none';
        this.updatePanelList();
    }

    createPanel() {
        this.panel = document.createElement('div');
        this.panel.className = 'glass-panel';
        this.panel.style.cssText = `
            position: fixed; right: 20px; top: 70px; width: 300px; max-height: 500px;
            display: none; z-index: 1000; padding: 15px; overflow-y: auto;
        `;
        this.panel.innerHTML = `
            <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                <h3 style="margin:0">History</h3>
                <button onclick="this.parentElement.parentElement.style.display='none'" style="background:none; border:none; color:white; cursor:pointer;">&times;</button>
            </div>
            <div id="history-list"></div>
        `;
        document.body.appendChild(this.panel);
    }

    updatePanelList() {
        if (!this.panel) return;
        const list = this.panel.querySelector('#history-list');
        list.innerHTML = '';

        [...this.undoStack].reverse().forEach((item, index) => {
            const el = document.createElement('div');
            el.style.cssText = 'padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); font-size: 0.9rem; display: flex; justify-content: space-between; align-items: center;';

            const time = new Date(item.timestamp).toLocaleTimeString();
            el.innerHTML = `
                <div>
                    <div style="font-weight:600">${item.description}</div>
                    <div style="font-size:0.75rem; color:#aaa">${time}</div>
                </div>
                <div style="display:flex; gap:5px;">
                    <button class="restore-btn" title="Restore"><i class="fas fa-undo"></i></button>
                    <button class="diff-btn" title="Compare with Current"><i class="fas fa-code-branch"></i></button>
                </div>
            `;

            // Restore handler
            el.querySelector('.restore-btn').onclick = () => {
                // In a real stack, better logic needed, but for now just load state
                this.canvasManager.importWorkflow(item.state);
                window.notificationManager.info('Restored version: ' + item.description);
            };

            // Diff handler
            el.querySelector('.diff-btn').onclick = () => {
                const currentState = this.canvasManager.exportWorkflow();
                const diffViewer = new DiffViewer();
                diffViewer.show(currentState, item.state);
            };

            list.appendChild(el);
        });

        if (this.undoStack.length === 0) {
            list.innerHTML = '<div style="color:#aaa; text-align:center; padding:20px;">No history yet</div>';
        }
    }

    saveState(description = 'Unknown Action') {
        if (this.isLocked) return;

        const state = this.canvasManager.exportWorkflow();

        // Don't save if state hasn't changed
        if (this.undoStack.length > 0) {
            const lastState = this.undoStack[this.undoStack.length - 1].state;
            if (JSON.stringify(state) === JSON.stringify(lastState)) {
                return;
            }
        }

        this.undoStack.push({
            timestamp: Date.now(),
            description: description,
            state: JSON.parse(JSON.stringify(state))
        });

        // Limit stack size
        if (this.undoStack.length > this.maxHistory) {
            this.undoStack.shift();
        }

        this.redoStack = [];
        console.log(`[History] Saved: ${description}`);
        this.updateUI(); // Keep existing if any
        this.updatePanelList(); // Update panel if open
    }

    undo() {
        if (this.undoStack.length <= 1) return; // Need at least initial state

        const currentState = this.undoStack.pop();
        this.redoStack.push(currentState);

        const previousState = this.undoStack[this.undoStack.length - 1];
        this.restoreState(previousState.state);

        console.log(`[History] Undid: ${currentState.description}`);
        this.updateUI();
    }

    redo() {
        if (this.redoStack.length === 0) return;

        const nextState = this.redoStack.pop();
        this.undoStack.push(nextState);

        this.restoreState(nextState.state);

        console.log(`[History] Redid: ${nextState.description}`);
        this.updateUI();
    }

    restoreState(state) {
        this.isLocked = true; // Prevent saving duplicate state during restore
        try {
            this.canvasManager.importWorkflow(state, true); // true = clear existing
        } finally {
            this.isLocked = false;
        }
    }

    updateUI() {
        // Update Undo/Redo button states if they exist
        const undoBtn = document.getElementById('undo-btn');
        const redoBtn = document.getElementById('redo-btn');

        if (undoBtn) undoBtn.disabled = this.undoStack.length <= 1;
        if (redoBtn) redoBtn.disabled = this.redoStack.length === 0;
    }
}

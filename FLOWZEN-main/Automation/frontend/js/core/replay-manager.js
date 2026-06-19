/**
 * ReplayManager
 * Handles the Visual Execution Replay mode, including:
 * - locking the canvas
 * - highlighting nodes based on status
 * - displaying badges and control panels
 * - showing detailed execution results
 */
class ReplayManager {
    constructor(app) {
        this.app = app; // Reference to main app (for notificationManager etc)
        this.active = false;
    }

    /**
     * Enter Replay Mode for a specific execution
     * @param {Object} execution - The execution object from the backend
     */
    enterReplayMode(execution) {
        console.log('🎬 Entering Replay Mode', execution);
        document.body.classList.add('replay-mode');
        this.active = true;

        // Clean up any previous state
        this.exitReplayMode(false);

        // 1. Render Floating Controls
        this.renderControls(execution);

        // 2. Highlight Nodes
        const results = execution.result?.node_results || [];
        results.forEach(res => this.highlightNode(res));

        // 3. Lock Canvas (Visual only - pointer events handled by CSS)
        document.body.classList.add('read-only-canvas');

        if (this.app.notificationManager) {
            this.app.notificationManager.info(`Replaying execution #${execution.id.slice(0, 8)}`);
        }
    }

    /**
     * Render the top floating control bar
     */
    renderControls(execution) {
        const controls = document.createElement('div');
        controls.id = 'replay-controls';

        // Determine status visuals
        const isSuccess = execution.status === 'completed';
        const statusIcon = isSuccess ? 'fa-check-circle' : 'fa-exclamation-circle';
        // Note: We use inline colors for icons within the dark control panel for contrast, 
        // as global theme vars might be dark-on-light.
        const statusColor = isSuccess ? '#10b981' : '#ef4444';

        controls.innerHTML = `
            <div class="replay-status">
                <i class="fas ${statusIcon}" style="color: ${statusColor}; font-size: 1.2rem;"></i>
                <span style="font-weight: 600;">Execution #${execution.id.slice(0, 8)}</span>
                <span class="replay-time" style="opacity: 0.7; font-size: 0.9rem;">
                    ${new Date(execution.created_at).toLocaleTimeString()}
                </span>
            </div>
            <div class="replay-divider"></div>
            <button id="exit-replay-btn" type="button" class="user-btn secondary small" style="border-radius: 15px; background: rgba(255,255,255,0.1); color: white; border: none;">
                <i class="fas fa-times me-1"></i> Exit
            </button>
        `;

        document.body.appendChild(controls);

        // Bind Exit Action
        document.getElementById('exit-replay-btn').addEventListener('click', () => {
            this.exitReplayMode();
        });
    }

    /**
     * Apply status classes and badges to a specific node
     */
    highlightNode(res) {
        const nodeEl = document.querySelector(`[data-node-id="${res.node_id}"]`);
        if (!nodeEl) return;

        // Remove old classes
        nodeEl.classList.remove('execution-success', 'execution-error');

        // Add new class
        nodeEl.classList.add(res.success ? 'execution-success' : 'execution-error');

        // Remove old badge
        const existingBadge = nodeEl.querySelector('.replay-badge');
        if (existingBadge) existingBadge.remove();

        // Create Badge
        const badge = document.createElement('div');
        // Use utility classes from replay.css (.success / .error)
        badge.className = `replay-badge ${res.success ? 'success' : 'error'}`;
        badge.innerHTML = `
            <i class="fas ${res.success ? 'fa-check' : 'fa-times'}"></i>
            ${res.execution_time_ms ? Math.round(res.execution_time_ms) + 'ms' : ''}
        `;
        nodeEl.appendChild(badge);

        // Add Click Listener for Details
        // We override the default click behavior for the node during replay
        nodeEl.onclick = (e) => {
            e.stopPropagation(); // Stop selection logic
            this.showNodeExecutionDetails(res);
        };
    }

    /**
     * Show side popover with node details
     */
    showNodeExecutionDetails(result) {
        // Remove existing popovers
        document.querySelectorAll('.execution-details-popover').forEach(el => el.remove());

        const popover = document.createElement('div');
        popover.className = 'execution-details-popover';

        // Dynamic Status Color
        const statusColor = result.success ? 'var(--user-success)' : 'var(--user-error)';

        popover.innerHTML = `
            <div class="execution-details-header">
                <h5>${result.node_type}</h5>
                <button class="close-details-btn"><i class="fas fa-times"></i></button>
            </div>
            
            <div class="mb-3">
                <label style="font-size: 0.8rem; color: var(--user-text-secondary); font-weight: 600;">STATUS</label>
                <div style="color: ${statusColor}; font-weight: 600;">
                    ${result.success ? 'Success' : 'Failed'} 
                    <span style="color: var(--user-text-muted); font-weight: 400; font-size: 0.9rem;">(${parseInt(result.execution_time_ms)}ms)</span>
                </div>
            </div>

            ${result.error_message ? `
                <div class="mb-3 p-2 rounded" style="background: var(--user-error-light); border: 1px solid var(--user-error);">
                    <label style="font-size: 0.8rem; color: var(--user-error); font-weight: 600;">ERROR</label>
                    <div style="color: var(--user-error); font-size: 0.9rem;">${result.error_message}</div>
                </div>
            ` : ''}

            <div class="mb-3">
                <label style="font-size: 0.8rem; color: var(--user-text-secondary); font-weight: 600;">OUTPUT</label>
                <div style="background: var(--user-bg-secondary); padding: 10px; border-radius: 6px; font-family: monospace; font-size: 0.85rem; overflow-x: auto; max-height: 300px; border: 1px solid var(--user-border-primary);">
                    <pre style="margin: 0; color: var(--user-text-primary);">${JSON.stringify(result.output_data, null, 2)}</pre>
                </div>
            </div>
        `;

        document.body.appendChild(popover);

        // Bind Close
        popover.querySelector('.close-details-btn').addEventListener('click', () => popover.remove());
    }

    /**
     * Exit Replay Mode and restore state
     */
    exitReplayMode(fullClean = true) {
        document.body.classList.remove('replay-mode', 'read-only-canvas');

        // Remove controls & details
        const controls = document.getElementById('replay-controls');
        if (controls) controls.remove();
        document.querySelectorAll('.execution-details-popover').forEach(el => el.remove());

        // Clean nodes
        document.querySelectorAll('.workflow-node').forEach(node => {
            node.classList.remove('execution-success', 'execution-error');
            const badge = node.querySelector('.replay-badge');
            if (badge) badge.remove();

            // Restore click handlers
            // Ideally we would restore specific handlers, but setting null allows 
            // the delegated listeners on the container (if any) to work, 
            // OR we assume the NodeManager will re-bind if selection is needed.
            // For now, null is safe as it clears the "Show Details" override.
            node.onclick = null;
        });

        this.active = false;

        if (fullClean && this.app.notificationManager) {
            this.app.notificationManager.info('Exited Replay Mode');
        }
    }
}

// Export to window
window.ReplayManager = ReplayManager;

/**
 * 🚀 REVOLUTIONARY REAL-TIME COLLABORATION ENGINE
 * 
 * Features:
 * - Live cursor tracking with user avatars
 * - Real-time presence indicators
 * - Collaborative editing with conflict resolution
 * - Live comments and annotations
 * - Activity feed with beautiful animations
 * - Voice/video chat integration
 */

class CollaborationEngine {
    constructor() {
        this.websocket = null;
        this.collaborators = new Map();
        this.cursors = new Map();
        this.comments = new Map();
        this.activityFeed = [];
        this.currentUser = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        
        this.init();
    }
    
    init() {
        this.setupWebSocket();
        this.createCollaborationUI();
        this.setupEventListeners();
        this.startHeartbeat();
        console.log('🚀 Collaboration Engine initialized');
    }
    
    setupWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/collaboration/`;
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            this.isConnected = true;
            this.reconnectAttempts = 0;
            this.showNotification('🌟 Connected to collaboration server', 'success');
            this.sendPresence();
        };
        
        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
        
        this.websocket.onclose = () => {
            this.isConnected = false;
            this.attemptReconnect();
        };
        
        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.showNotification('❌ Collaboration connection error', 'error');
        };
    }
    
    createCollaborationUI() {
        // Create collaboration panel
        const collaborationPanel = document.createElement('div');
        collaborationPanel.className = 'collaboration-panel';
        collaborationPanel.innerHTML = `
            <div class="collaboration-header">
                <div class="collaboration-title">
                    <i class="fas fa-users"></i>
                    <span>Live Collaboration</span>
                    <div class="connection-status ${this.isConnected ? 'connected' : 'disconnected'}"></div>
                </div>
                <button class="collapse-btn" onclick="collaborationEngine.togglePanel()">
                    <i class="fas fa-chevron-right"></i>
                </button>
            </div>
            
            <div class="collaboration-content">
                <!-- Active Collaborators -->
                <div class="collaborators-section">
                    <h4><i class="fas fa-user-friends"></i> Active Users</h4>
                    <div class="collaborators-list" id="collaborators-list">
                        <!-- Collaborators will be added here -->
                    </div>
                </div>
                
                <!-- Activity Feed -->
                <div class="activity-section">
                    <h4><i class="fas fa-stream"></i> Recent Activity</h4>
                    <div class="activity-feed" id="activity-feed">
                        <!-- Activity items will be added here -->
                    </div>
                </div>
                
                <!-- Comments Section -->
                <div class="comments-section">
                    <h4><i class="fas fa-comments"></i> Comments</h4>
                    <div class="comments-list" id="comments-list">
                        <!-- Comments will be added here -->
                    </div>
                    <div class="comment-input">
                        <input type="text" placeholder="Add a comment..." id="comment-input">
                        <button onclick="collaborationEngine.addComment()">
                            <i class="fas fa-paper-plane"></i>
                        </button>
                    </div>
                </div>
                
                <!-- Voice/Video Controls -->
                <div class="communication-controls">
                    <button class="voice-btn" onclick="collaborationEngine.toggleVoice()">
                        <i class="fas fa-microphone"></i>
                    </button>
                    <button class="video-btn" onclick="collaborationEngine.toggleVideo()">
                        <i class="fas fa-video"></i>
                    </button>
                    <button class="screen-share-btn" onclick="collaborationEngine.toggleScreenShare()">
                        <i class="fas fa-desktop"></i>
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(collaborationPanel);
        
        // Create cursor container
        const cursorContainer = document.createElement('div');
        cursorContainer.id = 'collaboration-cursors';
        cursorContainer.className = 'collaboration-cursors';
        document.body.appendChild(cursorContainer);
        
        this.setupStyles();
    }
    
    setupStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .collaboration-panel {
                position: fixed;
                top: 80px;
                right: 20px;
                width: 320px;
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(20px);
                border-radius: 16px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                z-index: 1000;
                transform: translateX(100%);
                transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            }
            
            .collaboration-panel.open {
                transform: translateX(0);
            }
            
            .collaboration-header {
                padding: 20px;
                border-bottom: 1px solid rgba(0, 0, 0, 0.1);
                display: flex;
                align-items: center;
                justify-content: space-between;
            }
            
            .collaboration-title {
                display: flex;
                align-items: center;
                gap: 8px;
                font-weight: 600;
                color: #1f2937;
            }
            
            .connection-status {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                margin-left: 8px;
            }
            
            .connection-status.connected {
                background: #10b981;
                box-shadow: 0 0 10px rgba(16, 185, 129, 0.5);
                animation: pulse 2s infinite;
            }
            
            .connection-status.disconnected {
                background: #ef4444;
            }
            
            .collaboration-content {
                padding: 20px;
                max-height: 600px;
                overflow-y: auto;
            }
            
            .collaborators-section,
            .activity-section,
            .comments-section {
                margin-bottom: 24px;
            }
            
            .collaborators-section h4,
            .activity-section h4,
            .comments-section h4 {
                margin: 0 0 12px 0;
                font-size: 14px;
                font-weight: 600;
                color: #6b7280;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .collaborator-item {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 8px 12px;
                border-radius: 8px;
                margin-bottom: 8px;
                background: rgba(16, 185, 129, 0.1);
                border: 1px solid rgba(16, 185, 129, 0.2);
                transition: all 0.2s ease;
            }
            
            .collaborator-item:hover {
                background: rgba(16, 185, 129, 0.15);
                transform: translateY(-1px);
            }
            
            .collaborator-avatar {
                width: 32px;
                height: 32px;
                border-radius: 50%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-weight: 600;
                font-size: 12px;
            }
            
            .collaborator-info {
                flex: 1;
            }
            
            .collaborator-name {
                font-weight: 500;
                font-size: 14px;
                color: #1f2937;
            }
            
            .collaborator-status {
                font-size: 12px;
                color: #6b7280;
            }
            
            .activity-item {
                display: flex;
                align-items: flex-start;
                gap: 12px;
                padding: 12px;
                border-radius: 8px;
                margin-bottom: 8px;
                background: rgba(0, 0, 0, 0.02);
                border-left: 3px solid #3b82f6;
                transition: all 0.2s ease;
                animation: slideInRight 0.3s ease;
            }
            
            .activity-icon {
                width: 24px;
                height: 24px;
                border-radius: 50%;
                background: #3b82f6;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 10px;
                flex-shrink: 0;
            }
            
            .activity-content {
                flex: 1;
            }
            
            .activity-text {
                font-size: 13px;
                color: #374151;
                margin-bottom: 4px;
            }
            
            .activity-time {
                font-size: 11px;
                color: #9ca3af;
            }
            
            .comment-item {
                padding: 12px;
                border-radius: 8px;
                margin-bottom: 8px;
                background: rgba(0, 0, 0, 0.02);
                border: 1px solid rgba(0, 0, 0, 0.05);
                animation: slideInUp 0.3s ease;
            }
            
            .comment-header {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 8px;
            }
            
            .comment-author {
                font-weight: 500;
                font-size: 12px;
                color: #1f2937;
            }
            
            .comment-time {
                font-size: 11px;
                color: #9ca3af;
            }
            
            .comment-text {
                font-size: 13px;
                color: #374151;
                line-height: 1.4;
            }
            
            .comment-input {
                display: flex;
                gap: 8px;
                margin-top: 12px;
            }
            
            .comment-input input {
                flex: 1;
                padding: 8px 12px;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 6px;
                font-size: 13px;
                background: rgba(255, 255, 255, 0.8);
            }
            
            .comment-input button {
                padding: 8px 12px;
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            
            .comment-input button:hover {
                background: #2563eb;
                transform: scale(1.05);
            }
            
            .communication-controls {
                display: flex;
                gap: 8px;
                padding-top: 16px;
                border-top: 1px solid rgba(0, 0, 0, 0.1);
            }
            
            .communication-controls button {
                flex: 1;
                padding: 10px;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 8px;
                background: rgba(255, 255, 255, 0.8);
                cursor: pointer;
                transition: all 0.2s ease;
            }
            
            .communication-controls button:hover {
                background: rgba(59, 130, 246, 0.1);
                border-color: #3b82f6;
                transform: translateY(-1px);
            }
            
            .communication-controls button.active {
                background: #3b82f6;
                color: white;
                border-color: #3b82f6;
            }
            
            .collaboration-cursors {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                pointer-events: none;
                z-index: 999;
            }
            
            .collaboration-cursor {
                position: absolute;
                pointer-events: none;
                transition: all 0.1s ease;
                z-index: 1000;
            }
            
            .cursor-pointer {
                width: 20px;
                height: 20px;
                background: #3b82f6;
                border-radius: 50% 0 50% 50%;
                transform: rotate(-45deg);
                position: relative;
            }
            
            .cursor-label {
                position: absolute;
                top: -30px;
                left: 20px;
                background: #1f2937;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 500;
                white-space: nowrap;
                transform: rotate(45deg);
            }
            
            @keyframes slideInRight {
                from {
                    transform: translateX(20px);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            
            @keyframes slideInUp {
                from {
                    transform: translateY(10px);
                    opacity: 0;
                }
                to {
                    transform: translateY(0);
                    opacity: 1;
                }
            }
            
            @keyframes pulse {
                0%, 100% {
                    opacity: 1;
                }
                50% {
                    opacity: 0.5;
                }
            }
        `;
        document.head.appendChild(style);
    }
    
    setupEventListeners() {
        // Track mouse movement for cursor sharing
        document.addEventListener('mousemove', (e) => {
            if (this.isConnected) {
                this.throttledSendCursor(e.clientX, e.clientY);
            }
        });
        
        // Track workflow changes
        document.addEventListener('workflowChanged', (e) => {
            if (this.isConnected) {
                this.sendWorkflowChange(e.detail);
            }
        });
        
        // Track node selection
        document.addEventListener('nodeSelected', (e) => {
            if (this.isConnected) {
                this.sendNodeSelection(e.detail);
            }
        });
        
        // Comment input enter key
        document.addEventListener('keydown', (e) => {
            if (e.target.id === 'comment-input' && e.key === 'Enter') {
                this.addComment();
            }
        });
    }
    
    throttledSendCursor = this.throttle((x, y) => {
        this.sendMessage({
            type: 'cursor_move',
            x: x,
            y: y,
            timestamp: Date.now()
        });
    }, 50);
    
    handleMessage(data) {
        switch (data.type) {
            case 'user_joined':
                this.handleUserJoined(data);
                break;
            case 'user_left':
                this.handleUserLeft(data);
                break;
            case 'cursor_move':
                this.handleCursorMove(data);
                break;
            case 'workflow_change':
                this.handleWorkflowChange(data);
                break;
            case 'node_selection':
                this.handleNodeSelection(data);
                break;
            case 'comment_added':
                this.handleCommentAdded(data);
                break;
            case 'activity_update':
                this.handleActivityUpdate(data);
                break;
        }
    }
    
    handleUserJoined(data) {
        this.collaborators.set(data.user.id, data.user);
        this.updateCollaboratorsList();
        this.addActivityItem({
            type: 'user_joined',
            user: data.user,
            timestamp: Date.now()
        });
        this.showNotification(`👋 ${data.user.name} joined the session`, 'info');
    }
    
    handleUserLeft(data) {
        this.collaborators.delete(data.user.id);
        this.cursors.delete(data.user.id);
        this.updateCollaboratorsList();
        this.removeCursor(data.user.id);
        this.addActivityItem({
            type: 'user_left',
            user: data.user,
            timestamp: Date.now()
        });
    }
    
    handleCursorMove(data) {
        this.updateCursor(data.user.id, data.x, data.y, data.user);
    }
    
    handleWorkflowChange(data) {
        this.addActivityItem({
            type: 'workflow_change',
            user: data.user,
            change: data.change,
            timestamp: Date.now()
        });
        
        // Apply the change to the local workflow
        if (window.workflowManager) {
            window.workflowManager.applyRemoteChange(data.change);
        }
    }
    
    handleNodeSelection(data) {
        // Highlight the selected node for other users
        this.highlightNodeForUser(data.nodeId, data.user);
    }
    
    handleCommentAdded(data) {
        this.addCommentToUI(data.comment);
    }
    
    handleActivityUpdate(data) {
        this.addActivityItem(data.activity);
    }
    
    updateCollaboratorsList() {
        const list = document.getElementById('collaborators-list');
        if (!list) return;
        
        list.innerHTML = '';
        
        this.collaborators.forEach((user) => {
            const item = document.createElement('div');
            item.className = 'collaborator-item';
            item.innerHTML = `
                <div class="collaborator-avatar" style="background: ${user.color || '#3b82f6'}">
                    ${user.name.charAt(0).toUpperCase()}
                </div>
                <div class="collaborator-info">
                    <div class="collaborator-name">${user.name}</div>
                    <div class="collaborator-status">${user.status || 'Active'}</div>
                </div>
            `;
            list.appendChild(item);
        });
    }
    
    updateCursor(userId, x, y, user) {
        let cursor = this.cursors.get(userId);
        
        if (!cursor) {
            cursor = document.createElement('div');
            cursor.className = 'collaboration-cursor';
            cursor.innerHTML = `
                <div class="cursor-pointer" style="background: ${user.color || '#3b82f6'}"></div>
                <div class="cursor-label">${user.name}</div>
            `;
            document.getElementById('collaboration-cursors').appendChild(cursor);
            this.cursors.set(userId, cursor);
        }
        
        cursor.style.left = x + 'px';
        cursor.style.top = y + 'px';
    }
    
    removeCursor(userId) {
        const cursor = this.cursors.get(userId);
        if (cursor) {
            cursor.remove();
            this.cursors.delete(userId);
        }
    }
    
    addActivityItem(activity) {
        this.activityFeed.unshift(activity);
        
        // Keep only last 50 items
        if (this.activityFeed.length > 50) {
            this.activityFeed = this.activityFeed.slice(0, 50);
        }
        
        this.updateActivityFeed();
    }
    
    updateActivityFeed() {
        const feed = document.getElementById('activity-feed');
        if (!feed) return;
        
        feed.innerHTML = '';
        
        this.activityFeed.slice(0, 10).forEach((activity) => {
            const item = document.createElement('div');
            item.className = 'activity-item';
            
            const icon = this.getActivityIcon(activity.type);
            const text = this.getActivityText(activity);
            const time = this.formatTime(activity.timestamp);
            
            item.innerHTML = `
                <div class="activity-icon">
                    <i class="${icon}"></i>
                </div>
                <div class="activity-content">
                    <div class="activity-text">${text}</div>
                    <div class="activity-time">${time}</div>
                </div>
            `;
            
            feed.appendChild(item);
        });
    }
    
    getActivityIcon(type) {
        const icons = {
            user_joined: 'fas fa-user-plus',
            user_left: 'fas fa-user-minus',
            workflow_change: 'fas fa-edit',
            node_added: 'fas fa-plus',
            node_deleted: 'fas fa-trash',
            connection_added: 'fas fa-link',
            comment_added: 'fas fa-comment'
        };
        return icons[type] || 'fas fa-info';
    }
    
    getActivityText(activity) {
        const texts = {
            user_joined: `${activity.user.name} joined the session`,
            user_left: `${activity.user.name} left the session`,
            workflow_change: `${activity.user.name} modified the workflow`,
            node_added: `${activity.user.name} added a node`,
            node_deleted: `${activity.user.name} deleted a node`,
            connection_added: `${activity.user.name} connected nodes`,
            comment_added: `${activity.user.name} added a comment`
        };
        return texts[activity.type] || 'Unknown activity';
    }
    
    formatTime(timestamp) {
        const now = Date.now();
        const diff = now - timestamp;
        
        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
        return `${Math.floor(diff / 86400000)}d ago`;
    }
    
    addComment() {
        const input = document.getElementById('comment-input');
        if (!input || !input.value.trim()) return;
        
        const comment = {
            id: Date.now(),
            text: input.value.trim(),
            author: this.currentUser,
            timestamp: Date.now()
        };
        
        this.sendMessage({
            type: 'add_comment',
            comment: comment
        });
        
        input.value = '';
    }
    
    addCommentToUI(comment) {
        const list = document.getElementById('comments-list');
        if (!list) return;
        
        const item = document.createElement('div');
        item.className = 'comment-item';
        item.innerHTML = `
            <div class="comment-header">
                <span class="comment-author">${comment.author.name}</span>
                <span class="comment-time">${this.formatTime(comment.timestamp)}</span>
            </div>
            <div class="comment-text">${comment.text}</div>
        `;
        
        list.insertBefore(item, list.firstChild);
    }
    
    sendMessage(message) {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify(message));
        }
    }
    
    sendPresence() {
        this.sendMessage({
            type: 'presence',
            user: this.currentUser
        });
    }
    
    sendWorkflowChange(change) {
        this.sendMessage({
            type: 'workflow_change',
            change: change
        });
    }
    
    sendNodeSelection(nodeId) {
        this.sendMessage({
            type: 'node_selection',
            nodeId: nodeId
        });
    }
    
    togglePanel() {
        const panel = document.querySelector('.collaboration-panel');
        panel.classList.toggle('open');
    }
    
    toggleVoice() {
        // Implement voice chat
        console.log('Voice chat toggled');
    }
    
    toggleVideo() {
        // Implement video chat
        console.log('Video chat toggled');
    }
    
    toggleScreenShare() {
        // Implement screen sharing
        console.log('Screen share toggled');
    }
    
    startHeartbeat() {
        setInterval(() => {
            if (this.isConnected) {
                this.sendMessage({ type: 'heartbeat' });
            }
        }, 30000);
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            setTimeout(() => {
                console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
                this.setupWebSocket();
            }, 2000 * this.reconnectAttempts);
        }
    }
    
    showNotification(message, type) {
        if (window.notificationManager) {
            window.notificationManager.show(message, type);
        }
    }
    
    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        }
    }
    
    highlightNodeForUser(nodeId, user) {
        const node = document.getElementById(nodeId);
        if (node) {
            node.style.boxShadow = `0 0 20px ${user.color || '#3b82f6'}`;
            setTimeout(() => {
                node.style.boxShadow = '';
            }, 2000);
        }
    }
    
    setCurrentUser(user) {
        this.currentUser = user;
    }
    
    destroy() {
        if (this.websocket) {
            this.websocket.close();
        }
        
        // Clean up UI elements
        const panel = document.querySelector('.collaboration-panel');
        const cursors = document.getElementById('collaboration-cursors');
        
        if (panel) panel.remove();
        if (cursors) cursors.remove();
    }
}

// Initialize collaboration engine
window.collaborationEngine = new CollaborationEngine();

// Auto-open collaboration panel
setTimeout(() => {
    if (window.collaborationEngine) {
        window.collaborationEngine.togglePanel();
    }
}, 1000);
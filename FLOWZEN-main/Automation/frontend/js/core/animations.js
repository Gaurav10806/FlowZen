// Advanced Animation System - Smooth, Professional Animations
class AnimationManager {
    constructor() {
        this.activeAnimations = new Map();
        this.animationQueue = [];
        this.isProcessing = false;
        this.particles = [];
        
        this.easingFunctions = {
            easeInOut: 'cubic-bezier(0.4, 0, 0.2, 1)',
            easeOut: 'cubic-bezier(0, 0, 0.2, 1)',
            easeIn: 'cubic-bezier(0.4, 0, 1, 1)',
            bounce: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
            elastic: 'cubic-bezier(0.175, 0.885, 0.32, 1.275)',
            spring: 'cubic-bezier(0.25, 0.46, 0.45, 0.94)'
        };
        
        this.init();
    }
    
    init() {
        this.setupAnimationStyles();
        this.setupParticleSystem();
        this.startAnimationLoop();
    }
    
    setupAnimationStyles() {
        const style = document.createElement('style');
        style.textContent = `
            @keyframes nodeAppear {
                0% {
                    opacity: 0;
                    transform: scale(0.8) translateY(-20px) rotate(-5deg);
                }
                50% {
                    opacity: 0.8;
                    transform: scale(1.05) translateY(-5px) rotate(2deg);
                }
                100% {
                    opacity: 1;
                    transform: scale(1) translateY(0) rotate(0deg);
                }
            }
            
            @keyframes nodeExecuting {
                0%, 100% { 
                    box-shadow: 0 0 0 0 rgba(79, 70, 229, 0.7);
                    transform: scale(1);
                }
                25% { 
                    box-shadow: 0 0 0 8px rgba(79, 70, 229, 0.4);
                    transform: scale(1.02);
                }
                50% { 
                    box-shadow: 0 0 0 15px rgba(79, 70, 229, 0);
                    transform: scale(1.05);
                }
                75% { 
                    box-shadow: 0 0 0 8px rgba(79, 70, 229, 0.4);
                    transform: scale(1.02);
                }
            }
            
            @keyframes connectionDraw {
                0% { 
                    stroke-dashoffset: 100%; 
                    opacity: 0;
                }
                20% {
                    opacity: 1;
                }
                100% { 
                    stroke-dashoffset: 0%; 
                    opacity: 1;
                }
            }
            
            @keyframes dataFlow {
                0% { 
                    transform: translateX(-100%) scale(0.5); 
                    opacity: 0; 
                }
                10% {
                    opacity: 1;
                    transform: translateX(-80%) scale(1);
                }
                90% { 
                    opacity: 1;
                    transform: translateX(80%) scale(1);
                }
                100% { 
                    transform: translateX(100%) scale(0.5); 
                    opacity: 0; 
                }
            }
            
            @keyframes panelSlideIn {
                0% { 
                    transform: translateX(100%) scale(0.95); 
                    opacity: 0; 
                }
                100% { 
                    transform: translateX(0) scale(1); 
                    opacity: 1; 
                }
            }
            
            @keyframes toastSlideIn {
                0% { 
                    transform: translateY(-100%) translateX(50px) scale(0.9) rotate(5deg); 
                    opacity: 0; 
                }
                100% { 
                    transform: translateY(0) translateX(0) scale(1) rotate(0deg); 
                    opacity: 1; 
                }
            }
            
            @keyframes shimmer {
                0% { background-position: -200px 0; }
                100% { background-position: calc(200px + 100%) 0; }
            }
            
            @keyframes morphBounce {
                0%, 100% { transform: scale(1); }
                50% { transform: scale(1.1); }
            }
            
            @keyframes wiggle {
                0%, 100% { transform: rotate(0deg); }
                25% { transform: rotate(-3deg); }
                75% { transform: rotate(3deg); }
            }
            
            @keyframes heartbeat {
                0%, 100% { transform: scale(1); }
                14% { transform: scale(1.1); }
                28% { transform: scale(1); }
                42% { transform: scale(1.1); }
                70% { transform: scale(1); }
            }
            
            @keyframes typewriter {
                from { width: 0; }
                to { width: 100%; }
            }
            
            @keyframes fadeInUp {
                from {
                    opacity: 0;
                    transform: translateY(30px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            @keyframes zoomInRotate {
                from {
                    opacity: 0;
                    transform: scale(0.5) rotate(-180deg);
                }
                to {
                    opacity: 1;
                    transform: scale(1) rotate(0deg);
                }
            }
            
            .animate-node-appear {
                animation: nodeAppear 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
            }
            
            .animate-node-executing {
                animation: nodeExecuting 2s infinite;
            }
            
            .animate-connection-draw {
                stroke-dasharray: 100%;
                animation: connectionDraw 0.8s ease-out forwards;
            }
            
            .animate-data-flow {
                animation: dataFlow 2s ease-in-out infinite;
            }
            
            .animate-panel-slide {
                animation: panelSlideIn 0.4s cubic-bezier(0.4, 0, 0.2, 1) forwards;
            }
            
            .animate-toast {
                animation: toastSlideIn 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
            }
            
            .animate-morph-bounce {
                animation: morphBounce 0.4s ease-in-out;
            }
            
            .animate-wiggle {
                animation: wiggle 0.5s ease-in-out;
            }
            
            .animate-heartbeat {
                animation: heartbeat 1.5s ease-in-out infinite;
            }
            
            .animate-fade-in-up {
                animation: fadeInUp 0.6s ease-out forwards;
            }
            
            .animate-zoom-in-rotate {
                animation: zoomInRotate 0.8s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
            }
            
            .skeleton-loading {
                background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
                background-size: 200px 100%;
                animation: shimmer 1.5s infinite;
            }
            
            .hover-lift {
                transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.3s ease;
            }
            
            .hover-lift:hover {
                transform: translateY(-4px) scale(1.02);
                box-shadow: 0 12px 30px rgba(0, 0, 0, 0.15);
            }
            
            .pulse-success {
                animation: pulse-success 0.8s ease-out;
            }
            
            @keyframes pulse-success {
                0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
                70% { box-shadow: 0 0 0 15px rgba(16, 185, 129, 0); }
                100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
            }
            
            .pulse-error {
                animation: pulse-error 0.8s ease-out;
            }
            
            @keyframes pulse-error {
                0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
                70% { box-shadow: 0 0 0 15px rgba(239, 68, 68, 0); }
                100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
            }
            
            .loading-dots::after {
                content: '';
                animation: loadingDots 1.5s infinite;
            }
            
            @keyframes loadingDots {
                0%, 20% { content: ''; }
                40% { content: '.'; }
                60% { content: '..'; }
                80%, 100% { content: '...'; }
            }
        `;
        document.head.appendChild(style);
    }
    
    setupParticleSystem() {
        this.particleCanvas = document.createElement('canvas');
        this.particleCanvas.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 9998;
        `;
        document.body.appendChild(this.particleCanvas);
        
        this.particleCtx = this.particleCanvas.getContext('2d');
        this.resizeParticleCanvas();
        
        window.addEventListener('resize', () => this.resizeParticleCanvas());
    }
    
    resizeParticleCanvas() {
        this.particleCanvas.width = window.innerWidth;
        this.particleCanvas.height = window.innerHeight;
    }
    
    startAnimationLoop() {
        const animate = () => {
            this.updateParticles();
            this.renderParticles();
            requestAnimationFrame(animate);
        };
        animate();
    }
    
    // Enhanced node creation animation
    animateNodeCreation(nodeElement) {
        // Add creation particles
        this.createParticleExplosion(
            nodeElement.offsetLeft + nodeElement.offsetWidth / 2,
            nodeElement.offsetTop + nodeElement.offsetHeight / 2,
            '#4f46e5'
        );
        
        nodeElement.classList.add('animate-node-appear');
        
        // Add sound effect (if audio is enabled)
        this.playSound('nodeCreate');
        
        setTimeout(() => {
            nodeElement.classList.remove('animate-node-appear');
        }, 600);
    }
    
    // Enhanced node execution animation
    animateNodeExecution(nodeElement) {
        nodeElement.classList.add('animate-node-executing');
        
        // Add execution particles
        const interval = setInterval(() => {
            this.createParticleStream(
                nodeElement.offsetLeft + nodeElement.offsetWidth / 2,
                nodeElement.offsetTop + nodeElement.offsetHeight / 2,
                '#10b981'
            );
        }, 200);
        
        return {
            stop: () => {
                nodeElement.classList.remove('animate-node-executing');
                clearInterval(interval);
            }
        };
    }
    
    // Enhanced connection drawing
    animateConnectionDraw(connectionElement) {
        connectionElement.classList.add('animate-connection-draw');
        
        // Add connection particles
        this.animateConnectionParticles(connectionElement);
        
        setTimeout(() => {
            connectionElement.classList.remove('animate-connection-draw');
        }, 800);
    }
    
    // Animate data flow with particles
    animateDataFlow(connectionElement, data) {
        const flowElement = document.createElement('div');
        flowElement.className = 'data-flow-indicator animate-data-flow';
        flowElement.style.cssText = `
            position: absolute;
            width: 12px;
            height: 12px;
            background: radial-gradient(circle, #4f46e5, #3730a3);
            border-radius: 50%;
            pointer-events: none;
            z-index: 1000;
            box-shadow: 0 0 12px #4f46e5;
        `;
        
        connectionElement.appendChild(flowElement);
        
        // Add trailing particles
        const trailInterval = setInterval(() => {
            this.createParticleTrail(
                flowElement.offsetLeft,
                flowElement.offsetTop,
                '#4f46e5'
            );
        }, 50);
        
        setTimeout(() => {
            clearInterval(trailInterval);
            if (flowElement.parentNode) {
                flowElement.parentNode.removeChild(flowElement);
            }
        }, 2000);
    }
    
    // Smooth panel transitions
    animatePanelOpen(panelElement) {
        panelElement.style.display = 'block';
        panelElement.classList.add('animate-panel-slide');
        
        setTimeout(() => {
            panelElement.classList.remove('animate-panel-slide');
        }, 400);
    }
    
    // Enhanced toast animations
    animateToast(toastElement) {
        toastElement.classList.add('animate-toast');
        
        // Add celebration particles for success toasts
        if (toastElement.classList.contains('success')) {
            this.createCelebrationParticles();
        }
        
        setTimeout(() => {
            toastElement.classList.remove('animate-toast');
        }, 500);
    }
    
    // Advanced animation with custom properties
    animate(element, properties, duration = 300, easing = 'easeInOut') {
        return new Promise((resolve) => {
            const animationId = Date.now() + Math.random();
            
            element.style.transition = `all ${duration}ms ${this.easingFunctions[easing]}`;
            
            Object.keys(properties).forEach(prop => {
                element.style[prop] = properties[prop];
            });
            
            const cleanup = () => {
                element.style.transition = '';
                this.activeAnimations.delete(animationId);
                resolve();
            };
            
            this.activeAnimations.set(animationId, cleanup);
            setTimeout(cleanup, duration);
        });
    }
    
    // Stagger animations with enhanced timing
    staggerAnimate(elements, properties, duration = 300, staggerDelay = 100) {
        return Promise.all(
            elements.map((element, index) => {
                return new Promise(resolve => {
                    setTimeout(() => {
                        // Add random variation to make it more natural
                        const variation = (Math.random() - 0.5) * 20;
                        this.animate(element, properties, duration + variation).then(resolve);
                    }, index * staggerDelay);
                });
            })
        );
    }
    
    // Morphing animation between states
    morph(element, fromState, toState, duration = 400) {
        const keyframes = [fromState, toState];
        
        return element.animate(keyframes, {
            duration,
            easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
            fill: 'forwards'
        });
    }
    
    // Bounce animation with enhanced physics
    bounce(element, intensity = 1) {
        const bounceKeyframes = [
            { transform: 'scale(1)', offset: 0 },
            { transform: `scale(${1 + 0.1 * intensity})`, offset: 0.3 },
            { transform: 'scale(1)', offset: 0.6 },
            { transform: `scale(${1 + 0.05 * intensity})`, offset: 0.8 },
            { transform: 'scale(1)', offset: 1 }
        ];
        
        element.animate(bounceKeyframes, {
            duration: 600,
            easing: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)'
        });
    }
    
    // Shake animation with customizable intensity
    shake(element, intensity = 1) {
        const shakeDistance = 10 * intensity;
        const keyframes = [
            { transform: 'translateX(0)' },
            { transform: `translateX(-${shakeDistance}px)` },
            { transform: `translateX(${shakeDistance}px)` },
            { transform: `translateX(-${shakeDistance * 0.7}px)` },
            { transform: `translateX(${shakeDistance * 0.7}px)` },
            { transform: `translateX(-${shakeDistance * 0.3}px)` },
            { transform: `translateX(${shakeDistance * 0.3}px)` },
            { transform: 'translateX(0)' }
        ];
        
        element.animate(keyframes, {
            duration: 600,
            easing: 'ease-in-out'
        });
    }
    
    // Enhanced pulse animation
    pulse(element, type = 'success', intensity = 1) {
        element.classList.add(`pulse-${type}`);
        
        // Add particle effect
        if (type === 'success') {
            this.createSuccessParticles(element);
        } else if (type === 'error') {
            this.createErrorParticles(element);
        }
        
        setTimeout(() => {
            element.classList.remove(`pulse-${type}`);
        }, 800);
    }
    
    // Typewriter effect
    typewriter(element, text, speed = 50) {
        element.textContent = '';
        let i = 0;
        
        const type = () => {
            if (i < text.length) {
                element.textContent += text.charAt(i);
                i++;
                setTimeout(type, speed + Math.random() * 20);
            }
        };
        
        type();
    }
    
    // Particle system methods
    createParticleExplosion(x, y, color) {
        for (let i = 0; i < 15; i++) {
            this.particles.push({
                x: x,
                y: y,
                vx: (Math.random() - 0.5) * 8,
                vy: (Math.random() - 0.5) * 8,
                life: 1,
                decay: 0.02,
                size: Math.random() * 4 + 2,
                color: color
            });
        }
    }
    
    createParticleStream(x, y, color) {
        for (let i = 0; i < 3; i++) {
            this.particles.push({
                x: x + (Math.random() - 0.5) * 20,
                y: y + (Math.random() - 0.5) * 20,
                vx: (Math.random() - 0.5) * 2,
                vy: -Math.random() * 3 - 1,
                life: 1,
                decay: 0.015,
                size: Math.random() * 3 + 1,
                color: color
            });
        }
    }
    
    createParticleTrail(x, y, color) {
        this.particles.push({
            x: x,
            y: y,
            vx: (Math.random() - 0.5) * 1,
            vy: (Math.random() - 0.5) * 1,
            life: 0.8,
            decay: 0.03,
            size: Math.random() * 2 + 1,
            color: color
        });
    }
    
    createCelebrationParticles() {
        const colors = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6'];
        
        for (let i = 0; i < 30; i++) {
            this.particles.push({
                x: window.innerWidth / 2,
                y: window.innerHeight / 2,
                vx: (Math.random() - 0.5) * 12,
                vy: -Math.random() * 8 - 2,
                life: 1,
                decay: 0.01,
                size: Math.random() * 6 + 3,
                color: colors[Math.floor(Math.random() * colors.length)]
            });
        }
    }
    
    createSuccessParticles(element) {
        const rect = element.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        
        for (let i = 0; i < 8; i++) {
            this.particles.push({
                x: centerX,
                y: centerY,
                vx: Math.cos(i * Math.PI / 4) * 3,
                vy: Math.sin(i * Math.PI / 4) * 3,
                life: 1,
                decay: 0.02,
                size: 3,
                color: '#10b981'
            });
        }
    }
    
    createErrorParticles(element) {
        const rect = element.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        
        for (let i = 0; i < 6; i++) {
            this.particles.push({
                x: centerX,
                y: centerY,
                vx: (Math.random() - 0.5) * 6,
                vy: -Math.random() * 4 - 1,
                life: 1,
                decay: 0.025,
                size: 4,
                color: '#ef4444'
            });
        }
    }
    
    animateConnectionParticles(connectionElement) {
        // This would need the path data to animate particles along the connection
        // For now, we'll create a simple effect
        const rect = connectionElement.getBoundingClientRect();
        
        for (let i = 0; i < 5; i++) {
            setTimeout(() => {
                this.particles.push({
                    x: rect.left + Math.random() * rect.width,
                    y: rect.top + Math.random() * rect.height,
                    vx: (Math.random() - 0.5) * 2,
                    vy: (Math.random() - 0.5) * 2,
                    life: 1,
                    decay: 0.02,
                    size: 2,
                    color: '#4f46e5'
                });
            }, i * 100);
        }
    }
    
    updateParticles() {
        this.particles = this.particles.filter(particle => {
            particle.x += particle.vx;
            particle.y += particle.vy;
            particle.vy += 0.1; // gravity
            particle.life -= particle.decay;
            
            return particle.life > 0;
        });
    }
    
    renderParticles() {
        this.particleCtx.clearRect(0, 0, this.particleCanvas.width, this.particleCanvas.height);
        
        this.particles.forEach(particle => {
            this.particleCtx.save();
            this.particleCtx.globalAlpha = particle.life;
            this.particleCtx.fillStyle = particle.color;
            this.particleCtx.beginPath();
            this.particleCtx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
            this.particleCtx.fill();
            this.particleCtx.restore();
        });
    }
    
    // Sound effects (optional)
    playSound(type) {
        // This would play sound effects if audio is enabled
        // For now, we'll just log the sound type
        console.log(`Playing sound: ${type}`);
    }
    
    // Cleanup all animations and particles
    cleanup() {
        this.activeAnimations.forEach(cleanup => cleanup());
        this.activeAnimations.clear();
        this.particles = [];
        
        if (this.particleCanvas && this.particleCanvas.parentNode) {
            this.particleCanvas.parentNode.removeChild(this.particleCanvas);
        }
    }
}

// Export for use in other modules
window.AnimationManager = AnimationManager;
/**
 * GOD-TIER ENGINE
 * Liquid Background & Inertial Physics
 */

const canvas = document.createElement('canvas');
canvas.id = 'liquid-canvas';
document.body.prepend(canvas);

const ctx = canvas.getContext('2d');
let time = 0;

// Resize
function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}
window.addEventListener('resize', resize);
resize();

// Mouse Tracking
let mouseX = 0, mouseY = 0;
let targetX = 0, targetY = 0;

// Mouse Tracking Removed for Performance and Native Cursor Restoration

// Liquid Blob Class
class Blob {
    constructor(x, y, color, speed) {
        this.x = x;
        this.y = y;
        this.color = color;
        this.speed = speed;
        this.angle = Math.random() * Math.PI * 2;
    }

    update() {
        this.angle += 0.002 * this.speed;
        this.x += Math.cos(this.angle) * 2;
        this.y += Math.sin(this.angle) * 2;

        // Mouse avoidance/attraction
        const dx = targetX - this.x;
        const dy = targetY - this.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < 400) {
            this.x -= dx * 0.005;
            this.y -= dy * 0.005;
        }
    }

    draw() {
        ctx.beginPath();
        const gradient = ctx.createRadialGradient(this.x, this.y, 0, this.x, this.y, 600);
        gradient.addColorStop(0, this.color);
        gradient.addColorStop(1, 'transparent');
        ctx.fillStyle = gradient;
        ctx.arc(this.x, this.y, 600, 0, Math.PI * 2);
        ctx.fill();
    }
}

const blobs = [
    new Blob(window.innerWidth * 0.2, window.innerHeight * 0.3, 'rgba(168, 85, 247, 0.4)', 1), // Purple
    new Blob(window.innerWidth * 0.8, window.innerHeight * 0.7, 'rgba(6, 182, 212, 0.3)', 1.5), // Cyan
    new Blob(window.innerWidth * 0.5, window.innerHeight * 0.5, 'rgba(236, 72, 153, 0.2)', 0.8)  // Pink
];

// Animation Loop
function animate() {
    // Clear with trail for motion blur feel
    ctx.fillStyle = 'rgba(3, 0, 20, 0.1)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Global filter optimization
    ctx.filter = 'blur(60px)';

    blobs.forEach(blob => {
        blob.update();
        blob.draw();
    });

    ctx.filter = 'none';

    time += 0.01;
    requestAnimationFrame(animate);
}

// Magnetic Buttons (Event Delegation for Dynamic Content)
let activeMagneticBtn = null;

document.addEventListener('mousemove', (e) => {
    const btn = e.target.closest('.btn-magnetic');

    // If we moved away from the active button, reset it
    if (activeMagneticBtn && activeMagneticBtn !== btn) {
        activeMagneticBtn.style.transform = 'translate(0, 0) scale(1)';
        activeMagneticBtn = null;
    }

    // If we are over a button, apply effect
    if (btn) {
        activeMagneticBtn = btn;
        const rect = btn.getBoundingClientRect();
        const x = e.clientX - rect.left - rect.width / 2;
        const y = e.clientY - rect.top - rect.height / 2;

        // Damping for smoother feel
        btn.style.transform = `translate(${x * 0.3}px, ${y * 0.3}px) scale(1.1)`;
    }
});

document.addEventListener('mouseleave', () => {
    if (activeMagneticBtn) {
        activeMagneticBtn.style.transform = 'translate(0, 0) scale(1)';
        activeMagneticBtn = null;
    }
});

animate();
console.log("🌌 GOD MODE: Liquid Engine Started");

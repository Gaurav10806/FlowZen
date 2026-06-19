/**
 * Simple Confetti Utility
 * Uses canvas-confetti from CDN if available, or falls back to simple implementation
 */
class ConfettiManager {
    constructor() {
        this.colors = ['#8b5cf6', '#3b82f6', '#10b981', '#f59e0b', '#ef4444'];
    }

    explode(origin = { x: 0.5, y: 0.5 }) {
        if (window.confetti) {
            window.confetti({
                particleCount: 100,
                spread: 70,
                origin: origin,
                colors: this.colors,
                zIndex: 99999
            });
        }
    }

    celebrate() {
        if (window.confetti) {
            var end = Date.now() + 2 * 1000;
            var colors = this.colors;

            (function frame() {
                window.confetti({
                    particleCount: 3,
                    angle: 60,
                    spread: 55,
                    origin: { x: 0 },
                    colors: colors,
                    zIndex: 99999
                });
                window.confetti({
                    particleCount: 3,
                    angle: 120,
                    spread: 55,
                    origin: { x: 1 },
                    colors: colors,
                    zIndex: 99999
                });

                if (Date.now() < end) {
                    requestAnimationFrame(frame);
                }
            }());
        }
    }
}

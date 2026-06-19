/**
 * Sound Manager - Handles UI Audio Feedback
 */
class SoundManager {
    constructor() {
        this.enabled = true; // Could load from user prefs
        this.sounds = {
            click: new Audio('/static/sounds/click.mp3'),
            connect: new Audio('/static/sounds/connect.mp3'),
            delete: new Audio('/static/sounds/delete.mp3'),
            success: new Audio('/static/sounds/success.mp3'),
            error: new Audio('/static/sounds/error.mp3'),
            notification: new Audio('/static/sounds/notification.mp3')
        };

        // Preload and set volume
        Object.values(this.sounds).forEach(sound => {
            sound.volume = 0.4;
            sound.load();
        });
    }

    play(soundName) {
        if (!this.enabled || !this.sounds[soundName]) return;

        // Clone node to allow overlapping sounds
        const sound = this.sounds[soundName].cloneNode();
        sound.volume = 0.4;
        sound.play().catch(e => console.debug('Sound play blocked:', e));
    }

    toggle() {
        this.enabled = !this.enabled;
        return this.enabled;
    }
}

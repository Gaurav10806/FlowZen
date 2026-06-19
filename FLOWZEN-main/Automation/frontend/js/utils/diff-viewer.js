/**
 * Simple JSON Diff Utility
 * Visualizes differences between two JSON objects
 */
class DiffViewer {
    constructor() {
        this.container = null;
    }

    show(oldObj, newObj) {
        this.createUI();
        const diff = this.computeDiff(oldObj, newObj);
        this.render(diff);
    }

    createUI() {
        // Remove existing
        const existing = document.getElementById('diff-modal');
        if (existing) existing.remove();

        this.container = document.createElement('div');
        this.container.id = 'diff-modal';
        this.container.style.cssText = `
            position: fixed; inset: 0; background: rgba(0,0,0,0.8); z-index: 10000;
            display: flex; align-items: center; justify-content: center; backdrop-filter: blur(5px);
        `;

        this.container.innerHTML = `
            <div class="glass-panel" style="width: 80%; height: 80%; display: flex; flex-direction: column; background: #1e1e1e; border-radius: 12px; overflow: hidden; border: 1px solid #333;">
                <div style="padding: 15px; border-bottom: 1px solid #333; display: flex; justify-content: space-between; align-items: center; background: #252526;">
                    <h3 style="margin: 0; color: #fff;">Version Comparison</h3>
                    <button onclick="document.getElementById('diff-modal').remove()" style="background: none; border: none; color: #ccc; cursor: pointer; font-size: 1.2rem;">&times;</button>
                </div>
                <div id="diff-content" style="flex: 1; overflow: auto; padding: 20px; font-family: monospace; font-size: 14px; color: #d4d4d4;"></div>
            </div>
        `;

        document.body.appendChild(this.container);
    }

    computeDiff(obj1, obj2) {
        // Simple line-by-line JSON string comparison
        const str1 = JSON.stringify(obj1, null, 2).split('\n');
        const str2 = JSON.stringify(obj2, null, 2).split('\n');

        // Use a simple diffing algorithm (LCS based or just line check)
        // For simplicity in this script, we'll mark Added/Removed lines
        // A real implementation would use 'diff' library

        let i = 0, j = 0;
        const diffs = [];

        while (i < str1.length || j < str2.length) {
            if (i < str1.length && j < str2.length && str1[i] === str2[j]) {
                diffs.push({ type: 'same', text: str1[i] });
                i++; j++;
            } else if (j < str2.length && (i >= str1.length || !str1.includes(str2[j]))) {
                diffs.push({ type: 'added', text: str2[j] });
                j++;
            } else if (i < str1.length && (j >= str2.length || !str2.includes(str1[i]))) {
                diffs.push({ type: 'removed', text: str1[i] });
                i++;
            } else {
                // Fallback for changed blocks
                diffs.push({ type: 'removed', text: str1[i] });
                diffs.push({ type: 'added', text: str2[j] });
                i++; j++;
            }
        }
        return diffs;
    }

    render(diffs) {
        const content = this.container.querySelector('#diff-content');

        diffs.forEach(line => {
            const div = document.createElement('div');
            div.textContent = line.text;
            div.style.whiteSpace = 'pre';

            if (line.type === 'added') {
                div.style.backgroundColor = 'rgba(16, 185, 129, 0.2)';
                div.style.color = '#34d399';
            } else if (line.type === 'removed') {
                div.style.backgroundColor = 'rgba(239, 68, 68, 0.2)';
                div.style.color = '#f87171';
                div.style.textDecoration = 'line-through';
                div.style.opacity = '0.7';
            } else {
                div.style.color = '#9ca3af';
            }

            content.appendChild(div);
        });
    }
}

window.DiffViewer = DiffViewer;

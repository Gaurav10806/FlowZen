/**
 * FLOWZEN UNIVERSAL TOAST SYSTEM
 * Reusable toast notification component.
 */

function showToast(message, type = "success") {
    // Ensure container exists
    let container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        container.style.cssText = "position: fixed; bottom: 25px; right: 25px; z-index: 10000; display: flex; flex-direction: column; gap: 12px; pointer-events: none;";
        document.body.appendChild(container);
    }

    // Create Toast Element
    const toast = document.createElement("div");
    toast.className = `flowzen-toast ${type}`;

    // Icon Selection
    let icon = "check-circle";
    if (type === "error") icon = "exclamation-circle";
    if (type === "warning") icon = "exclamation-triangle";
    if (type === "info") icon = "info-circle";

    toast.innerHTML = `
        <i class="fas fa-${icon}"></i>
        <span style="flex:1">${message}</span>
    `;

    // Append to container
    container.appendChild(toast);

    // Animate In
    // We use a small timeout to allow the DOM to render before adding the show class for transition
    setTimeout(() => toast.classList.add("show"), 10);

    // Auto Dismiss
    setTimeout(() => {
        toast.classList.remove("show");
        toast.classList.add("hide");
        setTimeout(() => toast.remove(), 300); // Wait for transition out
    }, 3000);
}

// Add CSS programmatically if not present (Self-contained)
const styleId = 'flowzen-toast-style';
if (!document.getElementById(styleId)) {
    const style = document.createElement('style');
    style.id = styleId;
    style.innerHTML = `
        .flowzen-toast {
            pointer-events: auto;
            min-width: 300px;
            max-width: 450px;
            background: white;
            padding: 14px 18px;
            border-radius: 12px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.08);
            border: 1px solid #E5E7EB;
            display: flex;
            align-items: center;
            gap: 12px;
            font-family: 'Outfit', sans-serif;
            font-weight: 500;
            font-size: 14px;
            color: #1F2937;
            opacity: 0;
            transform: translateY(20px);
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }
        
        .flowzen-toast.show {
            opacity: 1;
            transform: translateY(0);
        }
        
        .flowzen-toast.hide {
            opacity: 0;
            transform: translateY(-20px);
        }

        .flowzen-toast.success { border-left: 4px solid #10B981; }
        .flowzen-toast.success i { color: #10B981; }

        .flowzen-toast.error { border-left: 4px solid #EF4444; }
        .flowzen-toast.error i { color: #EF4444; }

        .flowzen-toast.warning { border-left: 4px solid #F59E0B; }
        .flowzen-toast.warning i { color: #F59E0B; }

        .flowzen-toast.info { border-left: 4px solid #3B82F6; }
        .flowzen-toast.info i { color: #3B82F6; }
    `;
    document.head.appendChild(style);
}

/**
 * Global Response Handler for Credentials API
 * Shows success/error toasts automatically based on standard API format
 */
async function handleApiResponse(response, successMsg = "Action successful!") {
    try {
        const data = await response.json();
        if (response.ok && (data.success || !data.error)) {
            showToast(data.message || successMsg, "success");
            return data;
        } else {
            const error = data.error || data.message || "An unexpected error occurred.";
            showToast(`❌ ${error}`, "error");
            return null;
        }
    } catch (e) {
        showToast("❌ Network Error or Invalid Response", "error");
        return null;
    }
}

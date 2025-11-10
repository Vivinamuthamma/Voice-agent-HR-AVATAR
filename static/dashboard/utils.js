// Utility functions for dashboard

// Utility functions
function showStatus(message, type) {
    const statusDiv = document.getElementById('systemStatus');
    if (statusDiv) {
        statusDiv.className = `alert alert-${type}`;
        statusDiv.innerHTML = `
            <div class="d-flex align-items-center">
                ${type === 'info' ? '<div class="spinner-border spinner-border-sm me-2" role="status"></div>' : ''}
                <span>${message}</span>
            </div>
        `;
        statusDiv.style.display = 'block';
    }
}

function hideStatus() {
    const statusDiv = document.getElementById('systemStatus');
    if (statusDiv) {
        statusDiv.style.display = 'none';
    }
}

// Make functions globally available
window.showStatus = showStatus;
window.hideStatus = hideStatus;

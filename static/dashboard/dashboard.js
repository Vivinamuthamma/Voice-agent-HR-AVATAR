// Dashboard JavaScript for AI Voice Interview System
// Main controller - handles initialization and coordination

let refreshInterval = null;

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Wait for all modules to load before initializing
    setTimeout(() => {
        loadDashboard();
        // Auto-refresh every 30 seconds
        refreshInterval = setInterval(loadDashboard, 30000);
    }, 100);
});

// Load complete dashboard data
async function loadDashboard() {
    try {
        if (typeof showStatus === 'function') {
            showStatus('Loading dashboard data...', 'info');
        }

        // Load sessions overview
        const sessionsResponse = await fetch('/api/dashboard/sessions');
        const sessionsData = await sessionsResponse.json();

        if (sessionsData.success) {
            updateOverviewCards(sessionsData.data);
            updateRecentSessionsTable(sessionsData.data.sessions);
            updateCharts(sessionsData.data);
        }

        // Load active interviews
        const activeResponse = await fetch('/api/dashboard/active-interviews');
        const activeData = await activeResponse.json();

        if (activeData.success) {
            updateActiveInterviewsTable(activeData.active_interviews);
        }

        if (typeof showStatus === 'function') {
            showStatus('Dashboard updated successfully', 'success');
            setTimeout(() => {
                if (typeof hideStatus === 'function') {
                    hideStatus();
                }
            }, 3000);
        }

    } catch (error) {
        console.error('Dashboard load error:', error);
        if (typeof showStatus === 'function') {
            showStatus('Failed to load dashboard data', 'danger');
        }
    }
}

function refreshDashboard() {
    loadDashboard();
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
});

// Make functions globally available
window.loadDashboard = loadDashboard;
window.refreshDashboard = refreshDashboard;

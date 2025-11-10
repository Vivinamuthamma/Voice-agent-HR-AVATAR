// Chart functionality for dashboard

let statusChart = null;
let timelineChart = null;

// Update charts with session data
function updateCharts(data) {
    // Status distribution chart
    const statusCtx = document.getElementById('statusChart').getContext('2d');
    const statusData = {
        labels: ['Active', 'Completed', 'Failed'],
        datasets: [{
            data: [data.active_sessions, data.completed_sessions, data.failed_sessions],
            backgroundColor: ['#28a745', '#007bff', '#dc3545'],
            borderWidth: 1
        }]
    };

    if (statusChart) {
        statusChart.destroy();
    }

    statusChart = new Chart(statusCtx, {
        type: 'doughnut',
        data: statusData,
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });

    // Timeline chart (simplified - showing last 7 days)
    const timelineCtx = document.getElementById('timelineChart').getContext('2d');

    // Group sessions by date
    const sessionsByDate = {};
    data.sessions.forEach(session => {
        const date = new Date(session.created_at).toLocaleDateString();
        sessionsByDate[date] = (sessionsByDate[date] || 0) + 1;
    });

    const dates = Object.keys(sessionsByDate).sort();
    const counts = dates.map(date => sessionsByDate[date]);

    const timelineData = {
        labels: dates,
        datasets: [{
            label: 'Sessions Created',
            data: counts,
            borderColor: '#007bff',
            backgroundColor: 'rgba(0, 123, 255, 0.1)',
            tension: 0.4,
            fill: true
        }]
    };

    if (timelineChart) {
        timelineChart.destroy();
    }

    timelineChart = new Chart(timelineCtx, {
        type: 'line',
        data: timelineData,
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1
                    }
                }
            }
        }
    });
}

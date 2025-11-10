// Table management functions for dashboard

// Update overview cards with session statistics
function updateOverviewCards(data) {
    document.getElementById('totalSessions').textContent = data.total_sessions;
    document.getElementById('activeInterviews').textContent = data.active_sessions;
    document.getElementById('completedSessions').textContent = data.completed_sessions;
    document.getElementById('failedSessions').textContent = data.failed_sessions;
}

// Update active interviews table
function updateActiveInterviewsTable(activeInterviews) {
    const tbody = document.getElementById('activeInterviewsBody');

    if (activeInterviews.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center text-muted">
                    <i class="fas fa-info-circle me-2"></i>
                    No active interviews at the moment
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = activeInterviews.map(interview => {
        const progressPercent = interview.total_questions > 0 ?
            Math.round((interview.current_question / interview.total_questions) * 100) : 0;

        const startedTime = new Date(interview.started_at).toLocaleString();

        return `
            <tr>
                <td>${interview.candidate_name}</td>
                <td>${interview.position}</td>
                <td>
                    <code class="small">${interview.room_name}</code>
                </td>
                <td>
                    <span class="badge bg-${interview.participants > 0 ? 'success' : 'warning'}">
                        ${interview.participants} participant${interview.participants !== 1 ? 's' : ''}
                    </span>
                </td>
                <td>
                    <div class="progress" style="width: 100px;">
                        <div class="progress-bar bg-primary" role="progressbar"
                             style="width: ${progressPercent}%" aria-valuenow="${progressPercent}"
                             aria-valuemin="0" aria-valuemax="100">
                            ${progressPercent}%
                        </div>
                    </div>
                    <small class="text-muted">
                        ${interview.responses_count}/${interview.total_questions} questions
                    </small>
                </td>
                <td><small>${startedTime}</small></td>
                <td>
                    <button class="btn btn-sm btn-outline-primary me-1"
                            onclick="viewSession('${interview.session_id}')">
                        <i class="fas fa-eye"></i>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

// Update recent sessions table
function updateRecentSessionsTable(sessions) {
    const tbody = document.getElementById('recentSessionsBody');

    if (sessions.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center text-muted">
                    <i class="fas fa-info-circle me-2"></i>
                    No sessions found
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = sessions.map(session => {
        const createdTime = new Date(session.created_at).toLocaleString();
        const statusBadge = getStatusBadge(session.status);
        const questionCount = session.questions ? session.questions.length : 0;

        return `
            <tr>
                <td>${session.candidate_name}</td>
                <td>${session.position}</td>
                <td>${statusBadge}</td>
                <td><small>${createdTime}</small></td>
                <td>${questionCount}</td>
                <td>
                    <button class="btn btn-sm btn-outline-primary me-1"
                            onclick="viewSession('${session.session_id}')">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-success me-1"
                            onclick="downloadReport('${session.session_id}')">
                        <i class="fas fa-download"></i>
                    </button>
                    ${session.email ? `
                        <button class="btn btn-sm btn-outline-secondary"
                                onclick="sendReport('${session.session_id}')">
                            <i class="fas fa-envelope"></i>
                        </button>
                    ` : ''}
                </td>
            </tr>
        `;
    }).join('');
}

// Get status badge HTML
function getStatusBadge(status) {
    const statusConfig = {
        'created': { class: 'secondary', icon: 'clock' },
        'ready': { class: 'info', icon: 'check-circle' },
        'active': { class: 'success', icon: 'play-circle' },
        'interviewing': { class: 'success', icon: 'microphone' },
        'completed': { class: 'primary', icon: 'check-double' },
        'finished': { class: 'primary', icon: 'check-double' },
        'failed': { class: 'danger', icon: 'exclamation-triangle' },
        'error': { class: 'danger', icon: 'exclamation-triangle' }
    };

    const config = statusConfig[status] || { class: 'secondary', icon: 'question-circle' };
    return `<span class="badge bg-${config.class}"><i class="fas fa-${config.icon} me-1"></i>${status || 'unknown'}</span>`;
}

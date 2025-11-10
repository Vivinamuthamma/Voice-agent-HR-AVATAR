 // Action functions for dashboard (downloads, views, etc.)

// Make functions globally available
window.downloadReport = downloadReport;
window.sendReport = sendReport;
window.viewTranscript = viewTranscript;
window.downloadTranscript = downloadTranscript;
async function downloadReport(sessionId) {
    try {
        const response = await fetch(`/api/reports/${sessionId}`);

        if (!response.ok) {
            // Try to get error message from response
            try {
                const errorData = await response.json();
                alert(`Error: ${errorData.error || 'Failed to download report'}`);
            } catch (e) {
                alert(`Error: Report download failed (${response.status})`);
            }
            return;
        }

        // Get the PDF data as blob
        const pdfBlob = await response.blob();

        // Create and trigger download
        const url = URL.createObjectURL(pdfBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `interview_report_${sessionId.substring(0, 8)}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

    } catch (error) {
        console.error('Download error:', error);
        alert('Failed to download report');
    }
}

async function sendReport(sessionId) {
    if (!confirm('Send interview report via email?')) {
        return;
    }

    try {
        const response = await fetch(`/api/reports/${sessionId}/send`, {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            alert('Report sent successfully!');
        } else {
            alert(`Error: ${data.error}`);
        }
    } catch (error) {
        console.error('Send report error:', error);
        alert('Failed to send report');
    }
}

async function viewTranscript(sessionId) {
    try {
        // Use the dedicated transcript endpoint that returns clean formatted data
        const response = await fetch(`/api/dashboard/session/${sessionId}/transcript`);
        const data = await response.json();

        if (!data.success) {
            alert(`Error: ${data.error}`);
            return;
        }

        const transcript = data.data.transcript || [];
        const interview = {
            candidate_name: data.data.candidate_name,
            position: data.data.position,
            session_id: sessionId
        };

        if (transcript.length === 0) {
            alert('No transcript available for this interview');
            return;
        }

        // Create a modal to display the transcript
        const modalHtml = `
            <div class="modal fade" id="transcriptModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Interview Transcript - ${interview.candidate_name}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="transcript-content" style="max-height: 400px; overflow-y: auto;">
                                ${transcript.map(entry => `
                                    <div class="transcript-entry mb-2">
                                        <div class="text-monospace">${entry}</div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            <button type="button" class="btn btn-primary" onclick="downloadTranscript('${sessionId}')">Download Transcript</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Remove existing modal if present
        const existingModal = document.getElementById('transcriptModal');
        if (existingModal) {
            existingModal.remove();
        }

        // Add modal to body
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('transcriptModal'));
        modal.show();

    } catch (error) {
        console.error('Transcript view error:', error);
        alert('Failed to load transcript');
    }
}

async function downloadTranscript(sessionId) {
    try {
        // Use the dedicated transcript endpoint that returns clean formatted data
        const response = await fetch(`/api/dashboard/session/${sessionId}/transcript`);
        const data = await response.json();

        if (!data.success) {
            alert(`Error: ${data.error}`);
            return;
        }

        const transcript = data.data.transcript || [];
        const interview = {
            candidate_name: data.data.candidate_name,
            position: data.data.position,
            session_id: sessionId
        };

        if (transcript.length === 0) {
            alert('No transcript available for this interview');
            return;
        }

        // Create transcript text
        let transcriptText = `Interview Transcript\n`;
        transcriptText += `Candidate: ${interview.candidate_name}\n`;
        transcriptText += `Position: ${interview.position}\n`;
        transcriptText += `Session ID: ${sessionId}\n`;
        transcriptText += `Date: ${new Date().toLocaleString()}\n\n`;

        transcript.forEach((entry, index) => {
            transcriptText += `${entry}\n`;
        });

        // Download as text file
        const blob = new Blob([transcriptText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `interview_transcript_${sessionId}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

    } catch (error) {
        console.error('Transcript download error:', error);
        alert('Failed to download transcript');
    }
}



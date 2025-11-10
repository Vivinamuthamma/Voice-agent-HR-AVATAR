from flask import Blueprint, render_template, jsonify, current_app, g
import os
import json
from pathlib import Path
from datetime import datetime
from async_manager import run_async_in_new_loop

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
def dashboard():
    """Serve the dashboard page"""
    return render_template('dashboard.html')

@dashboard_bp.route('/api/dashboard/sessions')
def get_sessions():
    """Get all interview sessions for dashboard"""
    try:
        # Get all session files
        sessions_dir = Path(current_app.root_path).parent / 'interview_sessions'
        sessions = []
        stats = {
            'total_sessions': 0,
            'completed_sessions': 0,
            'active_sessions': 0,
            'failed_sessions': 0,
            'total_transcripts': 0,
            'total_questions': 0
        }

        if sessions_dir.exists():
            for session_file in sessions_dir.glob('*.json'):
                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        session_data = json.load(f)

                    # Format session for dashboard
                    session_info = {
                        'session_id': session_data.get('session_id', session_file.stem),
                        'candidate_name': session_data.get('candidate_name', 'Unknown'),
                        'position': session_data.get('position', 'Unknown'),
                        'email': session_data.get('email', 'Unknown'),
                        'status': session_data.get('status', 'unknown'),
                        'created_at': session_data.get('created_at', 'Unknown'),
                        'completed_at': session_data.get('completed_at', None),
                        'room_name': session_data.get('room_name', None),
                        'transcript_count': len(session_data.get('transcript', [])),
                        'questions_count': len(session_data.get('questions', [])),
                        'has_analysis': bool(session_data.get('analysis')),
                        'has_evaluation': bool(session_data.get('evaluation'))
                    }
                    sessions.append(session_info)

                    # Update stats
                    stats['total_sessions'] += 1
                    status = session_data.get('status')
                    if status == 'completed':
                        stats['completed_sessions'] += 1
                    elif status == 'interviewing':
                        stats['active_sessions'] += 1
                    elif status in ['failed', 'error']:
                        stats['failed_sessions'] += 1

                    stats['total_transcripts'] += len(session_data.get('transcript', []))
                    stats['total_questions'] += len(session_data.get('questions', []))

                except Exception as e:
                    current_app.logger.warning(f"Error reading session file {session_file}: {e}")
                    continue

        # Sort by creation date (newest first)
        sessions.sort(key=lambda x: x.get('created_at', ''), reverse=True)

        return jsonify({
            'success': True,
            'data': {
                'sessions': sessions,
                **stats
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error getting sessions: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to load sessions: {str(e)}'
        }), 500

@dashboard_bp.route('/api/dashboard/stats')
def get_stats():
    """Get dashboard statistics"""
    try:
        sessions_dir = Path(current_app.root_path).parent / 'interview_sessions'
        stats = {
            'total_sessions': 0,
            'completed_sessions': 0,
            'active_sessions': 0,
            'total_transcripts': 0,
            'total_questions': 0
        }

        if sessions_dir.exists():
            for session_file in sessions_dir.glob('*.json'):
                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        session_data = json.load(f)

                    stats['total_sessions'] += 1

                    if session_data.get('status') == 'completed':
                        stats['completed_sessions'] += 1
                    elif session_data.get('status') == 'interviewing':
                        stats['active_sessions'] += 1

                    stats['total_transcripts'] += len(session_data.get('transcript', []))
                    stats['total_questions'] += len(session_data.get('questions', []))

                except Exception as e:
                    current_app.logger.warning(f"Error reading session file for stats {session_file}: {e}")
                    continue

        return jsonify({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        current_app.logger.error(f"Error getting stats: {e}")
        return jsonify({
            'success': False,
            'error': f'Failed to load statistics: {str(e)}'
        }), 500

from flask import Blueprint, request, jsonify, send_file, current_app
import os
import json
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from app.services.session_service import InterviewSessionService
from app.services.email_service import EmailService
from app.core.config import Config
from app.core.errors import ValidationError, SessionError, EmailError
from async_manager import run_async_in_new_loop, run_async_with_cleanup

reports_bp = Blueprint('reports', __name__)

session_service = InterviewSessionService()

def create_pdf_report(session_data, session_id):
    """Create a professional PDF report from session data"""
    buffer = BytesIO()

    # Create the PDF document
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )

    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=20,
        textColor=colors.darkgreen
    )

    section_style = ParagraphStyle(
        'CustomSection',
        parent=styles['Heading3'],
        fontSize=14,
        spaceAfter=15,
        textColor=colors.darkblue
    )

    normal_style = styles['Normal']
    normal_style.fontSize = 11
    normal_style.leading = 14

    # Build the PDF content
    content = []

    # Title
    content.append(Paragraph("Interview Assessment Report", title_style))
    content.append(Spacer(1, 0.25*inch))

    # Candidate Information Section
    content.append(Paragraph("Candidate Information", subtitle_style))

    candidate_info = [
        ["Candidate Name:", session_data.get('candidate_name', 'N/A')],
        ["Position Applied:", session_data.get('position', 'N/A')],
        ["Email:", session_data.get('email', 'N/A')],
        ["Session ID:", session_id],
        ["Interview Date:", session_data.get('created_at', 'N/A')],
        ["Completion Date:", session_data.get('completed_at', 'N/A')]
    ]

    candidate_table = Table(candidate_info, colWidths=[2*inch, 4*inch])
    candidate_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    content.append(candidate_table)
    content.append(Spacer(1, 0.25*inch))

    # Analysis Section
    analysis = session_data.get('analysis', {})
    if analysis:
        content.append(Paragraph("Document Analysis", subtitle_style))

        analysis_text = ""
        if 'summary' in analysis:
            analysis_text += f"<b>Summary:</b> {analysis['summary']}<br/><br/>"
        if 'key_skills' in analysis:
            analysis_text += f"<b>Key Skills Identified:</b> {analysis['key_skills']}<br/><br/>"
        if 'experience_level' in analysis:
            analysis_text += f"<b>Experience Level:</b> {analysis['experience_level']}<br/><br/>"
        if 'cultural_fit' in analysis:
            analysis_text += f"<b>Cultural Fit Assessment:</b> {analysis['cultural_fit']}<br/><br/>"

        content.append(Paragraph(analysis_text, normal_style))
        content.append(Spacer(1, 0.25*inch))

    # Interview Questions Section
    questions = session_data.get('questions', [])
    if questions:
        content.append(Paragraph("Interview Questions", subtitle_style))

        for i, question in enumerate(questions, 1):
            content.append(Paragraph(f"Question {i}:", section_style))
            # Handle both string and dict formats
            if isinstance(question, dict):
                question_text = question.get('question', str(question))
            else:
                question_text = str(question)
            content.append(Paragraph(question_text, normal_style))
            content.append(Spacer(1, 0.1*inch))

        content.append(Spacer(1, 0.25*inch))

    # Transcript Section
    transcript = session_data.get('transcript', [])
    if transcript:
        content.append(Paragraph("Interview Transcript", subtitle_style))

        # Format transcript entries
        transcript_content = []
        for entry in transcript:
            if isinstance(entry, dict):
                speaker = entry.get('speaker', 'unknown')
                text = entry.get('text', '').strip()
            else:
                # Handle string entries
                text = str(entry).strip()
                speaker = 'unknown'

            if not text:
                continue

            # Format speaker
            if speaker == 'agent':
                speaker_name = "🤖 Interviewer"
            elif speaker == 'candidate':
                speaker_name = "👤 Candidate"
            else:
                speaker_name = speaker.title()

            transcript_content.append(f"<b>{speaker_name}:</b> {text}")

        # Join transcript entries with line breaks
        transcript_text = "<br/><br/>".join(transcript_content)
        content.append(Paragraph(transcript_text, normal_style))
        content.append(Spacer(1, 0.25*inch))

    # Evaluation Section
    evaluation = session_data.get('evaluation', {})
    if evaluation:
        content.append(Paragraph("Final Evaluation", subtitle_style))

        eval_text = ""
        if isinstance(evaluation, dict):
            if 'overall_rating' in evaluation:
                eval_text += f"<b>Overall Rating:</b> {evaluation['overall_rating']}/10<br/><br/>"
            if 'strengths' in evaluation:
                eval_text += f"<b>Strengths:</b> {evaluation['strengths']}<br/><br/>"
            if 'weaknesses' in evaluation:
                eval_text += f"<b>Areas for Improvement:</b> {evaluation['weaknesses']}<br/><br/>"
            if 'recommendation' in evaluation:
                eval_text += f"<b>Recommendation:</b> {evaluation['recommendation']}<br/><br/>"
            if 'notes' in evaluation:
                eval_text += f"<b>Additional Notes:</b> {evaluation['notes']}<br/><br/>"
        else:
            eval_text = f"<b>Evaluation:</b> {str(evaluation)}<br/><br/>"

        content.append(Paragraph(eval_text, normal_style))

    # Build the PDF
    doc.build(content)
    buffer.seek(0)
    return buffer

@reports_bp.route('/api/reports/<session_id>', methods=['GET'])
def download_report(session_id):
    """Download interview report as PDF."""
    try:
        session_data = run_async_in_new_loop(session_service.get_session(session_id))
        if not session_data:
            raise SessionError(f'Session {session_id} not found', session_id)

        # Check if session has basic data (questions or analysis)
        questions = session_data.get('questions', [])
        analysis = session_data.get('analysis', {})
        if not questions and not analysis:
            raise ValidationError('Report not available - no interview data recorded')

        # Generate PDF report
        pdf_buffer = create_pdf_report(session_data, session_id)

        # Return PDF file for download
        filename = f"interview_report_{session_id}.pdf"
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )

    except SessionError as e:
        return jsonify({
            'success': False,
            'error': e.message
        }), e.status_code
    except ValidationError as e:
        return jsonify({
            'success': False,
            'error': e.message
        }), e.status_code
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to generate report: {str(e)}'
        }), 500


@reports_bp.route('/api/reports/<session_id>/send', methods=['POST'])
def send_report_email(session_id):
    """Send interview report via email."""
    try:
        session_data = run_async_in_new_loop(session_service.get_session(session_id))
        if not session_data:
            raise SessionError(f'Session {session_id} not found', session_id)

        # Check if session has basic data (questions or analysis)
        questions = session_data.get('questions', [])
        analysis = session_data.get('analysis', {})
        if not questions and not analysis:
            raise ValidationError('Cannot send report - no interview data recorded')

        candidate_email = session_data.get('email')
        if not candidate_email:
            raise ValidationError('Candidate email not found in session')

        # Check email configuration
        config = Config()
        if not all([config.SMTP_USERNAME, config.SMTP_PASSWORD, config.HR_EMAIL]):
            raise EmailError('Email service not configured - missing SMTP credentials or HR email')

        # Format transcript in simple readable format
        raw_transcript = session_data.get('transcript', [])
        formatted_transcript = []
        for entry in raw_transcript:
            speaker = entry.get('speaker', 'unknown')
            text = entry.get('text', '').strip()

            # Skip empty entries
            if not text:
                continue

            # Format as simple speaker: "text" format
            if speaker == 'agent':
                formatted_entry = f"agent: \"{text}\""
            elif speaker == 'candidate':
                formatted_entry = f"candidate: \"{text}\""
            else:
                formatted_entry = f"{speaker}: \"{text}\""

            formatted_transcript.append(formatted_entry)

        # Create report data
        report_data = {
            'session_id': session_id,
            'candidate_name': session_data.get('candidate_name'),
            'position': session_data.get('position'),
            'email': session_data.get('email'),
            'created_at': session_data.get('created_at'),
            'completed_at': session_data.get('completed_at'),
            'questions': session_data.get('questions', []),
            'responses': session_data.get('responses', []),
            'analysis': session_data.get('analysis', {}),
            'transcript': formatted_transcript,
            'evaluation': session_data.get('evaluation', {})
        }

        # Create email service
        email_service = EmailService(
            config.SMTP_SERVER,
            config.SMTP_PORT,
            config.SMTP_USERNAME,
            config.SMTP_PASSWORD
        )

        # Generate PDF report for email attachment
        pdf_buffer = create_pdf_report(session_data, session_id)
        pdf_data = pdf_buffer.getvalue()

        # Send report to both candidate and HR
        success = email_service.send_interview_report_with_pdf(candidate_email, pdf_data, session_id)

        if not success:
            raise EmailError('Failed to send report emails')

        return jsonify({
            'success': True,
            'message': 'Report sent successfully'
        })

    except SessionError as e:
        return jsonify({
            'success': False,
            'error': e.message
        }), e.status_code
    except ValidationError as e:
        return jsonify({
            'success': False,
            'error': e.message
        }), e.status_code
    except EmailError as e:
        return jsonify({
            'success': False,
            'error': e.message
        }), e.status_code
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to send report: {str(e)}'
        }), 500

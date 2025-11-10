from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import os
import asyncio
import logging
from app.services.document_service import DocumentProcessingService
from app.services.interview_service import InterviewService
from app.core.config import Config
from app.core.errors import ValidationError, FileProcessingError
from async_manager import run_async_with_cleanup, run_async_in_new_loop

files_bp = Blueprint('files', __name__)

document_service = DocumentProcessingService()
interview_service = InterviewService()
logger = logging.getLogger(__name__)

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

@files_bp.route('/api/upload', methods=['POST'])
def upload_files():
    """Upload and process job description and resume files"""
    try:
        if 'jd_file' not in request.files or 'resume_file' not in request.files:
            return jsonify({
                "error": "Both job description and resume files are required"
            }), 400

        jd_file = request.files['jd_file']
        resume_file = request.files['resume_file']

        if jd_file.filename == '' or resume_file.filename == '':
            return jsonify({"error": "Please select both files"}), 400

        # Check file sizes (10MB limit)
        max_size = 10 * 1024 * 1024  # 10MB
        jd_content = jd_file.read()
        resume_content = resume_file.read()

        if len(jd_content) > max_size or len(resume_content) > max_size:
            return jsonify({"error": "File size too large. Maximum 10MB per file."}), 400

        # Extract text from files
        jd_filename = jd_file.filename or "job_description.txt"
        resume_filename = resume_file.filename or "resume.txt"

        try:
            jd_text = document_service.extract_text_from_file(jd_content, jd_filename)
            resume_text = document_service.extract_text_from_file(resume_content, resume_filename)
        except Exception as e:
            return jsonify({"error": f"File processing failed: {str(e)}"}), 400

        if not jd_text.strip() or not resume_text.strip():
            return jsonify({"error": "Files appear to be empty or unreadable"}), 400

        return jsonify({
            "success": True,
            "jd_text": jd_text[:500] + "..." if len(jd_text) > 500 else jd_text,
            "resume_text": resume_text[:500] + "..." if len(resume_text) > 500 else resume_text,
            "jd_full": jd_text,
            "resume_full": resume_text
        })

    except Exception as e:
        logger.error(f"File upload error: {e}")
        return jsonify({"error": f"File processing failed: {str(e)}"}), 500

@files_bp.route('/api/analyze', methods=['POST'])
def analyze_documents():
    """Analyze documents with AI"""
    try:
        data = request.get_json()
        jd_text = data.get('jd_text', '')
        resume_text = data.get('resume_text', '')

        if not jd_text or not resume_text:
            return jsonify(
                {"error": "Job description and resume text are required"}), 400

        # Run analysis using proper async utility in new event loop
        analysis = run_async_in_new_loop(
            interview_service.analyze_documents(jd_text, resume_text),
            timeout=30.0
        )

        return jsonify({"success": True, "analysis": analysis})

    except Exception as e:
        logger.error(f"Document analysis error: {e}")
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 500

@files_bp.route('/api/generate-questions', methods=['POST'])
def generate_questions():
    """Generate interview questions"""
    try:
        data = request.get_json()
        jd_text = data.get('jd_text', '')
        resume_text = data.get('resume_text', '')
        num_questions = int(data.get('num_questions', 6))

        if not jd_text or not resume_text:
            return jsonify(
                {"error": "Job description and resume text are required"}), 400

        # Validate number of questions
        if num_questions < 1 or num_questions > 20:
            return jsonify({"error": "Number of questions must be between 1 and 20"}), 400

        # Run question generation using proper async utility in new event loop
        questions = run_async_in_new_loop(
            interview_service.generate_interview_questions(
                jd_text, resume_text, num_questions),
            timeout=30.0
        )

        return jsonify({"success": True, "questions": questions})

    except Exception as e:
        logger.error(f"Question generation error: {e}")
        return jsonify({"error": f"Question generation failed: {str(e)}"}), 500

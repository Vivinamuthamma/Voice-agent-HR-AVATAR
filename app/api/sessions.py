from flask import Blueprint, request, jsonify, g
import json
import logging
import asyncio
from app.services.email_service import EmailService
from app.services.session_service import InterviewSessionService
from app.services.livekit_service import LiveKitService
from app.services.room_service import RoomService
from app.services.session_operations import SessionOperations
from flask import current_app
from app.core.errors import ValidationError, SessionError
from app.core.validation import InputValidator
from app.core.response import APIResponse
from async_manager import AsyncLiveKitManager, run_async_with_cleanup, run_async_in_new_loop

sessions_bp = Blueprint('sessions', __name__)

session_service = InterviewSessionService()
email_service = EmailService()
logger = logging.getLogger(__name__)



def _validate_session_input(data):
    """Validate and sanitize session creation input data."""
    if not data:
        raise ValidationError("No data provided")

    # Validate required fields
    required_fields = ['candidate_name', 'position', 'email']
    for field in required_fields:
        value = data.get(field)
        if not value or not isinstance(value, str) or not value.strip():
            raise ValidationError(f"Missing or invalid required field: {field}")

    # Sanitize and validate
    candidate_name = data['candidate_name'].strip()[:100]
    position = data['position'].strip()[:200]
    email = data['email'].strip().lower()

    if '@' not in email or '.' not in email:
        raise ValidationError("Invalid email format")

    # Validate optional fields
    questions = data.get('questions', [])
    if questions and not isinstance(questions, list):
        raise ValidationError("Questions must be a list")

    analysis = data.get('analysis', {})
    if analysis and not isinstance(analysis, dict):
        raise ValidationError("Analysis must be a dictionary")

    jd_full = data.get('jd_full', '')
    resume_full = data.get('resume_full', '')
    if jd_full and not isinstance(jd_full, str):
        raise ValidationError("JD full text must be a string")
    if resume_full and not isinstance(resume_full, str):
        raise ValidationError("Resume full text must be a string")

    return {
        'candidate_name': candidate_name,
        'position': position,
        'email': email,
        'questions': questions,
        'analysis': analysis,
        'jd_full': jd_full,
        'resume_full': resume_full
    }

def _create_livekit_room(livekit_manager, room_name):
    """Create LiveKit room with error handling."""
    if not livekit_manager:
        raise SessionError("LiveKit service not available")

    try:
        room_result = run_async_in_new_loop(livekit_manager.create_room_async(room_name))
        if not room_result or not room_result.get("success"):
            error_msg = room_result.get('error', 'Unknown error') if room_result else 'No response'
            raise SessionError(f"Failed to create room: {error_msg}")
        return room_result
    except Exception as e:
        raise SessionError(f"Room creation failed: {str(e)}")

def _generate_livekit_tokens(livekit_manager, room_name, candidate_name):
    """Generate LiveKit tokens for session."""
    try:
        candidate_token = livekit_manager.generate_token(room_name, candidate_name)
        agent_token = livekit_manager.generate_token(room_name, 'interview_agent', is_agent=True)

        if not candidate_token or not agent_token:
            raise SessionError("Failed to generate access tokens")

        return candidate_token, agent_token
    except Exception as e:
        raise SessionError(f"Token generation failed: {str(e)}")



@sessions_bp.route('/api/create-session', methods=['POST'])
def create_session():
    """Create interview session with robust error handling and input validation"""
    try:
        # Validate content type
        if not request.is_json:
            return APIResponse.error("Request must be JSON", "validation_error", 400)

        data = request.get_json()
        validated_data = InputValidator.validate_session_data(data)

        logger.info(f"Creating session for candidate: {validated_data['candidate_name']}, position: {validated_data['position']}")

        # Initialize services
        livekit_manager = getattr(g, 'livekit_manager', None)
        if not livekit_manager:
            return APIResponse.error("LiveKit service not available", "service_error", 503)

        livekit_service = LiveKitService(
            url=current_app.config['LIVEKIT_URL'],
            api_key=current_app.config['LIVEKIT_API_KEY'],
            api_secret=current_app.config['LIVEKIT_API_SECRET']
        )
        room_service = RoomService(livekit_service)
        session_ops = SessionOperations(session_service, room_service)

        # Create complete session with room and tokens
        result = run_async_in_new_loop(session_ops.create_complete_session(validated_data))

        if not result.get("success"):
            return APIResponse.error(result.get("error", "Session creation failed"), "creation_error", 500)



        logger.info(f"Session created successfully: {result['session_id']}")
        return APIResponse.success({
            "session_id": result["session_id"],
            "room_name": result["room_name"],
            "candidate_token": result["candidate_token"],
            "livekit_url": current_app.config['LIVEKIT_URL']
        }, "Session created successfully")

    except Exception as e:
        logger.error(f"Session creation error: {e}", exc_info=True)
        return APIResponse.handle_exception(e)

@sessions_bp.route('/api/session/<session_id>', methods=['GET'])
def get_session(session_id):
    """Get session data"""
    try:
        session_id = InputValidator.validate_session_id(session_id)
        session_data = run_async_in_new_loop(session_service.get_session(session_id))
        if not session_data:
            return APIResponse.not_found("Session", session_id)
        return APIResponse.success({"session": session_data})
    except Exception as e:
        logger.error(f"Session retrieval error: {e}")
        return APIResponse.handle_exception(e)

@sessions_bp.route('/api/session/<session_id>', methods=['PUT'])
def update_session(session_id):
    """Update session data"""
    try:
        session_id = InputValidator.validate_session_id(session_id)

        if not request.is_json:
            return APIResponse.error("Request must be JSON", "validation_error", 400)

        data = request.get_json()

        session_data = run_async_in_new_loop(session_service.get_session(session_id))
        if not session_data:
            return APIResponse.not_found("Session", session_id)

        updates = data.copy()

        # Special handling for responses - merge them into questions
        if 'responses' in updates and isinstance(updates['responses'], list):
            responses = updates['responses']
            questions = session_data.get('questions', [])

            # Create a mapping of question_id to transcription
            response_map = {}
            for response in responses:
                if isinstance(response, dict) and 'question_id' in response and 'answer' in response:
                    response_map[response['question_id']] = response['answer']

            # Update questions with transcriptions
            for question in questions:
                if isinstance(question, dict) and 'id' in question:
                    question_id = question['id']
                    if question_id in response_map:
                        question['transcription'] = response_map[question_id]

            # Update the questions in updates
            updates['questions'] = questions

            # Also keep the responses array for backward compatibility
            updates['responses'] = [r['answer'] if isinstance(r, dict) and 'answer' in r else str(r) for r in responses]

        success = run_async_in_new_loop(session_service.update_session(session_id, updates))
        if not success:
            return APIResponse.error("Session update failed", "update_error", 500)

        return APIResponse.success(message="Session updated successfully")

    except Exception as e:
        logger.error(f"Session update error: {e}")
        return APIResponse.handle_exception(e)

@sessions_bp.route('/api/session/by-room/<room_name>')
def get_session_by_room(room_name):
    """Get session by room name"""
    try:
        room_name = InputValidator.validate_room_name(room_name)
        sessions = run_async_in_new_loop(session_service.list_sessions())
        for session_data in sessions:
            if session_data.get('room_name') == room_name:
                return APIResponse.success({
                    "session_id": session_data['session_id'],
                    "session": session_data
                })
        return APIResponse.not_found("Session", f"room:{room_name}")

    except Exception as e:
        logger.error(f"Session retrieval error: {e}")
        return APIResponse.handle_exception(e)

@sessions_bp.route('/api/test/create-room/<room_name>')
def create_test_room(room_name):
    """Create a test room for testing purposes"""
    livekit_manager = getattr(g, 'livekit_manager', None)
    if not livekit_manager:
        return jsonify({"error": "LiveKit service not available"}), 503

    async def _create_room():
        return await livekit_manager.create_room_async(room_name)

    try:
        result = run_async_with_cleanup(_create_room())
        return jsonify(result)
    except Exception as e:
        logger.error(f"Room creation failed: {e}")
        return jsonify({"error": "Failed to create room"}), 500

@sessions_bp.route('/api/livekit/room/<room_name>/participants')
def get_room_participants(room_name):
    """Get participants in a LiveKit room"""
    livekit_manager = getattr(g, 'livekit_manager', None)
    if not livekit_manager:
        return jsonify({"error": "LiveKit service not available"}), 503

    async def _get_participants():
        return await livekit_manager.list_participants_async(room_name)

    try:
        participants = run_async_with_cleanup(_get_participants())
        if participants is None:
            return jsonify([]), 200  # Return empty list instead of 404
        return jsonify(participants)
    except Exception as e:
        logger.error(f"Failed to get participants: {e}")
        return jsonify([]), 200  # Return empty list on error

@sessions_bp.route('/api/welcome', methods=['GET'])
def welcome():
    """Returns a welcome message"""
    logger.info(f"Request received: {request.method} {request.path}")
    return jsonify({"message": "Welcome to the Flask API Service!"})

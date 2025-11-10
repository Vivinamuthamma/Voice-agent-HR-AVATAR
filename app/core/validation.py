import re
from typing import Dict, Any, List, Optional
from app.core.errors import ValidationError

class InputValidator:
    """Comprehensive input validation and sanitization utilities."""

    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000, allow_html: bool = False) -> str:
        """Sanitize string input."""
        if not isinstance(value, str):
            raise ValidationError("Value must be a string")

        # Remove null bytes and control characters
        value = value.replace('\x00', '').strip()

        # Basic HTML sanitization if not allowed
        if not allow_html:
            value = re.sub(r'<[^>]+>', '', value)

        # Length validation
        if len(value) > max_length:
            raise ValidationError(f"Value exceeds maximum length of {max_length} characters")

        return value

    @staticmethod
    def validate_email(email: str) -> str:
        """Validate and sanitize email address."""
        email = InputValidator.sanitize_string(email, max_length=254)

        # RFC 5322 compliant email regex (simplified)
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        if not re.match(email_pattern, email):
            raise ValidationError("Invalid email format")

        return email.lower()

    @staticmethod
    def validate_session_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate session creation/update data."""
        if not isinstance(data, dict):
            raise ValidationError("Data must be a dictionary")

        validated = {}

        # Required fields
        required_fields = ['candidate_name', 'position', 'email']
        for field in required_fields:
            if field not in data or not data[field] or not isinstance(data[field], str) or not data[field].strip():
                raise ValidationError(f"Missing or invalid required field: {field}")
            validated[field] = InputValidator.sanitize_string(data[field])

        # Email validation
        validated['email'] = InputValidator.validate_email(data['email'])

        # Optional fields with validation
        if 'questions' in data:
            if not isinstance(data['questions'], list):
                raise ValidationError("Questions must be a list")
            validated['questions'] = data['questions']  # Assume pre-validated

        if 'analysis' in data:
            if not isinstance(data['analysis'], dict):
                raise ValidationError("Analysis must be a dictionary")
            validated['analysis'] = data['analysis']

        if 'jd_full' in data:
            validated['jd_full'] = InputValidator.sanitize_string(data['jd_full'], max_length=50000)

        if 'resume_full' in data:
            validated['resume_full'] = InputValidator.sanitize_string(data['resume_full'], max_length=50000)

        return validated

    @staticmethod
    def validate_session_id(session_id: str) -> str:
        """Validate session ID format."""
        if not isinstance(session_id, str):
            raise ValidationError("Session ID must be a string")

        # UUID format validation
        uuid_pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
        if not re.match(uuid_pattern, session_id):
            raise ValidationError("Invalid session ID format")

        return session_id

    @staticmethod
    def validate_room_name(room_name: str) -> str:
        """Validate LiveKit room name."""
        room_name = InputValidator.sanitize_string(room_name, max_length=100)

        # Allow alphanumeric, hyphens, and underscores
        if not re.match(r'^[a-zA-Z0-9_-]+$', room_name):
            raise ValidationError("Room name contains invalid characters")

        return room_name

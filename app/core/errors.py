from typing import Optional, Dict, Any

class InterviewAppError(Exception):
    """Base exception for interview application errors."""

    def __init__(self, message: str, status_code: int = 500, payload: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload

class ValidationError(InterviewAppError):
    """Raised when input validation fails."""
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message, status_code=400, payload={'field': field} if field else None)

class FileProcessingError(InterviewAppError):
    """Raised when file processing fails."""
    def __init__(self, message: str, filename: Optional[str] = None):
        super().__init__(message, status_code=400, payload={'filename': filename} if filename else None)

class LiveKitError(InterviewAppError):
    """Raised when LiveKit operations fail."""
    def __init__(self, message: str, operation: Optional[str] = None):
        super().__init__(message, status_code=500, payload={'operation': operation} if operation else None)

class SessionError(InterviewAppError):
    """Raised when session operations fail."""
    def __init__(self, message: str, session_id: Optional[str] = None):
        super().__init__(message, status_code=404, payload={'session_id': session_id} if session_id else None)

class EmailError(InterviewAppError):
    """Raised when email operations fail."""
    def __init__(self, message: str):
        super().__init__(message, status_code=500)

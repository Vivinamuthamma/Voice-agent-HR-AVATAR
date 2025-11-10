from flask import jsonify
from typing import Any, Dict, Optional
from app.core.errors import InterviewAppError

class APIResponse:
    """Standardized API response utilities."""

    @staticmethod
    def success(data: Any = None, message: str = "", status_code: int = 200) -> tuple:
        """Create a standardized success response."""
        response = {
            "success": True,
            "message": message,
            "status_code": status_code
        }

        if data is not None:
            response["data"] = data

        return jsonify(response), status_code

    @staticmethod
    def error(
        message: str,
        error_type: str = "internal_error",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ) -> tuple:
        """Create a standardized error response."""
        response = {
            "success": False,
            "error": message,
            "type": error_type,
            "status_code": status_code
        }

        if details:
            response["details"] = details

        return jsonify(response), status_code

    @staticmethod
    def handle_exception(e: Exception) -> tuple:
        """Handle exceptions and return appropriate API responses."""
        if isinstance(e, InterviewAppError):
            return APIResponse.error(
                message=e.message,
                error_type=e.__class__.__name__.lower(),
                status_code=e.status_code,
                details=e.payload
            )
        else:
            # Generic error handling
            return APIResponse.error(
                message="An unexpected error occurred",
                error_type="internal_error",
                status_code=500,
                details={"original_error": str(e)} if __debug__ else None
            )

    @staticmethod
    def validation_error(message: str, field: Optional[str] = None) -> tuple:
        """Create a validation error response."""
        details = {"field": field} if field else None
        return APIResponse.error(
            message=message,
            error_type="validation_error",
            status_code=400,
            details=details
        )

    @staticmethod
    def not_found(resource: str, resource_id: Optional[str] = None) -> tuple:
        """Create a not found error response."""
        message = f"{resource} not found"
        if resource_id:
            message += f": {resource_id}"

        details = {"resource": resource, "resource_id": resource_id} if resource_id else None
        return APIResponse.error(
            message=message,
            error_type="not_found",
            status_code=404,
            details=details
        )

    @staticmethod
    def unauthorized(message: str = "Authentication required") -> tuple:
        """Create an unauthorized error response."""
        return APIResponse.error(
            message=message,
            error_type="authentication_error",
            status_code=401
        )

    @staticmethod
    def forbidden(message: str = "Access denied") -> tuple:
        """Create a forbidden error response."""
        return APIResponse.error(
            message=message,
            error_type="authorization_error",
            status_code=403
        )

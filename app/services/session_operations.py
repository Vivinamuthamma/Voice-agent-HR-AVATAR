import logging
from typing import Dict, List, Optional, Any
from app.services.session_service import InterviewSessionService
from app.services.room_service import RoomService
from async_manager import run_async_with_cleanup

logger = logging.getLogger(__name__)

class SessionOperations:
    """Unified operations for interview sessions combining session and room management."""

    def __init__(self, session_service: InterviewSessionService, room_service: RoomService):
        self.session_service = session_service
        self.room_service = room_service

    async def create_complete_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a complete interview session with room and tokens.

        Args:
            session_data: Base session data (candidate_name, position, email, etc.)

        Returns:
            Dict with session info, room details, and tokens
        """
        try:
            # Prepare base session data
            base_data = {
                "candidate_name": session_data['candidate_name'],
                "position": session_data['position'],
                "email": session_data['email'],
                "questions": session_data.get('questions', []),
                "analysis": session_data.get('analysis', {}),
                "jd_full": session_data.get('jd_full', ''),
                "resume_full": session_data.get('resume_full', ''),
                "responses": [],
                "evaluations": [],
                "transcript": []
            }

            # Create session
            session_id = await self.session_service.create_session(base_data)

            # Create room and get tokens
            room_result = await self.room_service.create_interview_room(session_id, session_data['candidate_name'])

            if not room_result.get("success"):
                logger.error(f"Failed to create room for session {session_id}: {room_result.get('error')}")
                # Clean up session if room creation failed
                await self.session_service.delete_session(session_id)
                return {
                    "success": False,
                    "error": f"Room creation failed: {room_result.get('error')}"
                }

            # Update session with room details
            updates = {
                "room_name": room_result["room_name"],
                "room_sid": room_result.get("room_sid"),
                "candidate_token": room_result["candidate_token"],
                "agent_token": room_result["agent_token"],
                "status": "ready"
            }

            success = await self.session_service.update_session(session_id, updates)
            if not success:
                logger.error(f"Failed to update session {session_id} with room details")
                # Clean up room and session
                await self.room_service.delete_room(room_result["room_name"])
                await self.session_service.delete_session(session_id)
                return {
                    "success": False,
                    "error": "Session update failed"
                }

            logger.info(f"Successfully created complete session: {session_id}")

            return {
                "success": True,
                "session_id": session_id,
                "room_name": room_result["room_name"],
                "candidate_token": room_result["candidate_token"],
                "agent_token": room_result["agent_token"]
            }

        except Exception as e:
            logger.error(f"Error creating complete session: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_session_with_room_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session data including current room participant information.

        Args:
            session_id: Session identifier

        Returns:
            Session data with room info or None if not found
        """
        try:
            session_data = await self.session_service.get_session(session_id)
            if not session_data:
                return None

            # Add room participant info if room exists
            room_name = session_data.get('room_name')
            if room_name:
                participants = await self.room_service.get_room_participants(room_name)
                session_data['current_participants'] = participants or []

            return session_data

        except Exception as e:
            logger.error(f"Error getting session with room info for {session_id}: {e}")
            return None

    async def cleanup_session(self, session_id: str) -> Dict[str, Any]:
        """
        Clean up a session by deleting room and session data.

        Args:
            session_id: Session identifier

        Returns:
            Dict with cleanup result
        """
        try:
            # Get session data first
            session_data = await self.session_service.get_session(session_id)
            if not session_data:
                return {
                    "success": False,
                    "error": "Session not found"
                }

            room_name = session_data.get('room_name')
            cleanup_results = {
                "session_deleted": False,
                "room_deleted": False
            }

            # Delete room if it exists
            if room_name:
                room_result = await self.room_service.delete_room(room_name)
                cleanup_results["room_deleted"] = room_result.get("success", False)

            # Delete session
            session_deleted = await self.session_service.delete_session(session_id)
            cleanup_results["session_deleted"] = session_deleted

            success = cleanup_results["session_deleted"]
            logger.info(f"Session cleanup completed for {session_id}: {cleanup_results}")

            return {
                "success": success,
                "session_id": session_id,
                "cleanup_results": cleanup_results
            }

        except Exception as e:
            logger.error(f"Error during session cleanup for {session_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def list_sessions_with_status(self) -> List[Dict[str, Any]]:
        """
        List all sessions with enhanced status information.

        Returns:
            List of sessions with status details
        """
        try:
            sessions = await self.session_service.list_sessions()

            # Enhance with room status where possible
            for session in sessions:
                room_name = session.get('room_name')
                if room_name:
                    participants = await self.room_service.get_room_participants(room_name)
                    session['active_participants'] = len(participants) if participants else 0
                    session['is_room_active'] = len(participants) > 0 if participants else False
                else:
                    session['active_participants'] = 0
                    session['is_room_active'] = False

            return sessions

        except Exception as e:
            logger.error(f"Error listing sessions with status: {e}")
            return []

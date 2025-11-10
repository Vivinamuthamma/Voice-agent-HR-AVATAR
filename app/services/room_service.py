import logging
from typing import Dict, Optional, Tuple
from app.services.livekit_service import LiveKitService
from async_manager import run_async_with_cleanup

logger = logging.getLogger(__name__)

class RoomService:
    """Unified service for managing LiveKit rooms and tokens."""

    def __init__(self, livekit_service: LiveKitService):
        self.livekit_service = livekit_service

    async def create_interview_room(self, session_id: str, candidate_name: str) -> Dict:
        """
        Create a complete interview room setup with tokens.

        Args:
            session_id: Unique session identifier
            candidate_name: Name of the candidate

        Returns:
            Dict containing room info and tokens
        """
        try:
            # Generate room name from session ID
            room_name = f"interview_{session_id[:8]}"

            # Create the room
            room_result = await self.livekit_service.create_room(room_name)
            if not room_result or not room_result.get("success"):
                error_msg = room_result.get('error', 'Unknown error') if room_result else 'No response'
                logger.error(f"Failed to create room {room_name}: {error_msg}")
                return {
                    "success": False,
                    "error": f"Room creation failed: {error_msg}"
                }

            # Generate tokens
            candidate_token = self.livekit_service.generate_token(room_name, candidate_name)
            agent_token = self.livekit_service.generate_token(room_name, 'interview_agent', is_agent=True)

            if not candidate_token or not agent_token:
                logger.error(f"Failed to generate tokens for room {room_name}")
                return {
                    "success": False,
                    "error": "Token generation failed"
                }

            logger.info(f"Successfully created interview room: {room_name}")

            return {
                "success": True,
                "room_name": room_name,
                "room_sid": room_result.get("room_sid"),
                "candidate_token": candidate_token,
                "agent_token": agent_token,
                "already_existed": room_result.get("already_existed", False)
            }

        except Exception as e:
            logger.error(f"Error creating interview room for session {session_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def delete_room(self, room_name: str) -> Dict:
        """
        Delete a LiveKit room.

        Args:
            room_name: Name of the room to delete

        Returns:
            Dict with deletion result
        """
        try:
            result = await self.livekit_service.delete_room(room_name)
            if result and result.get("success"):
                logger.info(f"Successfully deleted room: {room_name}")
            else:
                logger.warning(f"Room deletion failed or room not found: {room_name}")
            return result
        except Exception as e:
            logger.error(f"Error deleting room {room_name}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_room_participants(self, room_name: str) -> Optional[list]:
        """
        Get participants in a room.

        Args:
            room_name: Name of the room

        Returns:
            List of participants or None if error
        """
        try:
            return await self.livekit_service.list_participants(room_name)
        except Exception as e:
            logger.error(f"Error getting participants for room {room_name}: {e}")
            return None

    def generate_tokens_for_room(self, room_name: str, candidate_name: str) -> Tuple[str, str]:
        """
        Generate both candidate and agent tokens for a room.

        Args:
            room_name: Name of the room
            candidate_name: Name of the candidate

        Returns:
            Tuple of (candidate_token, agent_token)
        """
        candidate_token = self.livekit_service.generate_token(room_name, candidate_name)
        agent_token = self.livekit_service.generate_token(room_name, 'interview_agent', is_agent=True)
        return candidate_token, agent_token

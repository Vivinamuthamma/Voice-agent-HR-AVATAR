import logging
from typing import Dict, Optional
from async_manager import AsyncLiveKitManager

logger = logging.getLogger(__name__)

class LiveKitService:
    def __init__(self, url: str, api_key: str, api_secret: str):
        self.async_manager = AsyncLiveKitManager(url, api_key, api_secret)

    async def create_room(self, room_name: str, empty_timeout: int = 3600, max_participants: int = 10) -> Dict:
        """Create a LiveKit room."""
        return await self.async_manager.create_room_async(room_name, empty_timeout, max_participants)

    async def delete_room(self, room_name: str) -> Dict:
        """Delete a LiveKit room."""
        return await self.async_manager.delete_room_async(room_name)

    async def list_participants(self, room_name: str) -> Optional[list]:
        """List participants in a room."""
        return await self.async_manager.list_participants_async(room_name)

    def generate_token(self, room_name: str, participant_name: str, is_agent: bool = False,
                      metadata: str = "", ttl: int = 3600) -> str:
        """Generate access token for a participant."""
        return self.async_manager.generate_token(room_name, participant_name, is_agent, metadata, ttl)

    async def validate_connection(self) -> bool:
        """Validate LiveKit connection."""
        return await self.async_manager.validate_connection()

    async def get_room_info(self, room_name: str) -> Optional[Dict]:
        """Get detailed room information."""
        return await self.async_manager.get_room_info(room_name)

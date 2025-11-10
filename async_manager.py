import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from livekit import api
import time
from app.core.http_client import get_http_client

logger = logging.getLogger(__name__)

class AsyncLiveKitManager:
    """Enhanced AsyncLiveKitManager with better error handling and reliability."""

    def __init__(self, url: str, api_key: str, api_secret: str, max_retries: int = 5, retry_delay: int = 2):
        self.url = url
        self.api_key = api_key
        self.api_secret = api_secret
        self.max_retries = max_retries
        self.retry_delay = retry_delay  # seconds
    
    @asynccontextmanager
    async def get_livekit_api(self) -> AsyncGenerator[api.LiveKitAPI, None]:
        """Context manager for LiveKit API with automatic cleanup and retry logic."""
        lk_api = None
        try:
            for attempt in range(self.max_retries):
                try:
                    lk_api = api.LiveKitAPI(
                        url=self.url,
                        api_key=self.api_key,
                        api_secret=self.api_secret
                    )

                    # Test the connection with a simple call
                    try:
                        await asyncio.wait_for(lk_api.room.list_rooms(api.ListRoomsRequest()), timeout=15)
                        logger.debug(f"LiveKit API connection test successful (attempt {attempt + 1})")
                        yield lk_api
                        break
                    except asyncio.TimeoutError:
                        logger.warning(f"LiveKit API connection timeout (attempt {attempt + 1})")
                        if lk_api:
                            await lk_api.aclose()
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(self.retry_delay * (2 ** attempt))
                            continue
                        else:
                            raise

                except Exception as e:
                    if lk_api:
                        await lk_api.aclose()

                    if attempt < self.max_retries - 1:
                        logger.warning(f"LiveKit API connection failed (attempt {attempt + 1}): {e}")
                        await asyncio.sleep(self.retry_delay * (2 ** attempt))
                        continue
                    else:
                        logger.error(f"LiveKit API connection failed after {self.max_retries} attempts: {e}")
                        raise
        finally:
            # Ensure cleanup happens in finally block
            if lk_api:
                try:
                    await lk_api.aclose()
                    logger.debug("LiveKit API client closed successfully")
                except Exception as e:
                    logger.warning(f"Error closing LiveKit API: {e}")
    
    async def create_room_async(self, room_name: str, empty_timeout: int = 3600, max_participants: int = 10) -> dict:
        """Create room with proper cleanup and improved error handling."""
        async with self.get_livekit_api() as lk_api:
            try:
                # Check if room already exists
                try:
                    existing_rooms = await lk_api.room.list_rooms(api.ListRoomsRequest())
                    for room in existing_rooms.rooms:
                        if room.name == room_name:
                            logger.info(f"Room {room_name} already exists with SID: {room.sid}")
                            return {
                                "success": True,
                                "room_name": room.name,
                                "room_sid": room.sid,
                                "already_existed": True
                            }
                except Exception as e:
                    logger.warning(f"Could not check existing rooms: {e}")
                    # Continue with room creation anyway

                # Create new room
                room = await asyncio.wait_for(
                    lk_api.room.create_room(
                        api.CreateRoomRequest(
                            name=room_name,
                            empty_timeout=empty_timeout,  # Use parameter
                            max_participants=max_participants,
                            node_id="",  # Let LiveKit choose
                            metadata=""
                        )
                    ),
                    timeout=30  # 30 second timeout
                )
                
                logger.info(f"Created room: {room.name} with SID: {room.sid}")
                return {
                    "success": True,
                    "room_name": room.name,
                    "room_sid": room.sid,
                    "created_at": room.creation_time,
                    "already_existed": False
                }
                
            except asyncio.TimeoutError:
                logger.error(f"Room creation timed out for: {room_name}")
                return {
                    "success": False,
                    "error": "Room creation timed out"
                }
            except Exception as e:
                logger.error(f"Error creating room {room_name}: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
    
    async def delete_room_async(self, room_name: str) -> dict:
        """Delete room with proper error handling and confirmation."""
        async with self.get_livekit_api() as lk_api:
            try:
                # First check if room exists
                try:
                    rooms = await lk_api.room.list_rooms(api.ListRoomsRequest())
                    room_exists = any(room.name == room_name for room in rooms.rooms)
                    if not room_exists:
                        logger.info(f"Room {room_name} does not exist, no deletion needed")
                        return {
                            "success": True,
                            "message": "Room does not exist",
                            "room_name": room_name
                        }
                except Exception as e:
                    logger.warning(f"Could not verify room existence: {e}")

                # Delete room
                await asyncio.wait_for(
                    lk_api.room.delete_room(api.DeleteRoomRequest(room=room_name)),
                    timeout=15
                )
                
                logger.info(f"Deleted room: {room_name}")
                return {
                    "success": True,
                    "message": "Room deleted successfully",
                    "room_name": room_name
                }
                
            except asyncio.TimeoutError:
                logger.error(f"Room deletion timed out for: {room_name}")
                return {
                    "success": False,
                    "error": "Room deletion timed out",
                    "room_name": room_name
                }
            except Exception as e:
                logger.error(f"Error deleting room {room_name}: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "room_name": room_name
                }

    async def list_participants_async(self, room_name: str) -> Optional[list]:
        """List participants in a room with enhanced error handling."""
        async with self.get_livekit_api() as lk_api:
            try:
                list_participants_request = api.ListParticipantsRequest(room=room_name)
                
                response = await asyncio.wait_for(
                    lk_api.room.list_participants(list_participants_request),
                    timeout=10
                )
                
                participants = []
                for p in response.participants:
                    participant_data = {
                        "identity": p.identity,
                        "name": p.name,
                        "state": p.state,
                        "joined_at": p.joined_at,
                        "sid": p.sid,
                        "permission": {
                            "can_subscribe": p.permission.can_subscribe,
                            "can_publish": p.permission.can_publish,
                            "can_publish_data": p.permission.can_publish_data,
                        } if p.permission else None,
                        "region": getattr(p, 'region', ''),
                        "is_publisher": getattr(p, 'is_publisher', False)
                    }
                    participants.append(participant_data)
                
                logger.info(f"Found {len(participants)} participants in room {room_name}")
                return participants
                
            except asyncio.TimeoutError:
                logger.error(f"Participant list request timed out for room: {room_name}")
                return None
            except Exception as e:
                error_msg = str(e).lower()
                if "not found" in error_msg or "does not exist" in error_msg:
                    logger.info(f"Room {room_name} not found")
                    return None
                else:
                    logger.error(f"Error listing participants for room {room_name}: {e}")
                    return None

    async def get_room_info(self, room_name: str) -> Optional[dict]:
        """Get detailed room information."""
        async with self.get_livekit_api() as lk_api:
            try:
                rooms = await asyncio.wait_for(
                    lk_api.room.list_rooms(api.ListRoomsRequest()),
                    timeout=10
                )
                
                for room in rooms.rooms:
                    if room.name == room_name:
                        return {
                            "name": room.name,
                            "sid": room.sid,
                            "empty_timeout": room.empty_timeout,
                            "max_participants": room.max_participants,
                            "creation_time": room.creation_time,
                            "turn_password": room.turn_password,
                            "enabled_codecs": [codec.mime for codec in room.enabled_codecs],
                            "metadata": room.metadata,
                            "num_participants": room.num_participants,
                            "num_publishers": room.num_publishers,
                            "active_recording": room.active_recording
                        }
                
                logger.info(f"Room {room_name} not found")
                return None
                
            except Exception as e:
                logger.error(f"Error getting room info for {room_name}: {e}")
                return None
    
    def generate_token(self, room_name: str, participant_name: str, is_agent: bool = False, 
                      metadata: str = "", ttl: int = 3600) -> str:
        """Generate access token with enhanced configuration and error handling."""
        try:
            if not all([self.api_key, self.api_secret, room_name, participant_name]):
                logger.error("Missing required parameters for token generation")
                return ""

            # Create token with identity and name
            token = api.AccessToken(self.api_key, self.api_secret)
            token = token.with_identity(participant_name).with_name(participant_name)
            
            # Set metadata if provided
            if metadata:
                token = token.with_metadata(metadata)
            
            # Set TTL (time to live) using timedelta
            import datetime
            token = token.with_ttl(datetime.timedelta(seconds=ttl))
            
            # Configure grants based on participant type
            if is_agent:
                grants = api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True,
                    can_update_own_metadata=True,
                    agent=True,
                    # Agent-specific permissions
                    room_admin=False,  # Set to True if agent needs admin capabilities
                    room_create=False,
                    room_list=False,
                    room_record=False,
                )
            else:
                # Regular participant (candidate)
                grants = api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True,
                    can_update_own_metadata=True,
                    agent=False,
                    # Restricted permissions for security
                    room_admin=False,
                    room_create=False,
                    room_list=False,
                    room_record=False,
                )
            
            token = token.with_grants(grants)
            jwt_token = token.to_jwt()
            
            participant_type = "agent" if is_agent else "participant"
            logger.info(f"Generated {participant_type} token for {participant_name} in room {room_name} (TTL: {ttl}s)")
            return jwt_token
            
        except Exception as e:
            logger.error(f"Token generation failed for {participant_name}: {e}", exc_info=True)
            return ""

    async def validate_connection(self) -> bool:
        """Validate the LiveKit connection and credentials."""
        try:
            async with self.get_livekit_api() as lk_api:
                # Simple test - list rooms
                rooms = await asyncio.wait_for(
                    lk_api.room.list_rooms(api.ListRoomsRequest()),
                    timeout=10
                )
                logger.info(f"Connection validation successful - found {len(rooms.rooms)} rooms")
                return True

        except Exception as e:
            logger.error(f"Connection validation failed: {e}")
            return False

    async def health_check(self) -> dict:
        """Perform comprehensive health check of LiveKit services."""
        health_status = {
            "livekit_connection": False,
            "room_operations": False,
            "token_generation": False,
            "http_client_available": False,
            "overall_status": "unhealthy",
            "details": {}
        }

        try:
            # Test HTTP client availability
            try:
                http_client = get_http_client()
                health_status["http_client_available"] = True
                health_status["details"]["http_client_status"] = "available"
            except Exception as e:
                logger.warning(f"HTTP client not available: {e}")
                health_status["details"]["http_client_error"] = str(e)

            # Test connection
            health_status["livekit_connection"] = await self.validate_connection()

            if health_status["livekit_connection"]:
                # Test room operations
                try:
                    async with self.get_livekit_api() as lk_api:
                        # Try to list rooms
                        rooms = await asyncio.wait_for(
                            lk_api.room.list_rooms(api.ListRoomsRequest()),
                            timeout=5
                        )
                        health_status["room_operations"] = True
                        health_status["details"]["rooms_count"] = len(rooms.rooms)
                except Exception as e:
                    logger.warning(f"Room operations health check failed: {e}")
                    health_status["details"]["room_error"] = str(e)

                # Test token generation
                try:
                    test_token = self.generate_token("test-room", "test-user")
                    health_status["token_generation"] = bool(test_token)
                except Exception as e:
                    logger.warning(f"Token generation health check failed: {e}")
                    health_status["details"]["token_error"] = str(e)

            # Determine overall status
            if health_status["livekit_connection"] and health_status["room_operations"] and health_status["http_client_available"]:
                health_status["overall_status"] = "healthy"
            elif health_status["livekit_connection"] or health_status["http_client_available"]:
                health_status["overall_status"] = "degraded"

            logger.info(f"LiveKit health check completed: {health_status['overall_status']}")
            return health_status

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health_status["details"]["error"] = str(e)
            return health_status

async def run_async_with_cleanup(coro, timeout: Optional[float] = None):
    """Run async coroutine with proper cleanup and timeout handling."""
    try:
        if timeout:
            return await asyncio.wait_for(coro, timeout=timeout)
        else:
            return await coro
    except asyncio.TimeoutError:
        logger.error(f"Async operation timed out after {timeout} seconds")
        raise
    except Exception as e:
        logger.error(f"Async execution failed: {e}")
        raise

def run_async_in_new_loop(coro, timeout: Optional[float] = None):
    """Run async coroutine in a new event loop to avoid conflicts."""
    try:
        # Create a new event loop for this operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if timeout:
                return loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
            else:
                return loop.run_until_complete(coro)
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Async execution in new loop failed: {e}")
        raise



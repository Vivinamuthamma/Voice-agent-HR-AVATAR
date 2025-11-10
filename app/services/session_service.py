import json
import os
import logging
import aiofiles
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from asyncio import Lock

class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle non-serializable objects by converting them to strings"""
    def default(self, obj):
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)

logger = logging.getLogger(__name__)

class InterviewSessionService:
    def __init__(self, sessions_dir: str = "interview_sessions"):
        self.sessions_dir = sessions_dir
        self.sessions_lock = asyncio.Lock()
        self._ensure_sessions_dir()

    def _ensure_sessions_dir(self):
        """Ensure the sessions directory exists."""
        if not os.path.exists(self.sessions_dir):
            os.makedirs(self.sessions_dir)

    async def create_session(self, session_data: Dict[str, Any]) -> str:
        """Create a new interview session."""
        import uuid
        session_id = str(uuid.uuid4())

        session_data.update({
            'session_id': session_id,
            'created_at': datetime.now().isoformat(),
            'status': 'created'
        })

        async with self.sessions_lock:
            session_file = os.path.join(self.sessions_dir, f"{session_id}.json")
            async with aiofiles.open(session_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(session_data, indent=2, cls=CustomJSONEncoder))

        logger.info(f"Created session {session_id}")
        return session_id

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data by ID."""
        session_file = os.path.join(self.sessions_dir, f"{session_id}.json")
        if not os.path.exists(session_file):
            return None

        try:
            async with aiofiles.open(session_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            logger.error(f"Error reading session {session_id}: {e}")
            return None

    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update session data."""
        session_data = await self.get_session(session_id)
        if not session_data:
            return False

        session_data.update(updates)
        session_data['updated_at'] = datetime.now().isoformat()

        async with self.sessions_lock:
            session_file = os.path.join(self.sessions_dir, f"{session_id}.json")
            try:
                async with aiofiles.open(session_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(session_data, indent=2, cls=CustomJSONEncoder))
                return True
            except Exception as e:
                logger.error(f"Error updating session {session_id}: {e}")
                return False

    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions."""
        sessions = []
        if not os.path.exists(self.sessions_dir):
            return sessions

        async with self.sessions_lock:
            # Use async directory listing
            import aiofiles.os
            try:
                filenames = await aiofiles.os.listdir(self.sessions_dir)
                for filename in filenames:
                    if filename.endswith('.json'):
                        session_id = filename[:-5]  # Remove .json extension
                        session_data = await self.get_session(session_id)
                        if session_data:
                            sessions.append(session_data)
            except Exception as e:
                logger.error(f"Error listing sessions: {e}")

        return sessions

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        session_file = os.path.join(self.sessions_dir, f"{session_id}.json")
        if not os.path.exists(session_file):
            return False

        try:
            # Use aiofiles for async file operations
            import aiofiles.os
            await aiofiles.os.remove(session_file)
            logger.info(f"Deleted session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            return False

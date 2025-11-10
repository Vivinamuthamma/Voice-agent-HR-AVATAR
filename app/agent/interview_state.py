import logging
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class InterviewState:
    """Enhanced interview state management without FSM."""

    def __init__(self):
        self.candidate_name: Optional[str] = None
        self.position: Optional[str] = None
        self.questions: List[Dict] = []
        self.current_question_index: int = 0
        self.responses: List[Dict] = []
        self.evaluations: List[Dict] = []
        self.session_id: Optional[str] = None
        self.backend_url: str = ""
        self.room_name: Optional[str] = None
        self.max_retries: int = 3
        self.last_spoken_text: Optional[str] = None
        self.current_answer_text: str = ""  # Accumulate real-time transcription
        self.last_speech_time: Optional[float] = None  # Track when speech was last received
        self.speech_pause_threshold: float = 2.0  # Seconds of silence to consider answer complete
        self.no_response_count: int = 0  # Track consecutive no-response attempts

    def get_current_question(self) -> Optional[Dict]:
        if 0 <= self.current_question_index < len(self.questions):
            return self.questions[self.current_question_index]
        return None

    def get_question_text(self, question: Dict) -> str:
        """Extract question text from question dict, handling nested structure."""
        if not question:
            return ""
        
        q_data = question.get('question', '')
        if isinstance(q_data, dict):
            # Handle nested structure: {"id": 1, "question": "text"}
            return q_data.get('question', '')
        elif isinstance(q_data, str):
            # Handle direct string structure: "text"
            return q_data
        else:
            return str(q_data)

    def move_to_next_question(self) -> bool:
        self.current_question_index += 1
        # Clear answer text when moving to next question
        self.current_answer_text = ""
        self.last_speech_time = None
        return self.current_question_index < len(self.questions)

    async def update_backend(self, data: Dict):
        """Update session data on the backend."""
        import aiohttp
        if not self.session_id:
            return
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=5),
                connector=aiohttp.TCPConnector(limit=10, ttl_dns_cache=30)
            ) as session:
                async with session.put(
                    f"{self.backend_url}/api/session/{self.session_id}",
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status != 200:
                        # Log warning but do not raise
                        logger.warning(f"Backend update returned status {response.status}")
        except Exception as e:
            logger.error(f"Error updating backend: {e}")

    async def update_backend_with_retry(self, data: Dict, max_retries: int = 3):
        """Update backend with retry logic for reliability."""
        import asyncio
        for attempt in range(max_retries):
            try:
                await self.update_backend(data)
                logger.info(f"Backend update successful on attempt {attempt + 1}")
                return True
            except Exception as e:
                logger.error(f"Backend update failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)  # Wait 1 second before retry
        logger.error(f"Backend update failed after {max_retries} attempts")
        return False

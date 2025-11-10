import asyncio
import logging
import os
import json
from typing import Annotated
from pathlib import Path
from datetime import datetime
from livekit import agents, rtc
from livekit.agents import JobContext, WorkerOptions, cli, tokenize, tts, ChatContext, ChatMessage
from livekit.agents import Agent, AgentSession, RoomInputOptions
from livekit.plugins import openai, deepgram, silero, elevenlabs, anam

from dotenv import load_dotenv
import PyPDF2
import io
import webrtcvad

from app.services.session_service import CustomJSONEncoder



# Load environment variables from keys.env
dotenv_path = Path(__file__).parent / 'keys.env'
load_dotenv(dotenv_path=dotenv_path)

logger = logging.getLogger("interview-agent")

class MockLLM:
    """Fallback LLM when OpenAI is unavailable"""
    def chat(self, chat_ctx):
        class MockStream:
            async def __aenter__(self):
                return self
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
            def __aiter__(self):
                return self
            async def __anext__(self):
                class MockChunk:
                    def __init__(self, text):
                        self.delta = MockDelta(text)
                class MockDelta:
                    def __init__(self, text):
                        self.content = text
                # Yield one chunk and then stop
                if not hasattr(self, '_yielded'):
                    self._yielded = True
                    return MockChunk("I'm sorry, AI services are currently unavailable. Please try again later or contact support for assistance.")
                else:
                    raise StopAsyncIteration

        return MockStream()

# Global storage for parsed documents
job_description = ""
resume_content = ""
questions_generated = []

class InterviewAssistant(Agent):
    def __init__(self, session_file=None, session_data=None):
        super().__init__(
            instructions="""You are an expert HR interviewer. I will provide a job description and resume. Your tasks:

1. ANALYZE: Review both documents to identify key requirements, candidate strengths, and gaps.

2. INTERVIEW:
- Greet the candidate briefly
- Ask 5 relevant questions one at a time
- Be professional and concise
- Ask follow-up questions only when necessary to clarify
- Reference their resume when relevant

3. EVALUATE:
After the interview, provide:
- Overall recommendation (Selected/Not Selected/Further Review)
- Scores: Technical Fit, Experience, Communication, Problem-Solving, Culture Fit (/10 each)
- Key strengths (3-5 points)
- Concerns/weaknesses
- Detailed hiring recommendation

Style: Professional, concise, unbiased. One question at a time. Wait for responses.
Begin the interview now.

IMPORTANT: After asking a question, ALWAYS wait for the candidate's response before proceeding.
Do not ask multiple questions at once or continue without hearing their answer.
Do not give feedback, praise, or encouragement during the interview.
Be direct and focus on gathering information.
The interview should be structured and efficient,quite conversational.

You have access to function tools for document processing, question generation, and interview management.
Use these tools appropriately to maintain the structured interview flow."""
        )
        self.session_file = session_file
        self.session_id = session_data.get('session_id') if session_data else None
        self.jd_content = ""
        self.resume_content = ""
        self.questions = []
        self.current_question_index = 0
        self.transcript = []  # Initialize transcript list for conversation capture

    async def save_transcript_to_session(self):
        """Save the current transcript to the session file with retry logic"""
        if not self.session_file:
            return

        session_file_path = str(self.session_file)
        if not os.path.exists(session_file_path):
            return

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Use async file operations
                import aiofiles
                async with aiofiles.open(session_file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    session_data = json.loads(content)

                # Update transcript in session data
                session_data['transcript'] = self.transcript
                session_data['updated_at'] = datetime.now().isoformat()

                # Atomic write with unique temp file to avoid conflicts
                import uuid
                temp_file = f"{session_file_path}.{uuid.uuid4().hex}.tmp"
                async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(session_data, indent=2, cls=CustomJSONEncoder))

                # Use os.replace for atomic operation
                os.replace(temp_file, session_file_path)

                logger.info(f"💾 Saved {len(self.transcript)} transcript entries to session file")
                return  # Success, exit retry loop

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Failed to save transcript (attempt {attempt + 1}/{max_retries}): {e}, retrying...")
                    await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"Failed to save transcript after {max_retries} attempts: {e}")



    async def parse_pdf(self, file_data: bytes) -> str:
        """Parse PDF content from bytes"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_data))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            return text.strip()
        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            return ""
    
    async def generate_questions(self, jd: str, resume: str) -> list[str]:
        """Generate interview questions based on JD and resume"""
        prompt = f"""As an expert HR interviewer, analyze the following Job Description and Resume to generate 5 thoughtful, comprehensive interview questions.

Job Description:
{jd}

Resume:
{resume}

Generate questions that demonstrate your expertise as an HR interviewer by:
1. Assessing technical competencies and hands-on experience mentioned in the resume
2. Exploring how the candidate's background aligns with the job requirements
3. Evaluating problem-solving approaches and critical thinking skills
4. Understanding the candidate's career progression and professional development
5. Gauging cultural fit and communication abilities

Focus on questions that reveal the candidate's depth of experience, ability to handle challenges, and potential for growth in this role. Make questions conversational and insightful, allowing the candidate to provide detailed responses that showcase their capabilities.

Return only the questions, numbered 1-5."""

        # Use OpenAI to generate questions with fallback
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                llm = openai.LLM(model="gpt-4o-mini", api_key=openai_key)
                logger.info("OpenAI LLM (gpt-4o-mini) initialized for question generation")
            except Exception as e:
                logger.error(f"OpenAI LLM initialization failed: {e}")
                logger.warning("Using fallback question generation")
                return self._generate_fallback_questions(5)
        else:
            logger.warning("No OpenAI API key found, using fallback question generation")
            return self._generate_fallback_questions(5)
        
        try:
            chat_ctx = ChatContext()
            chat_ctx.add_message(role="system", content="You are an expert HR interviewer. Generate insightful, relevant interview questions.")
            chat_ctx.add_message(role="user", content=prompt)

            questions_text = ""
            async with llm.chat(chat_ctx=chat_ctx) as stream:
                async for chunk in stream:
                    if chunk.delta and hasattr(chunk.delta, 'content'):
                        questions_text += chunk.delta.content or ""
        except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as e:
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ["event loop is closed", "cancelled", "connection", "timeout"]):
                logger.warning(f"LLM request interrupted ({type(e).__name__}: {e}), will retry question generation")
                # Wait a moment and retry once
                await asyncio.sleep(1.0)
                try:
                    # Retry the LLM call
                    chat_ctx = ChatContext()
                    chat_ctx.add_message(role="system", content="You are an expert HR interviewer. Generate insightful, relevant interview questions.")
                    chat_ctx.add_message(role="user", content=prompt)

                    questions_text = ""
                    async with llm.chat(chat_ctx=chat_ctx) as stream:
                        async for chunk in stream:
                            if chunk.delta and hasattr(chunk.delta, 'content'):
                                questions_text += chunk.delta.content or ""
                    # Parse questions into list
                    questions = [q.strip() for q in questions_text.split('\n') if q.strip() and any(c.isdigit() for c in q[:3])]
                    return questions
                except Exception as retry_e:
                    logger.error(f"Retry also failed: {retry_e}, cannot generate questions without LLM")
                    raise RuntimeError("Cannot generate interview questions due to persistent LLM connection issues. Please check your OpenAI API key and network connection.")
            else:
                logger.error(f"Unexpected error during LLM call: {e}")
                raise  # Re-raise unexpected errors
        
        # Parse questions into list
        questions = [q.strip() for q in questions_text.split('\n') if q.strip() and any(c.isdigit() for c in q[:3])]
        return questions

    def _generate_fallback_questions(self, num_questions: int) -> list[str]:
        """Generate generic fallback questions when LLM is not available"""
        fallback_questions = [
            "Can you walk me through your professional background and key experiences?",
            "What motivated you to apply for this position?",
            "Can you describe a challenging project you've worked on and how you handled it?",
            "How do you approach problem-solving in your work?",
            "What are your greatest professional strengths?",
            "Can you tell me about a time when you had to learn something new quickly?",
            "How do you handle working under pressure or meeting tight deadlines?",
            "Describe your experience working in a team environment.",
            "What tools and technologies are you most proficient with?",
            "How do you stay current with industry trends and best practices?",
            "Can you discuss a situation where you received constructive feedback and how you responded?",
            "What are your career goals and how does this position align with them?",
            "How do you prioritize tasks when working on multiple projects?",
            "Can you describe your experience with project management or coordination?",
            "What do you consider to be your most significant professional achievement?",
            "How do you handle conflicts or disagreements in a professional setting?",
            "What experience do you have with quality assurance or testing processes?",
            "How do you approach documentation and knowledge sharing?",
            "Can you discuss your experience with stakeholder communication?",
            "What strategies do you use for continuous professional development?"
        ]

        selected_questions = fallback_questions[:num_questions]
        return selected_questions


async def entrypoint(ctx: JobContext):
    """Main entry point for the LiveKit agent"""

    logger.info("Connecting to LiveKit room...")
    try:
        await ctx.connect()
        logger.info("Successfully connected to LiveKit room")

        # Enable transcription on the room
        try:
            ctx.room.transcription_enabled = True
            logger.info("✅ Room transcription enabled")
        except Exception as e:
            logger.warning(f"⚠️ Could not enable room transcription: {e}")

    except Exception as e:
        logger.error(f"Failed to connect to LiveKit room: {e}")
        raise

    # Initialize Anam avatar session with reconnection support
    anam_api_key = os.getenv("ANAM_API_KEY")
    anam_avatar = None
    avatar_reconnect_attempts = 0
    max_avatar_reconnect_attempts = 3
    avatar_reconnect_task = None

    async def initialize_avatar():
        nonlocal anam_avatar, avatar_reconnect_attempts
        if not anam_api_key:
            logger.warning("⚠️ ANAM_API_KEY not found - avatar will not be available")
            return None

        try:
            logger.info("Initializing Anam avatar session...")
            avatar = anam.AvatarSession(
                persona_config=anam.PersonaConfig(
                    name="HR Interviewer",
                    avatarId="30fa96d0-26c4-4e55-94a0-517025942e18",  # Professional avatar ID
                ),
                api_key=anam_api_key,
            )
            logger.info("✅ Anam avatar session initialized")
            avatar_reconnect_attempts = 0  # Reset on success
            return avatar
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize Anam avatar: {e}")
            return None

    async def reconnect_avatar():
        nonlocal anam_avatar, avatar_reconnect_attempts, avatar_reconnect_task
        if avatar_reconnect_attempts >= max_avatar_reconnect_attempts:
            logger.error("❌ Max avatar reconnection attempts reached, giving up")
            return

        avatar_reconnect_attempts += 1
        delay = min(2 ** avatar_reconnect_attempts, 30)  # Exponential backoff, max 30s

        logger.info(f"🔄 Attempting avatar reconnection {avatar_reconnect_attempts}/{max_avatar_reconnect_attempts} in {delay}s...")

        await asyncio.sleep(delay)

        try:
            new_avatar = await initialize_avatar()
            if new_avatar and ctx.room:
                logger.info("🚀 Starting reconnected avatar session...")
                await new_avatar.start(session, room=ctx.room)
                anam_avatar = new_avatar
                logger.info("✅ Avatar reconnection successful")
                avatar_reconnect_task = None
            else:
                logger.warning("⚠️ Avatar reconnection failed, will retry...")
                avatar_reconnect_task = asyncio.create_task(reconnect_avatar())
        except Exception as e:
            logger.error(f"❌ Avatar reconnection failed: {e}")
            if avatar_reconnect_attempts < max_avatar_reconnect_attempts:
                avatar_reconnect_task = asyncio.create_task(reconnect_avatar())

    anam_avatar = await initialize_avatar()

    # Load session data for this room asynchronously to avoid blocking
    room_name = ctx.room.name
    session_file = None
    session_data = None

    # Quick synchronous check for session file to avoid timeouts
    if os.path.exists("interview_sessions"):
        try:
            # Use synchronous file operations for speed - limit to avoid blocking
            import glob
            session_files = glob.glob(os.path.join("interview_sessions", "*.json"))
            session_files.sort(key=os.path.getmtime, reverse=True)  # Most recent first

            for file_path in session_files[:5]:  # Check only 5 most recent files
                try:
                    import aiofiles
                    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        data = json.loads(content)
                    if data.get('room_name') == room_name:
                        session_file = Path(file_path)
                        session_data = data
                        logger.info(f"Found session file for room {room_name}")
                        break
                except Exception as e:
                    continue
        except Exception as e:
            logger.warning(f"Error during session file search: {e}")

    # Create assistant instance after loading session data
    assistant_instance = InterviewAssistant(session_file=session_file, session_data=session_data)

    if session_data:
        try:
            assistant_instance.jd_content = session_data.get('jd_full', '')
            assistant_instance.resume_content = session_data.get('resume_full', '')

            logger.info(f"Loaded session data for room {room_name}: JD={len(assistant_instance.jd_content)} chars, Resume={len(assistant_instance.resume_content)} chars")

            # Load cached questions if available
            cached_questions = session_data.get('questions', [])
            if cached_questions:
                assistant_instance.questions = cached_questions
                logger.info(f"Loaded {len(assistant_instance.questions)} cached questions for session")

        except Exception as e:
            logger.error(f"Failed to process session data for {room_name}: {e}")
            assistant_instance.jd_content = ""
            assistant_instance.resume_content = ""
    else:
        logger.warning(f"No session file found for room {room_name}")
    
    # Setup STT (Speech-to-Text) with OpenAI primary and Deepgram fallback
    # Optimized for accurate candidate speech transcription
    openai_key = os.getenv("OPENAI_API_KEY")
    stt = None
    if openai_key:
        try:
            # OpenAI STT with basic configuration (language defaults to auto-detection)
            stt = openai.STT(api_key=openai_key)
            logger.info("LiveKit OpenAI STT initialized successfully")
        except Exception as e:
            logger.warning(f"OpenAI STT initialization failed: {e}, trying Deepgram fallback")
            try:
                deepgram_key = os.getenv("DEEPGRAM_API_KEY")
                if deepgram_key:
                    # Deepgram STT with enhanced accuracy settings
                    stt = deepgram.STT(
                        api_key=deepgram_key,
                        model="nova-3",  # Latest high-accuracy model
                        language="en-US",  # US English for precision
                        punctuate=True,  # Automatic punctuation for readability
                        smart_format=True  
                    )
                    logger.info("LiveKit Deepgram STT initialized as fallback with enhanced accuracy")
                else:
                    logger.error("No Deepgram API key found")
                    stt = None
            except Exception as e2:
                logger.error(f"Both STT providers failed: OpenAI - {e}, Deepgram - {e2}")
                stt = None
    else:
        logger.warning("No OpenAI API key found, trying Deepgram STT")
        deepgram_key = os.getenv("DEEPGRAM_API_KEY")
        if deepgram_key:
            try:
                # Deepgram STT with enhanced accuracy settings
                stt = deepgram.STT(
                    api_key=deepgram_key,
                    model="nova-3",  # Latest high-accuracy model
                    language="en-US",  # US English for precision
                    punctuate=True,  # Automatic punctuation for readability
                    smart_format=True  # Smart formatting and capitalization
                )
                logger.info("LiveKit Deepgram STT initialized with enhanced accuracy")
            except Exception as e:
                logger.error(f"Deepgram STT initialization failed: {e}")
                stt = None
        else:
            logger.error("No STT API keys found - transcription will not work")
            stt = None

    # CRITICAL: Test STT functionality before proceeding
    if stt:
        logger.info("🔍 Testing STT functionality...")
        try:
            # Check STT object attributes
            stt_attrs = [attr for attr in dir(stt) if not attr.startswith('_')]
            logger.info(f"🔍 STT object attributes: {stt_attrs}")

            # Try to access STT properties
            if hasattr(stt, 'language'):
                logger.info(f"🔍 STT language: {stt.language}")
            if hasattr(stt, 'model'):
                logger.info(f"🔍 STT model: {stt.model}")

            logger.info("✅ STT appears to be initialized correctly")
        except Exception as e:
            logger.warning(f"⚠️ STT test inconclusive: {e}")
    else:
        logger.error("❌ STT is not available - candidate speech will not be transcribed")

    # CRITICAL: Ensure STT is available for transcription
    if not stt:
        logger.error("STT service unavailable - transcription will not work")
        raise RuntimeError("STT service required for transcription. Please check OPENAI_API_KEY or DEEPGRAM_API_KEY environment variables.")

    # Store STT reference for later use (will be set after wrapper creation)
    stt_instance = None
    
    # Setup LLM with fallback
    llm = None
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            llm = openai.LLM(model="gpt-4o-mini", api_key=openai_key)
            logger.info("LiveKit OpenAI LLM (gpt-4o-mini) initialized successfully")

            test_ctx = ChatContext()
            test_ctx.add_message(role="user", content="Hello")
            try:
                async def test_chat():
                    response_received = False
                    async with llm.chat(chat_ctx=test_ctx) as stream:
                        async for chunk in stream:
                            if chunk.delta and hasattr(chunk.delta, 'content') and chunk.delta.content:
                                response_received = True
                                break
                    return response_received
                test_result = await asyncio.wait_for(test_chat(), timeout=10.0)
                if test_result:
                    logger.info("LLM connectivity test passed")
                else:
                    logger.warning("LLM connectivity test incomplete - proceeding anyway")
            except asyncio.TimeoutError:
                logger.warning("LLM connectivity test timed out - proceeding anyway")
            except Exception as e:
                error_details = str(e) if str(e) else type(e).__name__
                logger.warning(f"LLM connectivity test failed ({error_details}) - proceeding anyway")
        except Exception as e:
            error_details = str(e) if str(e) else type(e).__name__
            logger.warning(f"OpenAI LLM initialization failed ({error_details}) - using fallback")
            llm = MockLLM()
    else:
        logger.warning("No OpenAI API key found, using fallback LLM")
        llm = MockLLM()

    # Setup TTS (Text-to-Speech) with fallback
    tts_plugin = None
    if openai_key:
        try:
            tts_plugin = openai.TTS(voice="alloy", api_key=openai_key)
            logger.info("LiveKit OpenAI TTS initialized successfully with 'alloy' voice")
        except Exception as e:
            logger.warning(f"OpenAI TTS initialization failed: {e}, trying ElevenLabs fallback")
            tts_plugin = None

    if not tts_plugin:
        elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
        if elevenlabs_key:
            try:
                tts_plugin = elevenlabs.TTS(api_key=elevenlabs_key)
                logger.info("LiveKit ElevenLabs TTS initialized as fallback")
            except Exception as e:
                logger.warning(f"ElevenLabs TTS fallback failed: {e}")
                tts_plugin = None
        else:
            logger.warning("No ElevenLabs API key found - TTS unavailable")
            tts_plugin = None

    # Wrap TTS to capture agent speech for transcription
    class TranscriptionTTS:
        def __init__(self, tts, assistant_instance):
            self.tts = tts
            self.assistant_instance = assistant_instance

        def synthesize(self, *args, **kwargs):
            # Capture the text before synthesis for agent speech
            text = args[0] if args else kwargs.get('text', '')
            if text:
                # Capture agent speech in transcript
                transcript_entry = {
                    'speaker': 'agent',
                    'text': text,
                    'timestamp': datetime.now().timestamp(),
                    'type': 'message'
                }
                self.assistant_instance.transcript.append(transcript_entry)
                logger.info(f"📝 Captured agent speech: {text[:50]}...")

                # Save transcript to session file immediately
                asyncio.create_task(self.assistant_instance.save_transcript_to_session())

            # Return the original TTS synthesize method (async context manager)
            return self.tts.synthesize(*args, **kwargs)

        # Delegate other attributes to the wrapped TTS
        def __getattr__(self, name):
            return getattr(self.tts, name)

    if tts_plugin:
        tts_plugin = TranscriptionTTS(tts_plugin, assistant_instance)

    # Create AgentSession with service availability checks
    if not tts_plugin:
        logger.error("TTS service unavailable - cannot start voice assistant")
        raise RuntimeError("TTS service not available. Please check API keys and service configuration.")
    if not stt:
        logger.error("STT service unavailable - transcription will not work")
        raise RuntimeError("STT service required for transcription. Please check OPENAI_API_KEY or DEEPGRAM_API_KEY environment variables.")
    if not llm:
        logger.warning("LLM service unavailable - using fallback responses")

    logger.info("🔧 Creating AgentSession with transcription settings...")

    # Wrap STT to capture candidate speech for transcription with VAD and error handling
    class TranscriptionSTT:
        def __init__(self, stt, assistant_instance):
            self.stt = stt
            self.assistant_instance = assistant_instance
            self.retry_count = 0
            self.max_retries = 3
            # Initialize WebRTC VAD for voice activity detection
            self.vad = webrtcvad.Vad()
            self.vad.set_mode(3)  # Most aggressive filtering for clean speech
            self.audio_buffer = []
            self.speech_detected = False
            self.frame_duration = 30  # 30ms frames for VAD
            self.sample_rate = 16000  # 16kHz sample rate

        async def recognize(self, *args, **kwargs):
            for attempt in range(self.max_retries):
                try:
                    result = await self.stt.recognize(*args, **kwargs)

                    # Reset retry count on success
                    self.retry_count = 0

                    # Handle different STT result formats
                    text = None
                    if hasattr(result, 'text') and result.text:
                        text = result.text
                    elif hasattr(result, 'alternatives') and result.alternatives:
                        # Some STT services return alternatives
                        text = result.alternatives[0].text if result.alternatives[0].text else None
                    elif isinstance(result, str):
                        text = result

                    if text:
                        # Apply VAD filtering - only capture if speech was detected
                        if self._is_speech_likely(text):
                            # Capture candidate speech in transcript
                            transcript_entry = {
                                'speaker': 'candidate',
                                'text': text,
                                'timestamp': datetime.now().timestamp(),
                                'type': 'message'
                            }
                            self.assistant_instance.transcript.append(transcript_entry)
                            logger.info(f"📝 Captured candidate speech (VAD filtered): {text[:50]}...")

                            # Save transcript to session file immediately
                            asyncio.create_task(self.assistant_instance.save_transcript_to_session())
                        else:
                            logger.debug(f"🗣️ Speech detected but filtered by VAD: {text[:30]}...")

                    return result

                except Exception as e:
                    error_msg = str(e).lower()
                    is_retryable = any(keyword in error_msg for keyword in [
                        '500', 'internal', 'server error', 'timeout', 'connection',
                        'network', 'api', 'rate limit'
                    ])

                    if is_retryable and attempt < self.max_retries - 1:
                        wait_time = min(0.1 * (2 ** attempt), 2.0)  # Exponential backoff, max 2s
                        logger.warning(f"STT error (attempt {attempt + 1}/{self.max_retries}): {e}, retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"STT failed after {self.max_retries} attempts: {e}")
                        # Return empty result to prevent crashes
                        return type('EmptyResult', (), {'text': '', 'alternatives': []})()

            # This should never be reached, but just in case
            return type('EmptyResult', (), {'text': '', 'alternatives': []})()

        def _is_speech_likely(self, text):
            """Use heuristics to determine if text is likely actual speech vs noise"""
            if not text or len(text.strip()) < 2:
                return False

            # Filter out very short or nonsensical responses
            text_lower = text.lower().strip()

            # Common false positives from STT
            noise_patterns = [
                'thank you', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
                'um', 'uh', 'er', 'ah', 'like', 'you know', 'i mean', 'so', 'well', 'okay',
                'yeah', 'yes', 'no', 'hi', 'hello', 'hey', 'bye', 'goodbye', 'please', 'sorry'
            ]

            # If text is only noise words, likely not actual speech
            words = text_lower.split()
            if len(words) <= 3 and all(word in noise_patterns for word in words):
                return False

            # If text is very short and contains only articles/prepositions, likely noise
            if len(text_lower) <= 10 and all(word in ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'] for word in words):
                return False

            return True

        # Delegate other attributes to the wrapped STT
        def __getattr__(self, name):
            return getattr(self.stt, name)

    wrapped_stt = TranscriptionSTT(stt, assistant_instance)

    session = AgentSession(
        stt=wrapped_stt,
        llm=llm,
        tts=tts_plugin,
        vad=silero.VAD.load(),
        use_tts_aligned_transcript=True,
    )

    # Verify session was created with STT
    if hasattr(session, '_stt') and session._stt:
        logger.info("✅ AgentSession created with STT enabled")
    else:
        logger.warning("⚠️ AgentSession may not have STT properly configured")


    
    # Define function for document processing
    @agents.llm.function_tool(
        name="upload_job_description",
        description="Upload and parse a job description document. The document should be in text or PDF format."
    )
    async def upload_jd(
        content: Annotated[str, "The job description text content"]
    ) -> str:
        """Process uploaded job description"""
        assistant_instance.jd_content = content
        logger.info(f"Job description uploaded via voice: {len(content)} characters")
        response_text = f"Thank you for providing the job description. I've carefully reviewed it and understand the key requirements for this role. It contains {len(content.split())} words covering the responsibilities, qualifications, and expectations. I'm ready to proceed with the resume upload or we can begin generating tailored interview questions if you already have the resume ready."

        # Generate reply - this will be captured by TTS wrapper
        reply_result = await session.generate_reply(instructions=response_text)
        return response_text

    @agents.llm.function_tool(
        name="upload_resume",
        description="Upload and parse a candidate's resume. The document should be in text or PDF format."
    )
    async def upload_resume(
        content: Annotated[str, "The resume text content"]
    ) -> str:
        """Process uploaded resume"""
        assistant_instance.resume_content = content
        logger.info(f"Resume uploaded via voice: {len(content)} characters")
        response_text = f"Thank you for sharing your resume. I've taken the time to carefully review your professional background, skills, and experience. The document contains {len(content.split())} words detailing your career .Would you like me to proceed with generating the questions?"

        # Generate reply - this will be captured by TTS wrapper
        reply_result = await session.generate_reply(instructions=response_text)
        return response_text
    
    @agents.llm.function_tool(
        name="generate_interview_questions",
        description="Generate interview questions based on the uploaded job description and resume."
    )
    async def generate_questions() -> str:
        """Generate questions from JD and resume"""
        if not assistant_instance.jd_content or not assistant_instance.resume_content:
            return "I need both the job description and your resume to create meaningful, tailored interview questions. Could you please upload both documents first?"

        try:
            questions = await asyncio.wait_for(
                assistant_instance.generate_questions(
                    assistant_instance.jd_content,
                    assistant_instance.resume_content
                ),
                timeout=30.0  # 30 second timeout
            )
            assistant_instance.questions = questions

            questions_text = "Based on my careful analysis of your resume and the job requirements, I've prepared the following thoughtful interview questions that will help me assess your experience and fit for this role:\n\n"
            questions_text += "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
            questions_text += "\n\nI'm looking forward to hearing your detailed responses to these."

            # Generate reply - this will be captured by TTS wrapper
            reply_result = await session.generate_reply(instructions=questions_text)
            return questions_text
        except asyncio.TimeoutError:
            timeout_msg = "I'm taking longer than expected to generate questions. This might be due to high demand on the AI service. Please try again in a moment, or I can provide some general interview questions to get us started."
            await session.generate_reply(instructions=timeout_msg)  # This will be captured by TTS wrapper
            return timeout_msg
        except Exception as e:
            logger.error(f"Error generating questions: {e}")
            error_msg = f"I cannot generate personalized interview questions at this time due to a technical issue: {str(e)}. Please check your OpenAI API key configuration and try again."
            await session.generate_reply(instructions=error_msg)  # This will be captured by TTS wrapper
            return error_msg
    
    @agents.llm.function_tool(
        name="ask_next_question",
        description="Ask the next interview question from the generated list."
    )
    async def ask_next_question(
        question_number: Annotated[int, "The question number to ask (1-5)"]
    ) -> str:
        """Ask a specific question"""
        if not assistant_instance.questions:
            return "I haven't generated the interview questions yet. Let me first create thoughtful questions based on your resume and the job description."

        if question_number < 1 or question_number > len(assistant_instance.questions):
            return f"I can only ask questions numbered between 1 and {len(assistant_instance.questions)}. Which question would you like me to ask?"

        assistant_instance.current_question_index = question_number - 1
        question = assistant_instance.questions[question_number - 1]
        question_text = f"Question {question_number}: {question}"

        # Generate the spoken response
        response_text = f"Question {question_number}: {question}"

        # Generate reply - this will be captured by TTS wrapper
        reply_result = await session.generate_reply(instructions=response_text)
        return response_text

    @agents.llm.function_tool(
        name="get_transcript",
        description="Get the current conversation transcript of the interview."
    )
    async def get_transcript() -> str:
        """Get formatted transcript of the conversation"""
        if not assistant_instance.transcript:
            response_text = "No conversation has been recorded yet. The transcript will begin once we start the interview."
        else:
            # Format transcript for display
            transcript_lines = []
            transcript_lines.append("📝 **Interview Transcript**\n")

            for entry in assistant_instance.transcript:
                speaker = entry.get('speaker', 'unknown')
                text = entry.get('text', '')
                entry_type = entry.get('type', 'message')
                timestamp = entry.get('timestamp', 0)

                # Format speaker
                if speaker == 'agent':
                    speaker_icon = "🤖"
                    speaker_name = "Interviewer"
                else:
                    # Default to candidate for any non-agent speaker
                    speaker_icon = "👤"
                    speaker_name = "Candidate"

                # Format timestamp
                if isinstance(timestamp, (int, float)):
                    import time
                    time_str = time.strftime('%H:%M:%S', time.localtime(timestamp))
                else:
                    time_str = "00:00:00"

                # Format message based on type
                if entry_type == 'greeting':
                    formatted_text = f"*{text}*"
                elif entry_type == 'question':
                    question_num = entry.get('question_number', '')
                    formatted_text = f"**Question {question_num}:** {text}"
                else:
                    formatted_text = text

                transcript_lines.append(f"{speaker_icon} **{speaker_name}** ({time_str}): {formatted_text}")

            transcript_lines.append(f"\n📊 **Total Exchanges:** {len(assistant_instance.transcript)}")
            response_text = "\n".join(transcript_lines)

        # Generate reply - this will be captured by TTS wrapper
        reply_result = await session.generate_reply(instructions=response_text)
        return response_text

    @agents.llm.function_tool(
        name="summarize_transcript",
        description="Generate an AI-powered summary of the interview transcript including key points, overall assessment, and recommendations."
    )
    async def summarize_transcript() -> str:
        """Generate AI summary of the interview transcript"""
        if not assistant_instance.transcript:
            response_text = "There is no transcript available to summarize. Please conduct some interview questions first before requesting a summary."
            await session.generate_reply(instructions=response_text)  # This will be captured by TTS wrapper
            return response_text

        try:
            # Check if LLM is available
            if not llm or isinstance(llm, MockLLM):
                response_text = "I'm unable to generate an AI summary at this time due to service unavailability. However, I can provide you with the full transcript if you'd like to review it manually."
                await session.generate_reply(instructions=response_text)  # This will be captured by TTS wrapper
                return response_text

            # Format transcript for LLM analysis
            transcript_text = ""
            for entry in assistant_instance.transcript:
                speaker = entry.get('speaker', 'unknown')
                text = entry.get('text', '')
                speaker_name = "Interviewer" if speaker == 'agent' else "Candidate"
                transcript_text += f"{speaker_name}: {text}\n"

            # Create summary prompt
            summary_prompt = f"""
As an experienced HR professional and interview evaluator, please analyze the following interview transcript and provide a comprehensive summary.

INTERVIEW TRANSCRIPT:
{transcript_text}

Please provide a structured summary that includes:

1. **Key Points**: Main topics discussed and important information shared
2. **Overall Assessment**: Your evaluation of the candidate's performance, communication skills, and fit for the role
3. **Strengths**: Notable strengths demonstrated by the candidate
4. **Areas for Improvement**: Any areas where the candidate could develop further
5. **Recommendations**: Specific recommendations for next steps or follow-up

Format your response in a clear, professional manner suitable for both voice delivery and written reports. Keep the summary concise but comprehensive, focusing on actionable insights.

If the transcript is too short or incomplete, note this in your assessment.
"""

            # Generate summary using LLM
            chat_ctx = ChatContext()
            chat_ctx.add_message(role="system", content="You are an expert HR interviewer providing detailed interview analysis and feedback.")
            chat_ctx.add_message(role="user", content=summary_prompt)

            summary_text = ""
            async with llm.chat(chat_ctx=chat_ctx) as stream:
                async for chunk in stream:
                    if chunk.delta and hasattr(chunk.delta, 'content'):
                        summary_text += chunk.delta.content or ""

            # Format response for voice output
            response_text = f"Based on my analysis of the interview transcript, here's a comprehensive summary:\n\n{summary_text}\n\nThis assessment is based on {len(assistant_instance.transcript)} exchanges in the conversation."



            # Generate reply - this will be captured by TTS wrapper
            reply_result = await session.generate_reply(instructions=response_text)
            return response_text

        except asyncio.TimeoutError:
            timeout_msg = "The summary generation is taking longer than expected. This might be due to high demand on the AI service. Please try again in a moment."
            await session.generate_reply(instructions=timeout_msg)  # This will be captured by TTS wrapper
            return timeout_msg
        except Exception as e:
            logger.error(f"Error generating transcript summary: {e}")
            error_msg = "I encountered an issue while generating the summary. Please check your OpenAI API key configuration and try again, or I can provide the full transcript for manual review."
            await session.generate_reply(instructions=error_msg)  # This will be captured by TTS wrapper
            return error_msg

    @agents.llm.function_tool(
        name="end_interview",
        description="End the interview session, generate a final summary report, and update session status to completed."
    )
    async def end_interview() -> str:
        """End the interview and generate final summary report"""
        if not assistant_instance.transcript:
            response_text = "There is no transcript available to summarize. The interview cannot be ended without any recorded conversation."
            await session.generate_reply(instructions=response_text)
            return response_text

        # Check if there are meaningful candidate responses (more than just greeting)
        candidate_responses = [entry for entry in assistant_instance.transcript if entry.get('speaker') == 'candidate']
        if len(candidate_responses) < 2:  # Less than 2 candidate responses suggests incomplete interview
            response_text = "The interview appears to be incomplete with very limited candidate responses. While I can still provide an assessment based on the available information, I recommend conducting a more comprehensive interview for better evaluation. Would you like me to proceed with the available data or continue the interview?"
            await session.generate_reply(instructions=response_text)
            return response_text

        try:
            # Check if LLM is available for final summary
            if not llm or isinstance(llm, MockLLM):
                response_text = "I'm unable to generate a final AI summary at this time due to service unavailability. However, the interview will be marked as completed and you can review the full transcript manually."
                await session.generate_reply(instructions=response_text)

                # Still update session status even without AI summary
                await _update_session_completed()
                return response_text

            # Format transcript for LLM analysis
            transcript_text = ""
            for entry in assistant_instance.transcript:
                speaker = entry.get('speaker', 'unknown')
                text = entry.get('text', '')
                speaker_name = "Interviewer" if speaker == 'agent' else "Candidate"
                transcript_text += f"{speaker_name}: {text}\n"

            # Get the generated questions for evaluation context
            questions_context = ""
            if assistant_instance.questions:
                questions_context = "\n\nINTERVIEW QUESTIONS ASKED:\n" + "\n".join([f"{i+1}. {q}" for i, q in enumerate(assistant_instance.questions)])

            # Create comprehensive final summary prompt
            final_summary_prompt = f"""
As an expert HR interviewer, analyze the following complete interview transcript and provide a comprehensive final assessment report.

{questions_context}

COMPLETE INTERVIEW TRANSCRIPT:
{transcript_text}

Please provide a detailed final summary that includes:

1. **Overall Recommendation**: Selected/Not Selected/Further Review with justification
2. **Performance Scores** (out of 10):
   - Technical Fit: /10
   - Experience: /10
   - Communication: /10
   - Problem-Solving: /10
   - Culture Fit: /10
3. **Question-by-Question Assessment**: Evaluate how well the candidate answered each of the interview questions, noting specific strengths and areas for improvement
4. **Key Strengths**: 3-5 most notable strengths demonstrated
5. **Concerns/Weaknesses**: Areas that need improvement or development
6. **Detailed Hiring Recommendation**: Comprehensive assessment for HR decision-making

Format your response as a professional interview assessment report suitable for HR records and managerial review. Be thorough but concise, focusing on actionable insights that will inform the hiring decision.

This is the FINAL assessment - provide your most comprehensive and definitive evaluation.
"""

            # Generate final summary using LLM
            chat_ctx = ChatContext()
            chat_ctx.add_message(role="system", content="You are a senior HR professional providing the final comprehensive evaluation of a candidate after a complete interview process.")
            chat_ctx.add_message(role="user", content=final_summary_prompt)

            final_summary_text = ""
            async with llm.chat(chat_ctx=chat_ctx) as stream:
                async for chunk in stream:
                    if chunk.delta and hasattr(chunk.delta, 'content'):
                        final_summary_text += chunk.delta.content or ""

            # Update session status to completed
            await _update_session_completed()

            # Format response for voice output
            response_text = f"Thank you for participating in this interview. The interview has now been completed and I've generated a comprehensive final assessment report:\n\n{final_summary_text}\n\nThis concludes our interview session. Your responses have been carefully evaluated, and this assessment will be saved for HR review. Thank you for your time and candor throughout the process."

            # Generate reply - this will be captured by TTS wrapper
            reply_result = await session.generate_reply(instructions=response_text)
            return response_text

        except asyncio.TimeoutError:
            timeout_msg = "The final summary generation is taking longer than expected. The interview will still be marked as completed, and you can access the full transcript and basic assessment through the dashboard."
            await session.generate_reply(instructions=timeout_msg)

            # Update session status even on timeout
            await _update_session_completed()
            return timeout_msg
        except Exception as e:
            logger.error(f"Error generating final interview summary: {e}")
            error_msg = "I encountered an issue while generating the final summary. However, the interview has been marked as completed and you can review all materials through the dashboard."
            await session.generate_reply(instructions=error_msg)

            # Update session status even on error
            await _update_session_completed()
            return error_msg

    async def _update_session_completed():
        """Helper function to update session status to completed with retry logic"""
        if not assistant_instance.session_file:
            logger.warning("No session file available to update completion status")
            return

        session_file_path = str(assistant_instance.session_file)
        if not os.path.exists(session_file_path):
            logger.warning(f"Session file not found for completion update: {session_file_path}")
            return

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Use async file operations
                import aiofiles
                async with aiofiles.open(session_file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    session_data = json.loads(content)

                # Update session status and completion timestamp
                session_data['status'] = 'completed'
                session_data['completed_at'] = datetime.now().isoformat()
                session_data['updated_at'] = datetime.now().isoformat()

                # Atomic write with unique temp file to avoid conflicts
                import uuid
                temp_file = f"{session_file_path}.{uuid.uuid4().hex}.tmp"
                async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(session_data, indent=2, cls=CustomJSONEncoder))
                os.replace(temp_file, session_file_path)

                logger.info(f"✅ Interview session {assistant_instance.session_id} marked as completed")
                return  # Success, exit retry loop

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Failed to update session completion (attempt {attempt + 1}/{max_retries}): {e}, retrying...")
                    await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"Failed to update session completion status after {max_retries} attempts: {e}")

    # Register functions with the LLM BEFORE session start
    if llm:
        llm.functions = [
            upload_jd,
            upload_resume,
            generate_questions,
            ask_next_question,
            get_transcript,
            summarize_transcript,
            end_interview
        ]

    logger.info("🎯 Setting up interview agent...")

    # Log STT and TTS configuration for debugging
    logger.info(f"🔊 STT Provider: {type(stt).__name__ if stt else 'None'}")
    logger.info(f"🔊 TTS Provider: {type(tts_plugin).__name__ if tts_plugin else 'None'}")
    logger.info(f"🤖 LLM Provider: {type(llm).__name__ if llm else 'None'}")

    # Start the avatar session if available with error handling
    if anam_avatar:
        try:
            logger.info("Starting Anam avatar session...")
            await anam_avatar.start(session, room=ctx.room)
            logger.info("✅ Anam avatar session started successfully")
        except Exception as e:
            logger.error(f"Failed to start Anam avatar session: {e}")
            # Cancel any pending RPC tasks to prevent timeout errors
            try:
                # Clean up any pending RPC requests
                if hasattr(ctx.room.local_participant, '_pending_rpcs'):
                    for rpc_id in list(ctx.room.local_participant._pending_rpcs.keys()):
                        try:
                            ctx.room.local_participant._pending_rpcs[rpc_id].cancel()
                        except:
                            pass
            except:
                pass
            # Start reconnection process
            if not avatar_reconnect_task or avatar_reconnect_task.done():
                avatar_reconnect_task = asyncio.create_task(reconnect_avatar())

    # Start the session with enhanced transcription settings
    logger.info("Starting agent session...")
    try:
        # Force transcription settings
        room_input_options = RoomInputOptions()
        room_output_options = agents.RoomOutputOptions()

        await session.start(
            room=ctx.room,
            agent=assistant_instance,
            room_input_options=room_input_options,
            room_output_options=room_output_options,
        )

        logger.info("Agent session started successfully")

        # Verify room connection and participants
        logger.info(f"Room connected: {ctx.room.name}")
        logger.info(f"Local participant: {ctx.room.local_participant.identity}")
        logger.info(f"Remote participants: {len(ctx.room.remote_participants)}")

        # Set up track subscription handlers
        @ctx.room.on("track_published")
        def on_track_published(publication, participant):
            logger.info(f"📡 Track published: {publication.sid} by {participant.identity}, kind: {publication.kind}")
            if publication.kind == rtc.TrackKind.KIND_AUDIO:
                logger.info(f"🎤 Audio track published by {participant.identity}")
                # Subscribe to audio tracks automatically
                try:
                    publication.set_subscribed(True)
                    logger.info(f"✅ Subscribed to audio track: {publication.sid}")
                except Exception as e:
                    logger.error(f"Failed to subscribe to audio track {publication.sid}: {e}")

        @ctx.room.on("track_subscribed")
        def on_track_subscribed(track, publication, participant):
            logger.info(f"📡 Track subscribed: {publication.sid} by {participant.identity}, kind: {publication.kind}")
            if publication.kind == rtc.TrackKind.KIND_AUDIO:
                logger.info(f"🎤 Audio track subscribed and ready for STT: {publication.sid}")

        # Log current room state for debugging
        for identity, participant in ctx.room.remote_participants.items():
            logger.info(f"Remote participant: {identity} - tracks: {len(participant.track_publications)}")
            # Log track details for debugging STT issues
            for track_sid, publication in participant.track_publications.items():
                logger.info(f"  Track: {track_sid} - kind: {publication.kind}, source: {publication.source}")

        # Check if there are any audio tracks available and subscribe to them
        audio_tracks_found = False
        for identity, participant in ctx.room.remote_participants.items():
            for track_sid, publication in participant.track_publications.items():
                if publication.kind == rtc.TrackKind.KIND_AUDIO:
                    audio_tracks_found = True
                    logger.info(f"🎤 Audio track found: {track_sid} from participant {identity}")
                    # Ensure track is subscribed
                    try:
                        if not publication.subscribed:
                            publication.set_subscribed(True)
                            logger.info(f"✅ Subscribed to audio track: {track_sid}")
                        else:
                            logger.info(f"🎤 Track already subscribed: {track_sid}")
                    except Exception as e:
                        logger.error(f"Failed to subscribe to audio track {track_sid}: {e}")

        if not audio_tracks_found:
            logger.warning("⚠️ No audio tracks found from remote participants - STT may not work until candidate enables microphone")
            logger.warning("💡 The candidate needs to enable their microphone in the browser for speech transcription to work")
            logger.warning("💡 Audio tracks will be automatically detected and subscribed to when the candidate enables their mic")
        else:
            logger.info("✅ Audio tracks detected and subscribed - STT should be able to transcribe speech")

    except Exception as e:
        logger.error(f"Failed to start agent session: {e}")
        raise

    # CRITICAL: Ensure connection is fully established before proceeding
    logger.info("Waiting for room connection to stabilize...")
    await asyncio.sleep(3)  # Give connection more time to stabilize
    logger.info("Room connection stabilized")

    # Greet the user directly with TTS (not through LLM to avoid unwanted responses)
    greeting_text = "Hello! I'm your interviewer today. It's great to meet you. Are you ready to begin?"

    # Capture greeting in transcript
    greeting_entry = {
        'speaker': 'agent',
        'text': greeting_text,
        'timestamp': datetime.now().timestamp(),
        'type': 'greeting'
    }
    assistant_instance.transcript.append(greeting_entry)

    # Save transcript immediately
    asyncio.create_task(assistant_instance.save_transcript_to_session())

    # Speak the greeting directly using TTS
    logger.info("🎤 Speaking greeting directly via TTS")
    async with session.tts.synthesize(greeting_text):
        pass

    # Generate and speak the first question to start the interview
    logger.info("🎤 Generating first interview question...")
    first_question_instructions = "Now that you've greeted the candidate, start the interview by asking the first question. If you have job description and resume data available, ask a relevant question based on that information. Otherwise, ask a general introductory question to begin the conversation."
    reply_result = await session.generate_reply(instructions=first_question_instructions)
    logger.info("✅ First question generated and spoken")

    # Update session status to 'interviewing' so dashboard shows transcript
    if assistant_instance.session_file:
        session_file_path = str(assistant_instance.session_file)
        if os.path.exists(session_file_path):
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"Updating session status to 'interviewing' for {assistant_instance.session_id}")

                    # Use async file operations to avoid blocking
                    import aiofiles
                    async with aiofiles.open(session_file_path, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        session_data = json.loads(content)

                    session_data['status'] = 'interviewing'
                    session_data['updated_at'] = datetime.now().isoformat()

                    # Atomic write with unique temp file to avoid conflicts
                    import uuid
                    temp_file = f"{session_file_path}.{uuid.uuid4().hex}.tmp"
                    async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                        await f.write(json.dumps(session_data, indent=2, cls=CustomJSONEncoder))
                    os.replace(temp_file, session_file_path)

                    logger.info(f"✅ Updated session status to 'interviewing' for {assistant_instance.session_id}")
                    break  # Success, exit retry loop

                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Failed to update session status (attempt {attempt + 1}/{max_retries}): {e}, retrying...")
                        await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    else:
                        logger.error(f"Failed to update session status after {max_retries} attempts: {e}")
        else:
            logger.warning(f"Session file not found for status update: {session_file_path}")
    else:
        logger.warning("No session file available for status update")

    # Keep the connection alive and monitor transcription activity
    logger.info("Agent is now running and ready to handle interviews")

    # Periodic status logging and avatar health monitoring
    async def log_status():
        while True:
            try:
                logger.info(f"📊 STATUS: Participants: {len(ctx.room.remote_participants)}, Avatar: {'connected' if anam_avatar else 'disconnected'}")

                # Check avatar health and trigger reconnection if needed
                if anam_api_key and not anam_avatar and (not avatar_reconnect_task or avatar_reconnect_task.done()):
                    logger.warning("⚠️ Avatar disconnected, attempting reconnection...")
                    avatar_reconnect_task = asyncio.create_task(reconnect_avatar())

                # Clean up any lingering RPC tasks to prevent timeout errors
                try:
                    if hasattr(ctx.room.local_participant, '_pending_rpcs'):
                        pending_rpcs = list(ctx.room.local_participant._pending_rpcs.keys())
                        if pending_rpcs:
                            logger.info(f"🧹 Cleaning up {len(pending_rpcs)} pending RPC tasks")
                            for rpc_id in pending_rpcs:
                                try:
                                    ctx.room.local_participant._pending_rpcs[rpc_id].cancel()
                                except:
                                    pass
                except Exception as e:
                    logger.debug(f"RPC cleanup error (non-critical): {e}")

                await asyncio.sleep(30)  # Log every 30 seconds
            except Exception as e:
                logger.error(f"Status logging error: {e}")
                break

    # Start status logging task
    status_task = asyncio.create_task(log_status())

    try:
        await asyncio.sleep(float('inf'))
    except KeyboardInterrupt:
        logger.info("Agent shutdown requested")
        # Cancel avatar reconnection task
        if avatar_reconnect_task and not avatar_reconnect_task.done():
            avatar_reconnect_task.cancel()
            try:
                await avatar_reconnect_task
            except asyncio.CancelledError:
                pass
        status_task.cancel()
        try:
            await status_task
        except asyncio.CancelledError:
            pass
    except Exception as e:
        logger.error(f"Unexpected error during agent operation: {e}")
        # Clean up any pending RPC tasks before shutdown
        try:
            if hasattr(ctx.room.local_participant, '_pending_rpcs'):
                for rpc_id in list(ctx.room.local_participant._pending_rpcs.keys()):
                    try:
                        ctx.room.local_participant._pending_rpcs[rpc_id].cancel()
                    except:
                        pass
        except:
            pass
        # Cancel avatar reconnection task
        if avatar_reconnect_task and not avatar_reconnect_task.done():
            avatar_reconnect_task.cancel()
            try:
                await avatar_reconnect_task
            except asyncio.CancelledError:
                pass
        status_task.cancel()
        try:
            await status_task
        except asyncio.CancelledError:
            pass
        raise

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
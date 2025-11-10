import asyncio
import logging
from typing import Optional
from livekit import rtc
from livekit.plugins import openai
import os

logger = logging.getLogger(__name__)

class AudioManager:
    """Manages audio services including TTS and STT for the interview agent using LiveKit plugins."""

    def __init__(self, agent):
        self.agent = agent
        self.tts = None
        self.stt = None
        self.audio_source = None
        self.audio_track = None
        self.is_speaking = False
        self._current_stt_provider = "livekit-openai"

    async def initialize_audio_services(self):
        """Initialize TTS and STT services."""
        await self._initialize_tts_service()
        await self._initialize_stt_service()

        tts_status = "✅" if self.tts else "❌"
        stt_status = "✅" if self.stt else "❌"
        logger.info(f"Audio services initialized - TTS: {tts_status}, STT: {stt_status}")

    async def _initialize_tts_service(self):
        """Initialize LiveKit OpenAI TTS plugin."""
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            logger.error("OpenAI API key not found - TTS unavailable")
            self.tts = None
            return

        try:
            self.tts = openai.TTS(api_key=openai_key, voice="alloy")
            logger.info("LiveKit OpenAI TTS plugin initialized successfully with 'alloy' voice")
        except Exception as e:
            logger.error(f"TTS plugin initialization failed: {e}")
            self.tts = None

    async def _initialize_stt_service(self):
        """Initialize LiveKit OpenAI STT plugin with Deepgram fallback."""
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                self.stt = openai.STT(api_key=openai_key)
                logger.info("LiveKit OpenAI STT plugin initialized successfully")
                self._current_stt_provider = "livekit-openai"
                return
            except Exception as e:
                logger.warning(f"OpenAI STT plugin initialization failed: {e}, trying Deepgram fallback")

        # Fallback to Deepgram
        deepgram_key = os.getenv("DEEPGRAM_API_KEY")
        if deepgram_key:
            try:
                from livekit.plugins import deepgram
                self.stt = deepgram.STT(api_key=deepgram_key)
                logger.info("LiveKit Deepgram STT plugin initialized as fallback")
                self._current_stt_provider = "livekit-deepgram"
                return
            except Exception as e:
                logger.error(f"Deepgram STT fallback failed: {e}")

        logger.error("No STT providers available")
        self.stt = None
        self._current_stt_provider = None

    async def setup_audio_track(self):
        """Setup audio source and track with enhanced error handling."""
        try:
            self.audio_source = rtc.AudioSource(sample_rate=24000, num_channels=1)
            logger.info("Audio source created: 24kHz, mono")

            self.audio_track = rtc.LocalAudioTrack.create_audio_track(
                "agent-voice", self.audio_source
            )
            logger.info("Audio track created")

            if not self.audio_track:
                raise Exception("Audio track creation failed")

            publish_options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_UNKNOWN)

            # Wait for room to be connected
            max_wait = 10
            wait_count = 0
            while not hasattr(self.agent.room, 'connection_state') or self.agent.room.connection_state != rtc.ConnectionState.CONN_CONNECTED:
                if wait_count >= max_wait:
                    raise Exception("Room connection timeout")
                await asyncio.sleep(0.5)
                wait_count += 1
                logger.debug(f"Waiting for room connection... ({wait_count}/{max_wait})")

            local_participant = self.agent.room.local_participant
            if not local_participant:
                raise Exception("Local participant is None")

            existing_audio_tracks = [
                p for p in local_participant.track_publications.values()
                if p.track and p.track.kind == rtc.TrackKind.KIND_AUDIO and p.source == rtc.TrackSource.SOURCE_MICROPHONE
            ]
            if existing_audio_tracks:
                logger.warning("Microphone audio track already published, skipping new track publication")
                self.audio_track = existing_audio_tracks[0].track
                return

            publication = await local_participant.publish_track(
                self.audio_track, publish_options
            )

            if publication:
                logger.info(f"Audio track published successfully - SID: {publication.sid}")
                published_tracks = list(local_participant.track_publications.values())
                audio_tracks = [p for p in published_tracks if p.track and p.track.kind == rtc.TrackKind.KIND_AUDIO]
                logger.info(f"Total published audio tracks: {len(audio_tracks)}")
            else:
                raise Exception("Track publication returned None")

        except Exception as e:
            logger.error(f"Audio track setup failed: {e}", exc_info=True)
            self.audio_source = None
            self.audio_track = None
            raise

    async def say(self, text: str, check_speaking: bool = True, max_retries: int = 2):
        """Speech synthesis using LiveKit TTS plugin."""
        if self.is_speaking and check_speaking:
            logger.warning(f"Agent already speaking, queuing: {text[:50]}...")
            await asyncio.sleep(1)
            if self.is_speaking:
                logger.warning("Still speaking, skipping message")
                return

        if not text or not text.strip():
            logger.warning("Empty text provided to _say, skipping")
            return

        for attempt in range(max_retries):
            self.is_speaking = True
            self.agent.state.last_spoken_text = text

            try:
                if not self.tts:
                    logger.error("TTS service not available")
                    return

                if not self.audio_source or not self.audio_track:
                    logger.error("Audio source/track not initialized")
                    return

                logger.info(f"Agent speaking (attempt {attempt + 1}): '{text[:100]}{'...' if len(text) > 100 else ''}'")

                # Use LiveKit TTS plugin synthesize
                async for synthesized in self.tts.synthesize(text):
                    await self.audio_source.capture_frame(synthesized.frame)

                logger.info("Speech completed successfully")
                return

            except Exception as e:
                logger.error(f"Speech synthesis error (attempt {attempt + 1}): {e}")

            finally:
                self.is_speaking = False

            if attempt < max_retries - 1:
                await asyncio.sleep(1)

        logger.error(f"Speech synthesis failed after {max_retries} attempts")

    async def say_with_completion_tracking(self, text: str, max_retries: int = 3):
        """Enhanced speech synthesis with completion tracking and retry logic."""
        logger.info(f"Speaking with completion tracking: '{text[:50]}...'")

        try:
            await self.say(text, check_speaking=False, max_retries=max_retries)
            logger.info("Speech completed successfully with tracking")
        except Exception as e:
            logger.error(f"Speech with completion tracking failed: {e}")
            raise

    async def wait_for_all_speech_completion(self, timeout: float = 15.0):
        """Wait for all speech to complete before proceeding."""
        logger.info(f"Waiting for all speech completion (timeout: {timeout}s)")

        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            if not self.is_speaking:
                logger.info("All speech completed")
                return True
            await asyncio.sleep(0.1)

        logger.warning(f"Speech completion timeout after {timeout}s")
        return False

    async def test_audio_pipeline(self, test_text: str) -> bool:
        """Test the audio pipeline using LiveKit TTS plugin."""
        logger.info(f"Testing audio pipeline with: '{test_text}'")

        if not all([self.tts, self.audio_source, self.audio_track]):
            logger.error("Audio pipeline components not ready")
            return False

        try:
            frame_count = 0
            max_frames_to_test = 5

            # Use TTS plugin synthesize for testing
            async for synthesized in self.tts.synthesize(test_text):
                await self.audio_source.capture_frame(synthesized.frame)
                frame_count += 1
                if frame_count >= max_frames_to_test:
                    break

            success = frame_count > 0
            logger.info(f"Audio pipeline test {'passed' if success else 'failed'}: {frame_count} frames")
            return success

        except Exception as e:
            logger.error(f"Audio pipeline test failed: {e}")
            return False

    async def cleanup(self):
        """Cleanup audio resources."""
        if self.tts and hasattr(self.tts, 'aclose'):
            await self.tts.aclose()
        self.tts = None
        if self.stt and hasattr(self.stt, 'aclose'):
            await self.stt.aclose()
        self.stt = None
        self.audio_source = None
        self.audio_track = None

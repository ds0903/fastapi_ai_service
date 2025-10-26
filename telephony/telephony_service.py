"""
Telephony service for handling voice calls via Binotel
Integrates with Google Speech-to-Text and Text-to-Speech
Uses existing ClaudeService and BookingService
"""
import logging
import base64
import io
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from google.cloud import speech_v1 as speech
from google.cloud import texttospeech

from .config import binotel_settings
from .models import CallSession, CallStatus, CallDirection, VoiceMessage, AudioResponse
from app.services.claude_service import ClaudeService
from app.services.booking_service import BookingService
from app.services.google_sheets import GoogleSheetsService
from app.config import ProjectConfig
from app.utils.date_calendar import generate_calendar_for_claude

logger = logging.getLogger(__name__)


class TelephonyService:
    """Service for handling voice calls through Binotel with Google Cloud AI"""
    
    def __init__(self, db: Session, project_config: ProjectConfig, claude_service: ClaudeService):
        """
        Initialize telephony service
        
        Args:
            db: Database session
            project_config: Project configuration
            claude_service: Claude AI service instance
        """
        self.db = db
        self.project_config = project_config
        self.claude_service = claude_service
        
        # Initialize Google Cloud clients
        try:
            self.speech_client = speech.SpeechClient()
            self.tts_client = texttospeech.TextToSpeechClient()
            logger.info("Google Cloud Speech and TTS clients initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Cloud clients: {e}")
            self.speech_client = None
            self.tts_client = None
        
        # Check Binotel credentials
        if binotel_settings.binotel_api_key and binotel_settings.binotel_api_secret:
            logger.info("Binotel credentials configured")
        else:
            logger.warning("Binotel credentials not set - telephony will not work")
        
        # Initialize other services
        self.booking_service = BookingService(db, project_config)
        self.sheets_service = GoogleSheetsService(project_config)
        
        # Store active call sessions in memory
        self.active_calls: Dict[str, CallSession] = {}
    
    async def transcribe_audio(self, audio_data: bytes) -> Optional[VoiceMessage]:
        """
        Transcribe audio using Google Speech-to-Text
        
        Args:
            audio_data: Audio data in bytes
            
        Returns:
            VoiceMessage with transcribed text or None
        """
        if not self.speech_client:
            logger.error("Speech client not initialized")
            return None
        
        try:
            audio = speech.RecognitionAudio(content=audio_data)
            
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=binotel_settings.speech_sample_rate,
                language_code=binotel_settings.speech_language,
                enable_automatic_punctuation=True,
                model="phone_call",  # Optimized for phone call audio
            )
            
            response = self.speech_client.recognize(config=config, audio=audio)
            
            if not response.results:
                logger.warning("No speech recognized in audio")
                return None
            
            # Get the first result (most confident)
            result = response.results[0]
            alternative = result.alternatives[0]
            
            logger.info(f"Transcribed: '{alternative.transcript}' (confidence: {alternative.confidence})")
            
            return VoiceMessage(
                text=alternative.transcript,
                confidence=alternative.confidence,
                language=binotel_settings.speech_language
            )
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}", exc_info=True)
            return None
    
    async def synthesize_speech(self, text: str) -> Optional[AudioResponse]:
        """
        Synthesize speech using Google Text-to-Speech
        
        Args:
            text: Text to synthesize
            
        Returns:
            AudioResponse with audio data or None
        """
        if not self.tts_client:
            logger.error("TTS client not initialized")
            return None
        
        try:
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            voice = texttospeech.VoiceSelectionParams(
                language_code=binotel_settings.voice_language,
                name=binotel_settings.voice_name,
                ssml_gender=texttospeech.SsmlVoiceGender[binotel_settings.voice_gender]
            )
            
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                sample_rate_hertz=binotel_settings.speech_sample_rate
            )
            
            response = self.tts_client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            logger.info(f"Synthesized speech for text: '{text[:50]}...'")
            
            return AudioResponse(
                audio_data=response.audio_content,
                format="wav",
                sample_rate=binotel_settings.speech_sample_rate
            )
            
        except Exception as e:
            logger.error(f"Error synthesizing speech: {e}", exc_info=True)
            return None
    
    async def handle_incoming_call(self, call_id: str, from_number: str, to_number: str) -> Dict[str, Any]:
        """
        Handle incoming call initialization
        
        Args:
            call_id: Binotel Call ID
            from_number: Caller phone number
            to_number: Called number
            
        Returns:
            Response dict with welcome message and audio
        """
        logger.info(f"Handling incoming call: call_id={call_id}, from={from_number}")
        
        # Create call session
        call_session = CallSession(
            call_id=call_id,
            from_number=from_number,
            to_number=to_number,
            client_id=from_number,  # Use phone as client_id
            status=CallStatus.INITIATED,
            direction=CallDirection.INBOUND,
            project_id="default"
        )
        
        self.active_calls[call_id] = call_session
        
        # Generate welcome message
        welcome_text = "Вітаю! Я штучний інтелект салону краси. Чим можу вам допомогти?"
        
        # Synthesize welcome audio
        audio_response = await self.synthesize_speech(welcome_text)
        
        if not audio_response:
            logger.error(f"Failed to synthesize welcome message for call {call_id}")
            return {
                "success": False,
                "error": "Failed to generate welcome audio"
            }
        
        # Add to conversation history
        call_session.conversation_history.append({
            "role": "claude",
            "message": welcome_text,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Update call status
        call_session.status = CallStatus.IN_PROGRESS
        
        return {
            "success": True,
            "audio_data": base64.b64encode(audio_response.audio_data).decode(),
            "message": welcome_text
        }
    
    async def process_audio_input(
        self,
        call_id: str,
        audio_data: bytes
    ) -> Dict[str, Any]:
        """
        Process audio input from user and generate AI response
        
        Args:
            call_id: Binotel Call ID
            audio_data: Audio data from user
            
        Returns:
            Response dict with AI response and audio
        """
        logger.info(f"Processing audio input for call {call_id}")
        
        # Get call session
        call_session = self.active_calls.get(call_id)
        if not call_session:
            logger.error(f"Call session not found for call_id={call_id}")
            return {
                "success": False,
                "error": "Call session not found"
            }
        
        # Transcribe audio
        voice_message = await self.transcribe_audio(audio_data)
        
        if not voice_message:
            # No speech detected - ask user to repeat
            repeat_text = "Я вас не почув. Будь ласка, повторіть."
            audio_response = await self.synthesize_speech(repeat_text)
            
            return {
                "success": True,
                "audio_data": base64.b64encode(audio_response.audio_data).decode() if audio_response else None,
                "message": repeat_text,
                "should_continue": True
            }
        
        speech_text = voice_message.text
        logger.info(f"User said: '{speech_text}'")
        
        # Add user message to conversation history
        call_session.conversation_history.append({
            "role": "client",
            "message": speech_text,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Build dialogue history
        dialogue_history = self._build_dialogue_history(call_session)
        
        # Get current date and calendar
        import pytz
        berlin_tz = pytz.timezone('Europe/Berlin')
        berlin_now = datetime.now(berlin_tz)
        current_date = berlin_now.strftime("%d.%m.%Y %H:%M")
        day_of_week = berlin_now.strftime("%A")
        date_calendar = generate_calendar_for_claude(berlin_now, days_ahead=30)
        
        # Get available slots and client bookings
        available_slots = {}
        reserved_slots = {}
        client_bookings = await self.booking_service.get_client_bookings_as_string(call_session.from_number)
        
        try:
            # Generate AI response using existing ClaudeService
            main_response = await self.claude_service.generate_main_response(
                self.project_config,
                dialogue_history,
                speech_text,
                current_date,
                day_of_week,
                date_calendar,
                available_slots,
                reserved_slots,
                client_bookings,
                call_id,
                slots_target_date=None,
                zip_history=None,
                record_error=None,
                newbie_status=1,
                image_url=None
            )
            
            ai_response_text = main_response.gpt_response
            
            # Add AI response to conversation history
            call_session.conversation_history.append({
                "role": "claude",
                "message": ai_response_text,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Process booking if needed
            if any([main_response.activate_booking, main_response.reject_order, 
                   main_response.change_order]):
                booking_result = await self.booking_service.process_booking_action(
                    main_response,
                    call_session.from_number,
                    call_id,
                    call_session.from_number
                )
                
                if booking_result.get("success") and booking_result.get("message"):
                    ai_response_text += f" {booking_result['message']}"
            
            logger.info(f"AI response: '{ai_response_text[:100]}...'")
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}", exc_info=True)
            ai_response_text = "Вибачте, сталася помилка. Спробуйте ще раз."
        
        # Synthesize AI response
        audio_response = await self.synthesize_speech(ai_response_text)
        
        if not audio_response:
            logger.error(f"Failed to synthesize AI response for call {call_id}")
            return {
                "success": False,
                "error": "Failed to generate response audio"
            }
        
        # Check if call should end
        should_end = self._should_end_call(main_response if 'main_response' in locals() else None)
        
        if should_end:
            goodbye_text = "Дякую за дзвінок! До побачення!"
            goodbye_audio = await self.synthesize_speech(goodbye_text)
            
            # Combine response and goodbye
            combined_audio = audio_response.audio_data + (goodbye_audio.audio_data if goodbye_audio else b"")
            
            # End call
            await self._end_call(call_session)
            
            return {
                "success": True,
                "audio_data": base64.b64encode(combined_audio).decode(),
                "message": ai_response_text + " " + goodbye_text,
                "should_continue": False
            }
        
        return {
            "success": True,
            "audio_data": base64.b64encode(audio_response.audio_data).decode(),
            "message": ai_response_text,
            "should_continue": True
        }
    
    def _build_dialogue_history(self, call_session: CallSession) -> str:
        """Build dialogue history string from call session"""
        history = []
        
        for entry in call_session.conversation_history:
            role = "Клієнт" if entry["role"] == "client" else "Консультант"
            history.append(f"{role}: {entry['message']}")
        
        return "\n".join(history)
    
    def _should_end_call(self, main_response: Any) -> bool:
        """Determine if call should end based on AI response"""
        if not main_response:
            return False
        
        # End call if booking was confirmed or client said goodbye
        keywords = ["до побачення", "дякую", "все", "хватит", "достаточно"]
        response_lower = main_response.gpt_response.lower()
        
        return any(keyword in response_lower for keyword in keywords) or \
               main_response.activate_booking or \
               main_response.reject_order
    
    async def _end_call(self, call_session: CallSession):
        """End call and save record"""
        call_session.ended_at = datetime.utcnow()
        call_session.status = CallStatus.COMPLETED
        
        # Save call record
        await self._save_call_record(call_session)
        
        # Remove from active calls
        if call_session.call_id in self.active_calls:
            del self.active_calls[call_session.call_id]
        
        logger.info(f"Call {call_session.call_id} ended")
    
    async def _save_call_record(self, call_session: CallSession):
        """Save call record to database"""
        try:
            from app.database import Dialogue
            
            # Calculate duration
            if call_session.ended_at:
                duration = (call_session.ended_at - call_session.started_at).seconds
            else:
                call_session.ended_at = datetime.utcnow()
                duration = (call_session.ended_at - call_session.started_at).seconds
            
            # Save full conversation as dialogue entries
            for entry in call_session.conversation_history:
                dialogue = Dialogue(
                    project_id=call_session.project_id,
                    client_id=call_session.client_id,
                    role=entry["role"],
                    message=entry["message"],
                    timestamp=datetime.fromisoformat(entry["timestamp"])
                )
                self.db.add(dialogue)
            
            self.db.commit()
            
            logger.info(f"Saved call record for {call_session.call_id}, duration: {duration}s")
            
        except Exception as e:
            logger.error(f"Error saving call record: {e}", exc_info=True)
            self.db.rollback()
    
    def handle_call_status(self, call_id: str, call_status: str):
        """Handle call status updates from Binotel"""
        logger.info(f"Call {call_id} status update: {call_status}")
        
        if call_id in self.active_calls:
            call_session = self.active_calls[call_id]
            
            if call_status in ["completed", "failed", "busy", "no-answer", "cancelled"]:
                call_session.status = CallStatus(call_status)
                call_session.ended_at = datetime.utcnow()
                
                # Save and remove from active calls
                import asyncio
                asyncio.create_task(self._save_call_record(call_session))
                
                del self.active_calls[call_id]
    
    def get_active_calls_count(self) -> int:
        """Get number of active calls"""
        return len(self.active_calls)
    
    def get_call_info(self, call_id: str) -> Optional[CallSession]:
        """Get information about specific call"""
        return self.active_calls.get(call_id)

import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from anthropic import AsyncAnthropic
from sqlalchemy.orm import Session
import logging

from ..config import settings, ProjectConfig
from ..utils.prompt_loader import get_prompt
from ..models import (
    IntentDetectionResult, 
    ServiceIdentificationResult, 
    ClaudeMainResponse,
    DialogueHistory
)
from ..database import increment_counter

logger = logging.getLogger(__name__)


class ClaudeService:
    """Service for handling Claude AI interactions"""
    
    def __init__(self, db: Session):
        self.db = db
        try:
            self.client1 = AsyncAnthropic(api_key=settings.claude_api_key_1)
            self.client2 = AsyncAnthropic(api_key=settings.claude_api_key_2)
            logger.debug("ClaudeService initialized with two async API clients")
        except Exception as e:
            logger.error(f"Failed to initialize Claude clients: {e}")
            raise
    
    def _get_claude_client(self, counter: int, message_id: str = None) -> AsyncAnthropic:
        """Get Claude client based on counter for load balancing"""
        client = self.client1 if counter % 2 == 0 else self.client2
        if message_id:
            logger.debug(f"Message ID: {message_id} - Selected Claude client {1 if counter % 2 == 0 else 2} for counter {counter}")
        else:
            logger.debug(f"Selected Claude client {1 if counter % 2 == 0 else 2} for counter {counter}")
        return client
    
    async def detect_intent(
        self, 
        project_config: ProjectConfig,
        dialogue_history: str,
        current_message: str,
        message_id: str
    ) -> IntentDetectionResult:
        """
        Module 1: Intent detection
        Determines if client wants to book, specified date, or time preferences
        """
        logger.info(f"Message ID: {message_id} - Starting intent detection for project {project_config.project_id}")
        logger.debug(f"Message ID: {message_id} - Message for intent detection: '{current_message[:100]}...'")
        
        counter = increment_counter(self.db)
        client = self._get_claude_client(counter, message_id)
        
        prompt = self._build_intent_detection_prompt(
            project_config, 
            dialogue_history, 
            current_message
        )
        
        logger.info(f"Message ID: {message_id} - Built intent detection prompt, length: {len(prompt)} characters")
        
        try:
            logger.info(f"Message ID: {message_id} - Sending async request to Claude for intent detection. Dialogue history: {dialogue_history}, current message: {current_message}")
            response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            raw_response = response.content[0].text
            logger.info(f"Message ID: {message_id} - Claude raw response for intent detection: {raw_response}")
            logger.info(f"Message ID: {message_id} - Intent detection response length: {len(raw_response)} chars")
            
            if not raw_response.strip():
                logger.warning(f"Message ID: {message_id} - Intent detection received empty response from Claude")
                return IntentDetectionResult(waiting=1)
            
            result = self._parse_intent_response(raw_response, message_id)
            intent_result = IntentDetectionResult(**result)
            
            logger.info(f"Message ID: {message_id} - Claude thinking parsed result: {result}")
            logger.info(f"Message ID: {message_id} - Intent detection completed: waiting={intent_result.waiting}, date_order={intent_result.date_order}, time_range={intent_result.desire_time0}-{intent_result.desire_time1}")
            return intent_result
            
        except Exception as e:
            logger.error(f"Message ID: {message_id} - Error in intent detection: {e}", exc_info=True)
            logger.warning(f"Message ID: {message_id} - Falling back to default intent result (waiting=1)")
            return IntentDetectionResult(waiting=1)
    
    async def identify_service(
        self,
        project_config: ProjectConfig,
        dialogue_history: str,
        current_message: str,
        message_id: str
    ) -> ServiceIdentificationResult:
        """
        Module 2: Service identification
        Determines which service client wants and its duration
        """
        logger.info(f"Message ID: {message_id} - Starting service identification for project {project_config.project_id}")
        logger.debug(f"Message ID: {message_id} - Available services: {list(project_config.services.keys())}")
        
        counter = increment_counter(self.db)
        client = self._get_claude_client(counter, message_id)
        
        prompt = self._build_service_identification_prompt(
            project_config,
            dialogue_history,
            current_message
        )
        
        logger.debug(f"Message ID: {message_id} - Built service identification prompt, length: {len(prompt)} characters")
        
        try:
            logger.info(f"Message ID: {message_id} - Sending async request to Claude for service identification. Dialogue history: {dialogue_history}, current message: {current_message}")
            response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            raw_response = response.content[0].text
            logger.info(f"Message ID: {message_id} - Claude raw response for service identification: {raw_response}")
            logger.info(f"Message ID: {message_id} - Service identification response length: {len(raw_response)} chars")
            
            if not raw_response.strip():
                logger.warning(f"Message ID: {message_id} - Service identification received empty response from Claude")
                return ServiceIdentificationResult(time_fraction=1, service_name="unknown")
            
            result = self._parse_service_response(raw_response, message_id)
            service_result = ServiceIdentificationResult(**result)
            
            logger.info(f"Message ID: {message_id} - Claude thinking parsed result: {result}")
            duration_minutes = service_result.time_fraction * 30
            logger.info(f"Message ID: {message_id} - Service identification completed: service='{service_result.service_name}', duration={service_result.time_fraction} slots ({duration_minutes} minutes)")
            return service_result
            
        except Exception as e:
            logger.error(f"Message ID: {message_id} - Error in service identification: {e}", exc_info=True)
            logger.warning(f"Message ID: {message_id} - Falling back to default service result (unknown, 1 slot)")
            return ServiceIdentificationResult(time_fraction=1, service_name="unknown")
    
    async def generate_main_response(
        self,
        project_config: ProjectConfig,
        dialogue_history: str,
        current_message: str,
        current_date: str,
        available_slots: Dict[str, Any],
        reserved_slots: Dict[str, Any],
        rows_of_owner: str,
        message_id: str,
        zip_history: Optional[str] = None,
        record_error: Optional[str] = None
    ) -> ClaudeMainResponse:
        """
        Module 3: Main response generation
        Core module that generates client response and booking commands
        """
        logger.info(f"Message ID: {message_id} - Starting main response generation for project {project_config.project_id}")
        logger.debug(f"Message ID: {message_id} - Available slots count: {len(available_slots)}, reserved slots count: {len(reserved_slots)}")
        logger.debug(f"Message ID: {message_id} - Current message: '{current_message[:100]}...'")
        
        counter = increment_counter(self.db)
        client = self._get_claude_client(counter, message_id)
        
        prompt = self._build_main_response_prompt(
            project_config,
            dialogue_history,
            current_message,
            current_date,
            available_slots,
            reserved_slots,
            rows_of_owner,
            zip_history,
            record_error
        )
        
        logger.debug(f"Message ID: {message_id} - Built main response prompt, length: {len(prompt)} characters")
        
        try:
            logger.info(f"Message ID: {message_id} - Sending async request to Claude for main response generation. Dialogue history: {dialogue_history}, current message: {current_message}, current date: {current_date}, available slots: {available_slots}, reserved slots: {reserved_slots}, rows of owner: {rows_of_owner}, zip history: {zip_history}, record error: {record_error}")
            response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            raw_response = response.content[0].text
            logger.info(f"Message ID: {message_id} - Claude raw response for main response: {raw_response}")
            logger.info(f"Message ID: {message_id} - Main response length: {len(raw_response)} chars")
            
            if not raw_response.strip():
                logger.warning(f"Message ID: {message_id} - Main response received empty response from Claude")
                return ClaudeMainResponse(gpt_response="Извините, произошла ошибка. Попробуйте еще раз позже.")
            
            result = self._parse_main_response(raw_response, message_id)
            main_response = ClaudeMainResponse(**result)
            
            logger.info(f"Message ID: {message_id} - Claude thinking parsed result: {result}")
            logger.info(f"Message ID: {message_id} - Main response generated successfully: {len(main_response.gpt_response)} chars, booking actions: activate={main_response.activate_booking}, reject={main_response.reject_order}, change={main_response.change_order}")
            
            if main_response.activate_booking:
                logger.info(f"Message ID: {message_id} - Booking activation requested: specialist={main_response.cosmetolog}, date={main_response.date_order}, time={main_response.time_set_up}")
            elif main_response.reject_order:
                logger.info(f"Message ID: {message_id} - Booking rejection requested: date={main_response.date_reject}, time={main_response.time_reject}")
            elif main_response.change_order:
                logger.info(f"Message ID: {message_id} - Booking change requested: new specialist={main_response.cosmetolog}, new date={main_response.date_order}")
            
            return main_response
            
        except Exception as e:
            logger.error(f"Message ID: {message_id} - Error in generate_main_response: {e}", exc_info=True)
            logger.warning(f"Message ID: {message_id} - Falling back to default error response")
            return ClaudeMainResponse(
                gpt_response="Извините, произошла ошибка. Попробуйте еще раз позже."
            )
    
    async def compress_dialogue(
        self,
        project_config: ProjectConfig,
        dialogue_history: str
    ) -> str:
        """
        Module 4: Dialogue compression
        Compresses old dialogue to save tokens
        """
        counter = increment_counter(self.db)
        client = self._get_claude_client(counter)
        
        prompt = self._build_compression_prompt(project_config, dialogue_history)
        
        try:
            response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            return response.content[0].text.strip()
            
        except Exception as e:
            return dialogue_history[:500] + "..."
    
    def _build_intent_detection_prompt(
        self,
        project_config: ProjectConfig,
        dialogue_history: str,
        current_message: str
    ) -> str:
        """Build prompt for intent detection"""
        base_prompt = get_prompt("intent_detection")
        current_date = datetime.now().strftime("%d.%m.%Y")
        
        return f"""
        {base_prompt}
        
        current_date: {current_date}
        dialogue_history: {dialogue_history}
        current_message: {current_message}
        """
    
    def _build_service_identification_prompt(
        self,
        project_config: ProjectConfig,
        dialogue_history: str,
        current_message: str
    ) -> str:
        """Build prompt for service identification"""
        base_prompt = get_prompt("service_identification")
        
        return f"""
        {base_prompt}
        
        dialogue_history: {dialogue_history}
        current_message: {current_message}
        """
    
    def _build_main_response_prompt(
        self,
        project_config: ProjectConfig,
        dialogue_history: str,
        current_message: str,
        current_date: str,
        available_slots: Dict[str, Any],
        reserved_slots: Dict[str, Any],
        rows_of_owner: str,
        zip_history: Optional[str],
        record_error: Optional[str]
    ) -> str:
        """Build prompt for main response generation"""
        base_prompt = get_prompt("main_response")
        weekday = datetime.now().strftime("%A")
        record_status = record_error if record_error else "-"
        
        return f"""
        {base_prompt}
        
        current_date: {current_date}
        weekday: {weekday}
        available_slots: {json.dumps(available_slots, ensure_ascii=False)}
        reserved_slots: {json.dumps(reserved_slots, ensure_ascii=False)}
        rows_of_owner: {rows_of_owner}
        zip_history: {zip_history or ""}
        record_status: {record_status}
        dialogue_history: {dialogue_history}
        current_message: {current_message}
        """
    
    def _build_compression_prompt(
        self,
        project_config: ProjectConfig,
        dialogue_history: str
    ) -> str:
        """Build prompt for dialogue compression"""
        base_prompt = get_prompt("dialogue_compression")
        
        return f"""
        {base_prompt}
        
        Диалог для сжатия:
        {dialogue_history}
        """
    
    def _parse_intent_response(self, response: str, message_id: str) -> Dict[str, Any]:
        """Parse intent detection response"""
        try:
            logger.debug(f"Message ID: {message_id} - Parsing intent response: {response[:200]}...")
            # Handle "json{...}" prefix that Claude sometimes adds
            clean_response = response.strip()
            if clean_response.startswith("json"):
                clean_response = clean_response[4:].strip()
            
            result = json.loads(clean_response)
            parsed_result = {
                "waiting": result.get("waiting"),
                "date_order": result.get("date_order"),
                "desire_time0": result.get("desire_time0"),
                "desire_time1": result.get("desire_time1")
            }
            logger.debug(f"Message ID: {message_id} - Intent response parsed successfully: {parsed_result}")
            return parsed_result
        except Exception as e:
            logger.error(f"Message ID: {message_id} - Failed to parse intent response JSON: {e}")
            logger.warning(f"Message ID: {message_id} - Raw response was: '{response[:100]}...'")
            return {"waiting": 1}
    
    def _parse_service_response(self, response: str, message_id: str) -> Dict[str, Any]:
        """Parse service identification response"""
        try:
            logger.debug(f"Message ID: {message_id} - Parsing service response: {response[:200]}...")
            # Handle "json{...}" prefix that Claude sometimes adds
            clean_response = response.strip()
            if clean_response.startswith("json"):
                clean_response = clean_response[4:].strip()
            
            result = json.loads(clean_response)
            parsed_result = {
                "time_fraction": result.get("time_fractions", result.get("time_fraction", 1)),
                "service_name": result.get("service_name", "unknown")
            }
            logger.debug(f"Message ID: {message_id} - Service response parsed successfully: {parsed_result}")
            return parsed_result
        except Exception as e:
            logger.error(f"Message ID: {message_id} - Failed to parse service response JSON: {e}")
            logger.warning(f"Message ID: {message_id} - Raw response was: '{response[:100]}...'")
            return {"time_fraction": 1, "service_name": "unknown"}
    
    def _parse_main_response(self, response: str, message_id: str) -> Dict[str, Any]:
        """Parse main response"""
        try:
            logger.debug(f"Message ID: {message_id} - Parsing main response: {response[:200]}...")
            # Handle "json{...}" prefix and clean control characters
            import re
            clean_response = response.strip()
            if clean_response.startswith("json"):
                clean_response = clean_response[4:].strip()
            
            # Remove control characters that can break JSON parsing
            clean_response = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', clean_response)
            
            result = json.loads(clean_response)
            parsed_result = {
                "gpt_response": result.get("client_response", result.get("gpt_response", "")),
                "pic": result.get("pic"),
                "activate_booking": result.get("activate_booking"),
                "reject_order": result.get("reject_order"),
                "change_order": result.get("change_order"),
                "cosmetolog": result.get("cosmetolog"),
                "time_set_up": result.get("time_set_up"),
                "date_order": result.get("date_order"),
                "time_reject": result.get("time_reject"),
                "date_reject": result.get("date_reject"),
                "procedure": result.get("procedure"),
                "phone": result.get("phone"),
                "name": result.get("name"),
                "feedback": result.get("feedback")
            }
            logger.debug(f"Message ID: {message_id} - Main response parsed successfully: {parsed_result}")
            return parsed_result
        except Exception as e:
            logger.error(f"Message ID: {message_id} - Failed to parse main response JSON: {e}")
            logger.warning(f"Message ID: {message_id} - Raw response was: '{response[:200]}...'")
            return {
                "gpt_response": "Извините, произошла ошибка. Попробуйте еще раз.",
            } 
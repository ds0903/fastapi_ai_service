"""
Message processor for aiogram bot
Adapts existing process_message_async logic for use with aiogram
"""
import asyncio
import logging
from datetime import datetime, date, time
from typing import Dict, Any, Optional

from telegram.database import SessionLocal
from telegram.services.message_queue import MessageQueueService
from telegram.services.claude_service import ClaudeService
from telegram.services.google_sheets import GoogleSheetsService
from telegram.services.booking_service import BookingService
from telegram.services.email_service import EmailService
from telegram.services.dialogue_archiving import DialogueArchivingService
from telegram.utils.date_calendar import generate_calendar_for_claude
from telegram.models import MessageStatus
from telegram.database import Dialogue, BookingError
import pytz

logger = logging.getLogger(__name__)


def format_time_difference(timestamp1: datetime, timestamp2: datetime) -> str:
    """Format time difference between two timestamps"""
    if not timestamp1 or not timestamp2:
        return ""
    
    diff = abs(timestamp2 - timestamp1)
    total_seconds = int(diff.total_seconds())
    
    if total_seconds < 60:
        return f"через {total_seconds} сек"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        return f"через {minutes} мін"
    elif total_seconds < 86400:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if minutes > 0:
            return f"через {hours} г {minutes} мін"
        return f"через {hours} г"
    else:
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        if hours > 0:
            return f"через {days} дн {hours} г"
        return f"через {days} дн"


def get_dialogue_history(db, project_id: str, client_id: str, message_id: str) -> str:
    """Get recent dialogue history for a client"""
    dialogue_service = DialogueArchivingService()
    recent_history = dialogue_service.get_recent_dialogue_history(db, project_id, client_id)
    logger.debug(f"Message ID: {message_id} - Built recent dialogue history: {len(recent_history)} characters")
    return recent_history


def save_dialogue_entry(db, project_id: str, client_id: str, message: str, role: str, message_id: str):
    """Save a dialogue entry"""
    dialogue_service = DialogueArchivingService()
    dialogue_service.add_dialogue_entry(db, project_id, client_id, role, message)
    logger.debug(f"Message ID: {message_id} - Dialogue entry saved for role={role}")


def parse_date(date_str: str) -> Optional[date]:
    """Parse date string with error handling"""
    if not date_str:
        return None
    
    try:
        cleaned_date = date_str.strip()
        
        if len(cleaned_date.split('.')) == 2:
            current_year = datetime.now().year
            parsed_date = datetime.strptime(f"{cleaned_date}.{current_year}", "%d.%m.%Y").date()
            
            today = date.today()
            if parsed_date < today:
                parsed_date = parsed_date.replace(year=current_year + 1)
            elif parsed_date > today.replace(year=current_year + 1):
                return None
            
            return parsed_date
        
        elif len(cleaned_date.split('.')) == 3:
            return datetime.strptime(cleaned_date, "%d.%m.%Y").date()
        
        return None
    
    except Exception as e:
        logger.warning(f"Failed to parse date '{date_str}': {e}")
        return None


def parse_time(time_str: str) -> Optional[time]:
    """Parse time string"""
    try:
        return datetime.strptime(time_str, "%H:%M").time()
    except Exception:
        return None


def extract_date_from_context(dialogue_history: str, zip_history: str) -> Optional[str]:
    """Extract date from conversation context"""
    import re
    
    combined_text = f"{dialogue_history} {zip_history or ''}"
    
    date_patterns = [
        r'\b(\d{1,2})\.\s*(\d{1,2})\b',
        r'на\s+(\d{1,2})\.(\d{1,2})',
        r'записаться\s+(\d{1,2})\.(\d{1,2})',
    ]
    
    for pattern in date_patterns:
        matches = re.findall(pattern, combined_text)
        if matches:
            day, month = matches[-1]
            return f"{day.zfill(2)}.{month.zfill(2)}"
    
    return None


async def process_message_async(
    project_id: str,
    client_id: str,
    queue_item_id: str,
    message_id: str,
    contact_send_id: str = None,
    project_configs: dict = None,
    global_claude_service: ClaudeService = None
) -> dict:
    """
    Process message with AI and return response data
    Adapted from main.py for use with aiogram
    """
    logger.info(f"Message ID: {message_id} - Starting message processing for client_id={client_id}")
    
    error_count = 0
    db = SessionLocal()
    
    try:
        # Get project configuration
        if not project_configs or project_id not in project_configs:
            logger.error(f"Message ID: {message_id} - Project config not found for {project_id}")
            return {
                "error": "Project configuration not found",
                "error_count": 1,
                "gpt_response": "Сталася помилка конфігурації проекту",
                "pic": ""
            }
        
        project_config = project_configs[project_id]
        
        # Initialize services
        queue_service = MessageQueueService(db)
        claude_service = global_claude_service
        sheets_service = GoogleSheetsService(project_config)
        booking_service = BookingService(db, project_config, contact_send_id=contact_send_id)
        
        # Get message from queue
        message_item = queue_service.get_message_for_processing(project_id, client_id, message_id)
        if not message_item:
            logger.warning(f"Message ID: {message_id} - No message in queue")
            return {
                "error": "No message found",
                "error_count": 1,
                "gpt_response": "Повідомлення не знайдено в черзі",
                "pic": ""
            }
        
        # Extract image URL if present
        from telegram.models import SendPulseMessage
        temp_message = SendPulseMessage(
            date=datetime.now().strftime("%d.%m.%Y %H:%M"),
            response=message_item.aggregated_message,
            project_id=project_id
        )
        image_url = temp_message.get_image_url()
        clean_message = temp_message.get_text_without_image_url() if image_url else message_item.aggregated_message
        
        if image_url:
            logger.info(f"Message ID: {message_id} - Image URL detected: {image_url[:100]}...")
        
        # Update status to processing
        queue_service.update_message_status(message_item.id, MessageStatus.PROCESSING, message_id)
        
        # Get dialogue history
        dialogue_history = get_dialogue_history(db, project_id, client_id, message_id)
        dialogue_service = DialogueArchivingService()
        zip_history = dialogue_service.get_zip_history(db, project_id, client_id)
        
        # Get current date and calendar
        berlin_tz = pytz.timezone('Europe/Berlin')
        berlin_now = datetime.now(berlin_tz)
        current_date = berlin_now.strftime("%d.%m.%Y %H:%M")
        day_of_week = berlin_now.strftime("%A")
        date_calendar = generate_calendar_for_claude(berlin_now, days_ahead=30)
        
        current_message_text = clean_message if image_url else message_item.aggregated_message
        
        # Step 1: Intent detection
        logger.info(f"Message ID: {message_id} - Starting intent detection")
        intent_result = await claude_service.detect_intent(
            project_config,
            dialogue_history,
            current_message_text,
            current_date,
            day_of_week,
            date_calendar,
            message_id,
            zip_history
        )
        
        # Steps 2 & 3: Service identification and slot fetching
        service_result = None
        available_slots = {}
        reserved_slots = {}
        slots_target_date = None
        
        if not intent_result.waiting:
            logger.info(f"Message ID: {message_id} - Client wants booking, fetching services and slots")
            
            tasks = []
            
            # Task 1: Service identification
            service_task = claude_service.identify_service(
                project_config,
                dialogue_history,
                current_message_text,
                message_id
            )
            tasks.append(service_task)
            
            # Task 2: Slot fetching
            slot_task = None
            if intent_result.date_order:
                target_date = parse_date(intent_result.date_order)
                if target_date:
                    slot_task = sheets_service.get_available_slots_async(db, target_date, 1)
            elif intent_result.desire_time0 and intent_result.desire_time1:
                start_time = parse_time(intent_result.desire_time0)
                end_time = parse_time(intent_result.desire_time1)
                if start_time and end_time:
                    context_date = extract_date_from_context(dialogue_history, zip_history)
                    if context_date:
                        target_date = parse_date(context_date)
                        if target_date:
                            slot_task = sheets_service.get_available_slots_async(db, target_date, 1)
                    else:
                        slot_task = sheets_service.get_available_slots_by_time_range_async(
                            db, start_time, end_time, 1
                        )
            
            if slot_task:
                tasks.append(slot_task)
            
            # Task 3: Client bookings
            client_bookings_task = asyncio.to_thread(
                booking_service.get_client_bookings_as_string, client_id
            )
            tasks.append(client_bookings_task)
            
            # Run in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            service_result = results[0] if not isinstance(results[0], Exception) else None
            if isinstance(results[0], Exception):
                error_count += 1
                logger.error(f"Message ID: {message_id} - Service identification error: {results[0]}")
                from telegram.models import ServiceIdentificationResult
                service_result = ServiceIdentificationResult(time_fraction=1, service_name="unknown")
            
            if len(results) > 1 and slot_task:
                slots = results[1] if not isinstance(results[1], Exception) else None
                if slots:
                    available_slots = slots.slots_by_specialist
                    reserved_slots = slots.reserved_slots_by_specialist or {}
                    slots_target_date = slots.target_date
                    logger.info(f"Message ID: {message_id} - Found slots for {len(available_slots)} specialists")
            
            client_bookings_idx = 2 if slot_task else 1
            if len(results) > client_bookings_idx:
                client_bookings = results[client_bookings_idx] if not isinstance(results[client_bookings_idx], Exception) else ""
            else:
                client_bookings = ""
            
            # Recalculate slots if needed
            if service_result and service_result.time_fraction != 1 and available_slots:
                from telegram.utils.slot_calculator import apply_duration_to_all_specialists, apply_reserved_duration_to_all_specialists
                original_available_slots = dict(available_slots)
                available_slots = apply_duration_to_all_specialists(available_slots, service_result.time_fraction)
                if reserved_slots:
                    reserved_slots = apply_reserved_duration_to_all_specialists(
                        reserved_slots, original_available_slots, service_result.time_fraction
                    )
        else:
            logger.info(f"Message ID: {message_id} - Client is chatting, no slots needed")
            client_bookings = await asyncio.to_thread(
                booking_service.get_client_bookings_as_string, client_id
            )
        
        # Check for newbie status
        newbie_check_task = asyncio.create_task(
            sheets_service.check_client_massage_history(client_id)
        )
        
        # Get booking error if any
        booking_error = db.query(BookingError).filter_by(client_id=client_id).first()
        record_error = booking_error.error_message if booking_error else None
        if record_error:
            logger.info(f"Message ID: {message_id} - Found booking error: {record_error}")
            db.delete(booking_error)
            db.commit()
        
        # Get newbie status
        try:
            is_newbie = await newbie_check_task
            newbie_status = 1 if is_newbie else 0
        except Exception as e:
            logger.error(f"Message ID: {message_id} - Failed newbie check: {e}")
            newbie_status = 1
        
        # Step 3: Generate main response
        logger.info(f"Message ID: {message_id} - Generating main AI response")
        main_response = await claude_service.generate_main_response(
            project_config,
            dialogue_history,
            current_message_text,
            current_date,
            day_of_week,
            date_calendar,
            available_slots,
            reserved_slots,
            client_bookings,
            message_id,
            slots_target_date,
            zip_history,
            record_error,
            newbie_status=newbie_status,
            image_url=image_url
        )
        
        # Process booking actions
        booking_result = {"success": False, "message": ""}
        if any([
            main_response.activate_booking,
            main_response.reject_order,
            main_response.change_order,
            main_response.booking_confirmed,
            main_response.booking_declined
        ]):
            logger.info(f"Message ID: {message_id} - Processing booking action")
            booking_result = await booking_service.process_booking_action(
                main_response, client_id, message_id, contact_send_id
            )
        
        # Save booking errors
        if booking_result and not booking_result.get("success"):
            error_msg = booking_result.get("message", "")
            if error_msg and error_msg not in ["", "None", "No booking action required"]:
                existing_error = db.query(BookingError).filter_by(client_id=client_id).first()
                if existing_error:
                    existing_error.error_message = error_msg
                    existing_error.updated_at = datetime.utcnow()
                else:
                    new_error = BookingError(client_id=client_id, error_message=error_msg)
                    db.add(new_error)
                db.commit()
        elif booking_result and booking_result.get("success"):
            db.query(BookingError).filter_by(client_id=client_id).delete()
            db.commit()
        
        # Process feedback
        if main_response.feedback:
            logger.info(f"Message ID: {message_id} - Processing feedback")
            await booking_service._save_feedback(main_response, client_id, message_id)
        
        # Process human consultant request
        if main_response.human_consultant_requested:
            logger.info(f"Message ID: {message_id} - Sending human consultant email")
            email_service = EmailService()
            await email_service.send_human_consultant_request(
                request_type=main_response.human_consultant_requested,
                client_id=client_id,
                client_name=main_response.name,
                phone=main_response.phone,
                last_message=current_message_text,
                message_id=message_id,
                contact_send_id=contact_send_id
            )
        
        # Save dialogue
        save_dialogue_entry(db, project_id, client_id, message_item.original_message, "client", message_id)
        save_dialogue_entry(db, project_id, client_id, main_response.gpt_response, "claude", message_id)
        
        # Mark as completed
        current_status = queue_service.check_if_message_superseded(message_item.id, message_id)
        if not current_status:
            queue_service.update_message_status(message_item.id, MessageStatus.COMPLETED, message_id)
        
        # Prepare response
        final_response = main_response.gpt_response
        if booking_result["success"] and booking_result.get("message") and booking_result["message"] not in [None, "", "None", "No booking action required"]:
            final_response += f"\n\n{booking_result['message']}"
        
        logger.info(f"Message ID: {message_id} - Processing completed successfully")
        
        if error_count > 0:
            return {
                "error": f"Completed with {error_count} errors",
                "error_count": error_count,
                "gpt_response": final_response,
                "pic": main_response.pic or ""
            }
        else:
            return {
                "gpt_response": final_response,
                "pic": main_response.pic or ""
            }
    
    except Exception as e:
        error_count += 1
        logger.error(f"Message ID: {message_id} - Critical error: {e}", exc_info=True)
        
        try:
            queue_service = MessageQueueService(db)
            queue_service.update_message_status(queue_item_id, MessageStatus.CANCELLED, message_id)
        except Exception:
            pass
        
        return {
            "error": f"Critical error: {str(e)}",
            "error_count": error_count,
            "gpt_response": "Виникла критична помилка при обробці повідомлення",
            "pic": ""
        }
    
    finally:
        db.close()

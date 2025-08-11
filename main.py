from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import Dict, Any, Optional
from datetime import datetime, date, time
import asyncio
import json
import logging
import sys
import random
import string
import os

from app.database import get_db, create_tables, SessionLocal
from app.config import settings, ProjectConfig
from app.models import (
    SendPulseMessage, 
    WebhookResponse, 
    ProjectStats,
    MessageStatus
)
from app.services.message_queue import MessageQueueService
from app.services.claude_service import ClaudeService
from app.services.google_sheets import GoogleSheetsService
from app.services.booking_service import BookingService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


def generate_message_id() -> str:
    """Generate a unique 10-character alphanumeric message ID"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))


def load_local_config() -> Dict[str, Any]:
    """Load local configuration from local_config.json"""
    config_file = "local_config.json"
    
    if not os.path.exists(config_file):
        logger.warning(f"Local config file '{config_file}' not found. Using default configuration.")
        return {
            "default": {
                "specialists": ["Арина", "Эдуард", "Инна", "Жанна"],
                "services": {
                    "Чистка лица": 3,
                    "Уход за кожей лица": 3,
                    "Пилинг": 2,
                    "Карбоновый пилинг": 2,
                    "Микродермабразия": 2,
                    "Коагуляция": 1,
                    "Мезотерапия": 2,
                    "Биоревитализация": 2,
                    "Контурная пластика": 3,
                    "Алмазная микродермабразия": 2,
                    "Безинъекционная мезотерапия": 2,
                    "Плазмолифтинг": 3,
                    "Карбоновый пилинг — 900": 2,
                    "BB glow": 4,
                    "УЗ чистка": 3,
                    "Гидропилинг": 2,
                    "RF лифтинг": 2,
                    "Фонофорез": 2,
                    "Смас лифтинг лица": 4,
                    "Чистка лица и уход за лицом": 4,
                    "Пилинг — 600": 2,
                    "Массаж лица": 2,
                    "Пирсинг ушей": 1,
                    "Лечение гипергидроза": 2,
                    "Липолитики": 2,
                    "Нитевой лифтинг": 3,
                    "Коррекция мимических морщин": 2,
                    "Гиалуронидаза": 2,
                    "Увеличение и коррекция губ": 2,
                    "Бланчтерапия": 2,
                    "Склеротерапия": 2,
                    "Миостимуляция тела": 1,
                    "Консультация подолога": 2,
                    "Установка скоб": 1,
                    "Медицинский педикюр": 3,
                    "Лазерное лечение онихомикоза": 2,
                    "Изготовление ортопедических стелек": 3,
                    "Общий массаж": 2,
                    "Массаж спины": 2,
                    "Антицеллюлитный массаж": 3,
                    "Вакуумный": 2,
                    "Стоун терапия": 3,
                    "Шоколадный массаж": 3,
                    "Массаж со скрабом": 2,
                    "Шоколадное обертывание": 2,
                    "Грязевые обертывания": 2,
                    "Лимфодренажный массаж": 3,
                    "Прессотерапия": 2,
                    "Коллагенарий": 1,
                    "Солярий горизонтальный": 1,
                    "Солярий вертикальный": 1,
                    "Турбо солярий": 1,
                    "Коррекция формы бровей": 2,
                    "Окрашивание бровей": 2,
                    "Ламинирование бровей": 3,
                    "Окрашивание ресниц": 1,
                    "Ламинирование ресниц": 3,
                    "Маникюр без покрытия": 2,
                    "Маникюр с покр. гель": 4,
                    "Покрытие гель": 2,
                    "Наращивание, коррекция с маникюром": 5,
                    "Педикюр без покрытия": 3,
                    "Педикюр с покрытием гель": 4,
                    "Чистка пальцев ног": 2,
                    "SPA для ног": 3,
                    "Женская стрижка": 3,
                    "Мужская стрижка": 2,
                    "Детская стрижка": 2,
                    "Окрашивание волос": 8,
                    "Уход за волосами": 4,
                    "Укладка волос": 2,
                    "Прически": 4,
                    "Плетение кос": 2,
                    "Кератиновое насыщение волос": 8,
                    "Наращивание волос 1 прядь": 10
                }
            }
        }
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            logger.info(f"Loaded local configuration from '{config_file}'")
            return config
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing local config file '{config_file}': {e}")
        logger.warning("Using default configuration due to parsing error")
        return load_local_config.__defaults__[0] if hasattr(load_local_config, '__defaults__') else {}
    except Exception as e:
        logger.error(f"Error loading local config file '{config_file}': {e}")
        logger.warning("Using default configuration due to loading error")
        return {}





project_configs = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database
    create_tables()
    
    # Create database session for initialization
    db = SessionLocal()
    try:
        # Load local configuration
        local_config = load_local_config()
        
        # Load project configurations
        default_config = ProjectConfig("default")
        
        # Apply configuration from local_config.json if available
        if "default" in local_config:
            default_project_config = local_config["default"]
            default_config.specialists = default_project_config.get("specialists", ["Арина", "Эдуард", "Инна", "Жанна"])
            default_config.services = default_project_config.get("services", {})
        else:
            logger.warning("No 'default' configuration found in local config, using hardcoded defaults")
            default_config.specialists = ["Арина", "Эдуард", "Инна", "Жанна"]
            default_config.services = {}
        
        project_configs["default"] = default_config
        
        # Load configurations for other projects if they exist in local_config.json
        for project_id, project_data in local_config.items():
            if project_id != "default":
                project_config = ProjectConfig(project_id)
                project_config.specialists = project_data.get("specialists", default_config.specialists)
                project_config.services = project_data.get("services", default_config.services)
                project_configs[project_id] = project_config
                logger.info(f"Loaded configuration for project '{project_id}'")
        
        # Create database record for default project if it doesn't exist
        from app.database import Project
        existing_project = db.query(Project).filter(Project.project_id == "default").first()
        if not existing_project:
            db_project = Project(
                project_id="default",
                name="Default Project",
                configuration=default_config.to_dict(),
                is_active=True
            )
            db.add(db_project)
            db.commit()
            logger.info("Created default project in database")
        else:
            logger.info("Default project already exists in database")
        
    finally:
        db.close()
    
    yield
    
    # Cleanup
    project_configs.clear()


app = FastAPI(
    title="Telegram Bot Backend",
    description="FastAPI backend for SendPulse Telegram bot with AI management",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Telegram Bot Backend is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}


@app.post("/webhook/sendpulse", response_model=WebhookResponse)
async def sendpulse_webhook(
    message: SendPulseMessage,
    db: Session = Depends(get_db)
):
    """
    Main webhook endpoint for SendPulse messages
    Processes incoming messages according to the technical specification
    """
    # Generate unique message ID for tracking
    message_id = generate_message_id()
    client_id = message.tg_id
    
    # Log message receipt with unique ID
    logger.info(f"Message {message.response} get UUID: {message_id}")
    logger.info(f"Message ID: {message_id} - Webhook received: project_id={message.project_id}, client_id={client_id}, count={message.count}, retry={message.retry}")
    logger.debug(f"Message ID: {message_id} - Message content: '{message.response[:200]}...'")
    
    error_count = 0
    
    try:
        # Get project configuration
        project_config = project_configs.get(message.project_id, project_configs.get("default"))
        if not project_config:
            error_count += 1
            logger.error(f"Message ID: {message_id} - Project configuration not found for project_id={message.project_id}")
            return WebhookResponse(
                send_status="FALSE",
                count=f"{error_count}",
                gpt_response="Project configuration not found",
                pic="",
                status="500",
                user_message=message.response
            )
        
        # Ensure project exists in database (create if doesn't exist)
        from app.database import Project
        existing_project = db.query(Project).filter(Project.project_id == message.project_id).first()
        if not existing_project:
            logger.info(f"Message ID: {message_id} - Creating new project in database: {message.project_id}")
            db_project = Project(
                project_id=message.project_id,
                name=f"Project {message.project_id}",
                configuration=project_config.to_dict(),
                is_active=True
            )
            db.add(db_project)
            db.commit()
            logger.info(f"Message ID: {message_id} - Created project {message.project_id} in database")
        
        # Initialize services
        logger.debug(f"Message ID: {message_id} - Initializing queue service for webhook request from client_id={client_id}")
        queue_service = MessageQueueService(db)
        
        # Process incoming message
        logger.info(f"Message ID: {message_id} - Processing incoming message {message.response[:100]} through queue service for client_id={client_id}")
        queue_result = queue_service.process_incoming_message(message, message_id)
        
        if "error" in queue_result:
            error_count += 1
            logger.error(f"Message ID: {message_id} - Queue processing error for client_id={client_id}: {queue_result['error']}")
            return WebhookResponse(
                send_status="FALSE",
                count=f"{error_count}",
                gpt_response=f"Error: {queue_result['error']}",
                pic="",
                status="500",
                user_message=message.response
            )
        
        # Check if this message should be skipped due to retry logic
        if queue_result.get("send_status") == "FALSE":
            logger.info(f"Message ID: {message_id} - Message skipped due to retry logic for client_id={client_id}")
            return WebhookResponse(
                send_status="FALSE",
                count="1",
                gpt_response="Message skipped due to retry logic",
                pic="",
                status="200",
                user_message=message.response
            )
        
        # Process the message directly and wait for response
        logger.info(f"Message ID: {message_id} - Processing message directly for client_id={client_id}")
        response_data = await process_message_async(
            message.project_id,
            client_id,
            queue_result["queue_item_id"],
            message_id
        )
        
        if not response_data:
            error_count += 1
            logger.error(f"Message ID: {message_id} - No response received from processing for client_id={client_id}")
            return WebhookResponse(
                send_status="FALSE",
                count=f"{error_count}",
                gpt_response="Произошла ошибка при обработке сообщения",
                pic="",
                status="200",
                user_message=message.response
            )
        
        # Check for processing errors in response_data
        if response_data.get("error"):
            error_count += response_data.get("error_count", 1)
            logger.error(f"Message ID: {message_id} - Processing errors occurred for client_id={client_id}: {response_data['error']}")
            return WebhookResponse(
                send_status="FALSE",
                count=f"{error_count}",
                gpt_response=response_data.get("gpt_response", "Произошла ошибка при обработке сообщения"),
                pic=response_data.get("pic", ""),
                status="200",
                user_message=message.response
            )
        
        # CRITICAL: Check if this message was superseded during processing
        queue_service = MessageQueueService(db)
        message_was_superseded = queue_service.check_if_message_superseded(queue_result["queue_item_id"], message_id)
        
        if message_was_superseded:
            # This message was superseded by a newer message during processing
            logger.info(f"Message ID: {message_id} - Message {queue_result['queue_item_id']} was superseded during processing for client_id={client_id}, returning send_status=FALSE")
            return WebhookResponse(
                send_status="FALSE",
                count=None,  # No errors, just superseded by newer message
                gpt_response=response_data["gpt_response"],  # Still return the generated response
                pic=response_data.get("pic", ""),
                status="200",
                user_message=message.response
            )
        
        # Check if there are new messages in queue after processing
        has_new_messages = queue_service.has_pending_messages(message.project_id, client_id, message_id)
        
        # Determine send_status and count based on errors and new messages
        if has_new_messages:
            # No errors but new messages arrived during processing
            send_status = "FALSE"
            count = None  # No errors, just new messages
            logger.info(f"Message ID: {message_id} - New messages found in queue for client_id={client_id}, returning send_status=FALSE, count=None")
        else:
            # No errors and no new messages - successful completion
            send_status = "TRUE"
            count = "0"  # Successful completion, no errors
            logger.info(f"Message ID: {message_id} - No new messages in queue for client_id={client_id}, returning send_status=TRUE, count=0")
        
        # Return the final response
        return WebhookResponse(
            send_status=send_status,
            count=count,
            gpt_response=response_data["gpt_response"],
            pic=response_data.get("pic", ""),
            status="200",
            user_message=message.response
        )
        
    except Exception as e:
        error_count += 1
        logger.error(f"Message ID: {message_id} - Webhook error: {e}", exc_info=True)
        return WebhookResponse(
            send_status="FALSE",
            count=f"{error_count}",
            gpt_response="Произошла ошибка при обработке сообщения",
            pic="",
            status="500",
            user_message=message.response
        )


async def process_message_async(project_id: str, client_id: str, queue_item_id: str, message_id: str) -> dict:
    """
    Process message with AI and return response data
    This implements the full processing pipeline from the technical specification
    """
    logger.info(f"Message ID: {message_id} - Starting message processing for project_id={project_id}, client_id={client_id}, queue_item_id={queue_item_id}")
    
    error_count = 0
    
    try:
        # Get new database session for processing
        from app.database import SessionLocal
        db = SessionLocal()
        
        try:
            # Get project configuration
            project_config = project_configs.get(project_id, project_configs.get("default"))
            if not project_config:
                error_count += 1
                logger.error(f"Message ID: {message_id} - Project configuration not found for project_id={project_id}")
                return {
                    "error": "Project configuration not found",
                    "error_count": error_count,
                    "gpt_response": "Произошла ошибка конфигурации проекта",
                    "pic": ""
                }
            
            # Initialize services
            logger.debug(f"Message ID: {message_id} - Initializing services for client_id={client_id}")
            queue_service = MessageQueueService(db)
            claude_service = ClaudeService(db)
            sheets_service = GoogleSheetsService(project_config)
            booking_service = BookingService(db, project_config)
            
            # Get message from queue
            logger.debug(f"Message ID: {message_id} - Getting message from queue for client_id={client_id}")
            message_item = queue_service.get_message_for_processing(project_id, client_id, message_id)
            if not message_item:
                error_count += 1
                logger.warning(f"Message ID: {message_id} - No message found in queue for client_id={client_id}")
                return {
                    "error": "No message found in queue",
                    "error_count": error_count,
                    "gpt_response": "Сообщение не найдено в очереди",
                    "pic": ""
                }
            
            logger.info(f"Message ID: {message_id} - Processing message: '{message_item.aggregated_message[:100]}...' for client_id={client_id}")
            
            # Update message status to processing
            logger.debug(f"Message ID: {message_id} - Updating message status to processing for message_id={message_item.id}")
            queue_service.update_message_status(message_item.id, MessageStatus.PROCESSING, message_id)
            
            # Get dialogue history
            logger.debug(f"Message ID: {message_id} - Getting dialogue history for client_id={client_id}")
            dialogue_history = get_dialogue_history(db, project_id, client_id, message_id)
            
            # Step 1: Intent detection (async)
            logger.info(f"Message ID: {message_id} - Starting intent detection for client_id={client_id}")
            try:
                intent_result = await claude_service.detect_intent(
                    project_config,
                    dialogue_history,
                    message_item.aggregated_message,
                    message_id
                )
                logger.debug(f"Message ID: {message_id} - Intent detection result for client_id={client_id}: waiting={intent_result.waiting}, date_order={intent_result.date_order}")
            except Exception as e:
                error_count += 1
                logger.error(f"Message ID: {message_id} - Error in intent detection for client_id={client_id}: {e}")
                # Continue with default intent
                from app.models import IntentDetectionResult
                intent_result = IntentDetectionResult(waiting=1)
            
            # Steps 2 & 3: Run service identification and slot fetching in parallel when possible
            service_result = None
            available_slots = {}
            reserved_slots = {}
            current_date = date.today()
            
            if not intent_result.waiting:
                # Client is not just chatting - need service info and slots
                logger.info(f"Message ID: {message_id} - Running parallel service identification and slot fetching for client_id={client_id}")
                logger.debug(f"Message ID: {message_id} - Intent result: waiting={intent_result.waiting}, date_order={intent_result.date_order}, desire_time0={intent_result.desire_time0}, desire_time1={intent_result.desire_time1}")
                
                # Prepare tasks that can run in parallel
                tasks = []
                
                # Task 1: Service identification
                service_task = claude_service.identify_service(
                    project_config,
                    dialogue_history,
                    message_item.aggregated_message,
                    message_id
                )
                tasks.append(service_task)
                
                # Task 2: Get slots based on intent (if we have date/time info)
                slot_task = None
                logger.debug(f"Message ID: {message_id} - Checking intent conditions for slot fetching: date_order='{intent_result.date_order}', desire_time0='{intent_result.desire_time0}', desire_time1='{intent_result.desire_time1}'")
                if intent_result.date_order:
                    logger.debug(f"Message ID: {message_id} - Preparing slot fetch for specific date {intent_result.date_order}")
                    target_date = parse_date(intent_result.date_order)
                    if target_date:
                        # Use default time_fraction initially, will adjust after service identification
                        slot_task = sheets_service.get_available_slots_async(db, target_date, 1)
                elif intent_result.desire_time0 and intent_result.desire_time1:
                    logger.debug(f"Message ID: {message_id} - Preparing slot fetch for time range {intent_result.desire_time0}-{intent_result.desire_time1}")
                    start_time = parse_time(intent_result.desire_time0)
                    end_time = parse_time(intent_result.desire_time1)
                    if start_time and end_time:
                        slot_task = sheets_service.get_available_slots_by_time_range_async(
                            db, start_time, end_time, 1
                        )
                
                if slot_task:
                    logger.debug(f"Message ID: {message_id} - Slot task created, will fetch slots")
                else:
                    logger.warning(f"Message ID: {message_id} - No slot task created - intent detection conditions not met for slot fetching")
                
                if slot_task:
                    tasks.append(slot_task)
                
                # Task 3: Get client bookings (can run in parallel)
                client_bookings_task = asyncio.to_thread(booking_service.get_client_bookings_as_string, client_id)
                tasks.append(client_bookings_task)
                
                try:
                    # Run tasks in parallel
                    logger.debug(f"Message ID: {message_id} - Running {len(tasks)} tasks in parallel for client_id={client_id}")
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Process results
                    service_result = results[0] if not isinstance(results[0], Exception) else None
                    if isinstance(results[0], Exception):
                        error_count += 1
                        logger.error(f"Message ID: {message_id} - Error in parallel service identification for client_id={client_id}: {results[0]}")
                        from app.models import ServiceIdentificationResult
                        service_result = ServiceIdentificationResult(time_fraction=1, service_name="unknown")
                    
                    if len(results) > 1 and slot_task:
                        slots = results[1] if not isinstance(results[1], Exception) else None
                        if isinstance(results[1], Exception):
                            error_count += 1
                            logger.error(f"Message ID: {message_id} - Error in parallel slot fetching for client_id={client_id}: {results[1]}")
                        elif slots:
                            available_slots = slots.slots_by_specialist
                            logger.debug(f"Message ID: {message_id} - Found available slots in parallel: {len(available_slots)} specialists")
                    
                    # Get client bookings result
                    client_bookings_idx = 2 if slot_task else 1
                    if len(results) > client_bookings_idx:
                        client_bookings = results[client_bookings_idx] if not isinstance(results[client_bookings_idx], Exception) else ""
                        if isinstance(results[client_bookings_idx], Exception):
                            error_count += 1
                            logger.error(f"Message ID: {message_id} - Error getting client bookings for client_id={client_id}: {results[client_bookings_idx]}")
                            client_bookings = ""
                    else:
                        client_bookings = ""
                    
                    logger.info(f"Message ID: {message_id} - Parallel processing completed for client_id={client_id}")
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"Message ID: {message_id} - Error in parallel processing for client_id={client_id}: {e}")
                    # Fallback to default values
                    from app.models import ServiceIdentificationResult
                    service_result = ServiceIdentificationResult(time_fraction=1, service_name="unknown")
                    client_bookings = ""
                
                # If we need to refetch slots with correct time_fraction after service identification
                if service_result and service_result.time_fraction != 1 and available_slots:
                    logger.debug(f"Message ID: {message_id} - Refetching slots with correct time_fraction={service_result.time_fraction} for client_id={client_id}")
                    try:
                        if intent_result.date_order:
                            target_date = parse_date(intent_result.date_order)
                            if target_date:
                                slots = await sheets_service.get_available_slots_async(db, target_date, service_result.time_fraction)
                                available_slots = slots.slots_by_specialist
                        elif intent_result.desire_time0 and intent_result.desire_time1:
                            start_time = parse_time(intent_result.desire_time0)
                            end_time = parse_time(intent_result.desire_time1)
                            if start_time and end_time:
                                slots = await sheets_service.get_available_slots_by_time_range_async(
                                    db, start_time, end_time, service_result.time_fraction
                                )
                                available_slots = slots.slots_by_specialist
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Message ID: {message_id} - Error refetching slots with correct time_fraction for client_id={client_id}: {e}")
                
            else:
                # Client is just chatting/waiting - only need basic info
                logger.info(f"Message ID: {message_id} - Client is waiting/chatting for client_id={client_id} (waiting={intent_result.waiting}), skipping service identification and slot fetching")
                try:
                    client_bookings = await asyncio.to_thread(booking_service.get_client_bookings_as_string, client_id)
                except Exception as e:
                    error_count += 1
                    logger.error(f"Message ID: {message_id} - Error getting client bookings for client_id={client_id}: {e}")
                    client_bookings = ""
            
            # Step 3: Generate main response (async)
            logger.info(f"Message ID: {message_id} - Generating main response for client_id={client_id}")
            logger.info(f"Message ID: {message_id} - SENDING TO CLAUDE: available_slots={available_slots}, reserved_slots={reserved_slots}")
            try:
                main_response = await claude_service.generate_main_response(
                    project_config,
                    dialogue_history,
                    message_item.aggregated_message,
                    current_date.strftime("%d.%m.%Y"),
                    available_slots,
                    reserved_slots,
                    client_bookings,
                    message_id
                )
                logger.debug(f"Message ID: {message_id} - Main response generated for client_id={client_id}: activate_booking={main_response.activate_booking}, reject_order={main_response.reject_order}, change_order={main_response.change_order}")
            except Exception as e:
                error_count += 1
                logger.error(f"Message ID: {message_id} - Error generating main response for client_id={client_id}: {e}")
                # Return error response
                queue_service.update_message_status(message_item.id, MessageStatus.CANCELLED, message_id)
                return {
                    "error": "Error generating AI response",
                    "error_count": error_count,
                    "gpt_response": "Извините, произошла ошибка при генерации ответа. Попробуйте еще раз.",
                    "pic": ""
                }
            
            # Process booking actions (async)
            booking_result = {"success": False, "message": ""}
            if any([main_response.activate_booking, main_response.reject_order, main_response.change_order]):
                logger.info(f"Message ID: {message_id} - Processing booking action for client_id={client_id}")
                try:
                    booking_result = await booking_service.process_booking_action(main_response, client_id, message_id)
                    logger.info(f"Message ID: {message_id} - Booking action result for client_id={client_id}: success={booking_result['success']}, message={booking_result['message']}")
                except Exception as e:
                    error_count += 1
                    logger.error(f"Message ID: {message_id} - Error processing booking action for client_id={client_id}: {e}")
                    booking_result = {"success": False, "message": "Ошибка при обработке бронирования"}
            else:
                logger.debug(f"Message ID: {message_id} - No booking action required for client_id={client_id}")
            
            # Save dialogue entry
            logger.debug(f"Message ID: {message_id} - Saving dialogue entries for client_id={client_id}")
            try:
                save_dialogue_entry(db, project_id, client_id, message_item.original_message, "client", message_id)
                save_dialogue_entry(db, project_id, client_id, main_response.gpt_response, "claude", message_id)
            except Exception as e:
                error_count += 1
                logger.error(f"Message ID: {message_id} - Error saving dialogue entries for client_id={client_id}: {e}")
                # Continue anyway
            
            # Mark current message as completed (only if not superseded)
            current_status = queue_service.check_if_message_superseded(message_item.id, message_id)
            if not current_status:
                logger.debug(f"Message ID: {message_id} - Updating message status to completed for message_id={message_item.id}")
                queue_service.update_message_status(message_item.id, MessageStatus.COMPLETED, message_id)
            else:
                logger.debug(f"Message ID: {message_id} - Message {message_item.id} was superseded, preserving superseded status")
            
            # Prepare final response
            final_response = main_response.gpt_response
            if booking_result["success"]:
                final_response += f"\n\n{booking_result['message']}"
            elif booking_result["message"]:
                final_response += f"\n\nОшибка: {booking_result['message']}"
            
            logger.info(f"Message ID: {message_id} - Message processing completed for client_id={client_id} with {error_count} errors")
            
            # Return response data for webhook
            if error_count > 0:
                return {
                    "error": f"Processing completed with {error_count} errors",
                    "error_count": error_count,
                    "gpt_response": final_response,
                    "pic": main_response.pic or ""
                }
            else:
                return {
                    "gpt_response": final_response,
                    "pic": main_response.pic or ""
                }
            
        finally:
            db.close()
            logger.debug(f"Message ID: {message_id} - Database session closed for client_id={client_id}")
            
    except Exception as e:
        error_count += 1
        logger.error(f"Message ID: {message_id} - Error processing message for client_id={client_id}: {e}", exc_info=True)
        # Update message status to failed
        try:
            from app.database import SessionLocal
            db = SessionLocal()
            queue_service = MessageQueueService(db)
            logger.debug(f"Message ID: {message_id} - Marking message as cancelled due to error for queue_item_id={queue_item_id}")
            queue_service.update_message_status(queue_item_id, MessageStatus.CANCELLED, message_id)
            db.close()
        except Exception as cleanup_error:
            error_count += 1
            logger.error(f"Message ID: {message_id} - Failed to update message status during error cleanup: {cleanup_error}")
        
        return {
            "error": f"Critical error during processing: {str(e)}",
            "error_count": error_count,
            "gpt_response": "Произошла критическая ошибка при обработке сообщения",
            "pic": ""
        }


def get_dialogue_history(db: Session, project_id: str, client_id: str, message_id: str) -> str:
    """Get dialogue history for a client"""
    from app.database import Dialogue
    from sqlalchemy import desc
    
    logger.debug(f"Message ID: {message_id} - Getting dialogue history for client_id={client_id}, project_id={project_id}")
    
    dialogues = db.query(Dialogue).filter(
        and_(
            Dialogue.project_id == project_id,
            Dialogue.client_id == client_id,
            Dialogue.is_archived.is_(False)
        )
    ).order_by(desc(Dialogue.timestamp)).limit(50).all()
    
    logger.debug(f"Message ID: {message_id} - Found {len(dialogues)} dialogue entries for client_id={client_id}")
    
    history_lines = []
    for dialogue in reversed(dialogues):
        role = "Клиент" if dialogue.role == "client" else "Бот"
        history_lines.append(f"{role}: {dialogue.message}")
    
    history_text = "\n".join(history_lines)
    logger.debug(f"Message ID: {message_id} - Built dialogue history for client_id={client_id}: {len(history_text)} characters")
    
    return history_text


def save_dialogue_entry(db: Session, project_id: str, client_id: str, message: str, role: str, message_id: str):
    """Save a dialogue entry"""
    from app.database import Dialogue
    
    logger.debug(f"Message ID: {message_id} - Saving dialogue entry: client_id={client_id}, role={role}, message_length={len(message)}")
    
    dialogue = Dialogue(
        project_id=project_id,
        client_id=client_id,
        role=role,
        message=message,
        timestamp=datetime.utcnow()
    )
    
    db.add(dialogue)
    db.commit()
    
    logger.debug(f"Message ID: {message_id} - Dialogue entry saved successfully for client_id={client_id}, role={role}")


def parse_date(date_str: str) -> Optional[date]:
    """Parse date string"""
    logger.debug(f"Parsing date string: '{date_str}'")
    try:
        if len(date_str.split('.')) == 2:
            current_year = datetime.now().year
            parsed_date = datetime.strptime(f"{date_str}.{current_year}", "%d.%m.%Y").date()
            logger.debug(f"Successfully parsed date: {parsed_date}")
            return parsed_date
        logger.warning(f"Invalid date format: '{date_str}' (expected DD.MM)")
        return None
    except Exception as e:
        logger.warning(f"Failed to parse date '{date_str}': {e}")
        return None


def parse_time(time_str: str) -> Optional[time]:
    """Parse time string"""
    logger.debug(f"Parsing time string: '{time_str}'")
    try:
        parsed_time = datetime.strptime(time_str, "%H:%M").time()
        logger.debug(f"Successfully parsed time: {parsed_time}")
        return parsed_time
    except Exception as e:
        logger.warning(f"Failed to parse time '{time_str}': {e}")
        return None


@app.get("/projects/{project_id}/stats", response_model=ProjectStats)
async def get_project_stats(project_id: str, db: Session = Depends(get_db)):
    """Get statistics for a project"""
    from app.database import MessageQueue, Booking
    
    total_messages = db.query(MessageQueue).filter(
        MessageQueue.project_id == project_id
    ).count()
    
    total_bookings = db.query(Booking).filter(
        Booking.project_id == project_id
    ).count()
    
    active_bookings = db.query(Booking).filter(
        and_(
            Booking.project_id == project_id,
            Booking.status == "active"
        )
    ).count()
    
    total_clients = db.query(func.count(func.distinct(MessageQueue.client_id))).filter(
        MessageQueue.project_id == project_id
    ).scalar()
    
    return ProjectStats(
        project_id=project_id,
        total_messages=total_messages,
        total_bookings=total_bookings,
        active_bookings=active_bookings,
        total_clients=total_clients
    )


@app.get("/projects/{project_id}/queue")
async def get_queue_stats(project_id: str, db: Session = Depends(get_db)):
    """Get message queue statistics"""
    queue_service = MessageQueueService(db)
    return queue_service.get_queue_stats(project_id)


@app.post("/projects/{project_id}/config")
async def update_project_config(project_id: str, config_data: Dict[str, Any]):
    """Update project configuration"""
    config = ProjectConfig.from_dict(config_data)
    project_configs[project_id] = config
    return {"success": True, "message": "Configuration updated"}


@app.get("/projects/{project_id}/config")
async def get_project_config(project_id: str):
    """Get project configuration"""
    config = project_configs.get(project_id, project_configs.get("default"))
    if not config:
        raise HTTPException(status_code=404, detail="Project not found")
    return config.to_dict()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port) 
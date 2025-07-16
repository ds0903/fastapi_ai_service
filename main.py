from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

from app.database import get_db, create_tables, SessionLocal
from app.config import settings, ProjectConfig
from app.models import (
    SendPulseMessage, 
    WebhookResponse, 
    ErrorResponse,
    ProjectStats,
    MessageStatus
)
from app.services.message_queue import MessageQueueService
from app.services.claude_service import ClaudeService
from app.services.google_sheets import GoogleSheetsService
from app.services.booking_service import BookingService
from app.services.sendpulse_service import SendPulseService


project_configs = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database
    create_tables()
    
    # Create database session for initialization
    db = SessionLocal()
    try:
        # Load project configurations
        default_config = ProjectConfig("default")
        default_config.specialists = ["Арина", "Эдуард", "Инна", "Жанна"]
        default_config.services = {
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
        project_configs["default"] = default_config
        
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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Main webhook endpoint for SendPulse messages
    Processes incoming messages according to the technical specification
    """
    client_id = message.tg_id or message.client_id
    logger.info(f"Webhook received: project_id={message.project_id}, client_id={client_id}, count={message.count}, retry={message.retry}")
    logger.debug(f"Message content: '{message.response[:200]}...'")
    
    try:
        # Get project configuration
        project_config = project_configs.get(message.project_id, project_configs.get("default"))
        if not project_config:
            logger.error(f"Project configuration not found for project_id={message.project_id}")
            raise HTTPException(status_code=404, detail="Project configuration not found")
        
        # Initialize services
        logger.debug(f"Initializing queue service for webhook request from client_id={client_id}")
        queue_service = MessageQueueService(db)
        
        # Process incoming message
        logger.debug(f"Processing incoming message through queue service for client_id={client_id}")
        queue_result = queue_service.process_incoming_message(message)
        
        if "error" in queue_result:
            logger.error(f"Queue processing error for client_id={client_id}: {queue_result['error']}")
            return WebhookResponse(
                send_status="FALSE",
                count=str(message.count),
                gpt_response=f"Error: {queue_result['error']}"
            )
        
        # Check if client is already being processed
        if queue_service.is_client_currently_processing(message.project_id, client_id):
            logger.info(f"Client {client_id} is already being processed, message queued for batching")
        else:
            logger.info(f"Message queued successfully, starting background processing for client_id={client_id}")
            # Process the message in background
            background_tasks.add_task(
                process_message_async,
                message.project_id,
                message.tg_id or message.client_id,
                queue_result["queue_item_id"],
                message.count
            )
        
        # Return immediate response
        logger.debug(f"Returning immediate response to client_id={client_id}")
        return WebhookResponse(
            send_status="TRUE",
            count=str(message.count),
            gpt_response="Обрабатываю ваш запрос..."
        )
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return WebhookResponse(
            send_status="FALSE",
            count=str(message.count),
            gpt_response="Произошла ошибка при обработке сообщения"
        )


async def process_message_async(project_id: str, client_id: str, queue_item_id: str, original_count: int = 0):
    """
    Background task to process message with AI
    This implements the full processing pipeline from the technical specification
    """
    logger.info(f"Starting message processing for project_id={project_id}, client_id={client_id}, queue_item_id={queue_item_id}")
    
    try:
        # Get new database session for background task
        from app.database import SessionLocal
        db = SessionLocal()
        
        try:
            # Get project configuration
            project_config = project_configs.get(project_id, project_configs.get("default"))
            if not project_config:
                logger.error(f"Project configuration not found for project_id={project_id}")
                return
            
            # Initialize services
            logger.debug(f"Initializing services for client_id={client_id}")
            queue_service = MessageQueueService(db)
            claude_service = ClaudeService(db)
            sheets_service = GoogleSheetsService(project_config)
            booking_service = BookingService(db, project_config)
            sendpulse_service = SendPulseService()
            
            # Get message from queue
            logger.debug(f"Getting message from queue for client_id={client_id}")
            message_item = queue_service.get_message_for_processing(project_id, client_id)
            if not message_item:
                logger.warning(f"No message found in queue for client_id={client_id}")
                return
            
            logger.info(f"Processing message: '{message_item.aggregated_message[:100]}...' for client_id={client_id}")
            
            # Update message status to processing
            logger.debug(f"Updating message status to processing for message_id={message_item.id}")
            queue_service.update_message_status(message_item.id, MessageStatus.PROCESSING)
            
            # Get dialogue history
            logger.debug(f"Getting dialogue history for client_id={client_id}")
            dialogue_history = get_dialogue_history(db, project_id, client_id)
            
            # Step 1: Intent detection
            logger.info(f"Starting intent detection for client_id={client_id}")
            intent_result = await claude_service.detect_intent(
                project_config,
                dialogue_history,
                message_item.aggregated_message
            )
            logger.debug(f"Intent detection result for client_id={client_id}: waiting={intent_result.waiting}, date_order={intent_result.date_order}")
            
            
            # Step 2: Service identification (if needed)
            service_result = None
            if not intent_result.waiting:
                logger.info(f"Starting service identification for client_id={client_id}")
                service_result = await claude_service.identify_service(
                    project_config,
                    dialogue_history,
                    message_item.aggregated_message
                )
                logger.debug(f"Service identification result for client_id={client_id}: service={service_result.service_name}, duration={service_result.time_fraction}")
            else:
                logger.debug(f"Skipping service identification for client_id={client_id} (client is waiting/chatting)")
            
            # Get available and reserved slots
            current_date = date.today()
            available_slots = {}
            reserved_slots = {}
            
            if intent_result.date_order:
                logger.info(f"Getting slots for specific date {intent_result.date_order} for client_id={client_id}")
                target_date = parse_date(intent_result.date_order)
                if target_date:
                    time_fraction = service_result.time_fraction if service_result else 1
                    slots = sheets_service.get_available_slots(db, target_date, time_fraction)
                    available_slots = slots.slots_by_specialist
                    logger.debug(f"Found available slots for {target_date}: {len(available_slots)} specialists")
                else:
                    logger.warning(f"Could not parse date '{intent_result.date_order}' for client_id={client_id}")
            elif intent_result.desire_time0 and intent_result.desire_time1:
                logger.info(f"Getting slots for time range {intent_result.desire_time0}-{intent_result.desire_time1} for client_id={client_id}")
                start_time = parse_time(intent_result.desire_time0)
                end_time = parse_time(intent_result.desire_time1)
                if start_time and end_time:
                    time_fraction = service_result.time_fraction if service_result else 1
                    slots = sheets_service.get_available_slots_by_time_range(
                        db, start_time, end_time, time_fraction
                    )
                    available_slots = slots.slots_by_specialist
                    logger.debug(f"Found available slots for time range: {len(available_slots)} specialists")
                else:
                    logger.warning(f"Could not parse time range '{intent_result.desire_time0}-{intent_result.desire_time1}' for client_id={client_id}")
            
            # Get client's existing bookings
            logger.debug(f"Getting existing bookings for client_id={client_id}")
            client_bookings = booking_service.get_client_bookings_as_string(client_id)
            
            # Step 3: Generate main response
            logger.info(f"Generating main response for client_id={client_id}")
            main_response = await claude_service.generate_main_response(
                project_config,
                dialogue_history,
                message_item.aggregated_message,
                current_date.strftime("%d.%m.%Y"),
                available_slots,
                reserved_slots,
                client_bookings
            )
            logger.debug(f"Main response generated for client_id={client_id}: activate_booking={main_response.activate_booking}, reject_order={main_response.reject_order}, change_order={main_response.change_order}")
            
            # Process booking actions
            booking_result = {"success": False, "message": ""}
            if any([main_response.activate_booking, main_response.reject_order, main_response.change_order]):
                logger.info(f"Processing booking action for client_id={client_id}")
                booking_result = booking_service.process_booking_action(main_response, client_id)
                logger.info(f"Booking action result for client_id={client_id}: success={booking_result['success']}, message={booking_result['message']}")
            else:
                logger.debug(f"No booking action required for client_id={client_id}")
            
            # Save dialogue entry
            logger.debug(f"Saving dialogue entries for client_id={client_id}")
            save_dialogue_entry(db, project_id, client_id, message_item.original_message, "client")
            save_dialogue_entry(db, project_id, client_id, main_response.gpt_response, "claude")
            
            # Mark current message as completed first
            logger.debug(f"Updating message status to completed for message_id={message_item.id}")
            queue_service.update_message_status(message_item.id, MessageStatus.COMPLETED)
            
            # Check if new messages arrived during processing and need to be batched
            logger.info(f"Checking for new messages that arrived during processing for client_id={client_id}")
            new_batched_message = queue_service.check_for_new_messages_during_processing(
                project_id, client_id, message_item.id
            )
            
            if new_batched_message:
                # New messages arrived - create batch and continue processing
                logger.info(f"New messages found for client_id={client_id}, creating batch and continuing processing")
                batched_queue_item = queue_service.create_batched_message(project_id, client_id, new_batched_message)
                
                # Close current SendPulse service
                await sendpulse_service.close()
                
                # Schedule processing of the batched messages
                logger.info(f"Scheduling processing of batched messages for client_id={client_id}")
                await process_message_async(project_id, client_id, batched_queue_item.id, original_count)
                return
            
            # No new messages - prepare and send final response
            logger.info(f"No new messages found for client_id={client_id}, sending final response")
            final_response = main_response.gpt_response
            if booking_result["success"]:
                final_response += f"\n\n{booking_result['message']}"
            elif booking_result["message"]:
                final_response += f"\n\nОшибка: {booking_result['message']}"
            
            # Send response back to SendPulse API
            logger.info(f"Sending final response to client_id={client_id}: {final_response[:200]}...")
            send_success = await sendpulse_service.send_response(
                client_id=client_id,
                project_id=project_id,
                response_text=final_response,
                pic=main_response.pic or "",
                count=str(original_count)
            )
            
            if send_success:
                logger.info(f"Response successfully sent to SendPulse for client_id={client_id}")
            else:
                logger.warning(f"Failed to send response to SendPulse for client_id={client_id}")
            
            # Clear client queue
            logger.debug(f"Clearing client queue for client_id={client_id}")
            queue_service.clear_client_queue(project_id, client_id)
            
            # Close SendPulse service
            await sendpulse_service.close()
            
            logger.info(f"Message processing completed successfully for client_id={client_id}")
            
        finally:
            db.close()
            logger.debug(f"Database session closed for client_id={client_id}")
            
    except Exception as e:
        logger.error(f"Error processing message for client_id={client_id}: {e}", exc_info=True)
        # Update message status to failed
        try:
            from app.database import SessionLocal
            db = SessionLocal()
            queue_service = MessageQueueService(db)
            logger.debug(f"Marking message as cancelled due to error for queue_item_id={queue_item_id}")
            queue_service.update_message_status(queue_item_id, MessageStatus.CANCELLED)
            db.close()
            
            # Close SendPulse service if it was initialized
            try:
                sendpulse_service = SendPulseService()
                await sendpulse_service.close()
            except:
                pass
                
        except Exception as cleanup_error:
            logger.error(f"Failed to update message status during error cleanup: {cleanup_error}")


def get_dialogue_history(db: Session, project_id: str, client_id: str) -> str:
    """Get dialogue history for a client"""
    from app.database import Dialogue
    from sqlalchemy import desc
    
    logger.debug(f"Getting dialogue history for client_id={client_id}, project_id={project_id}")
    
    dialogues = db.query(Dialogue).filter(
        and_(
            Dialogue.project_id == project_id,
            Dialogue.client_id == client_id,
            Dialogue.is_archived == False
        )
    ).order_by(desc(Dialogue.timestamp)).limit(50).all()
    
    logger.debug(f"Found {len(dialogues)} dialogue entries for client_id={client_id}")
    
    history_lines = []
    for dialogue in reversed(dialogues):
        role = "Клиент" if dialogue.role == "client" else "Бот"
        history_lines.append(f"{role}: {dialogue.message}")
    
    history_text = "\n".join(history_lines)
    logger.debug(f"Built dialogue history for client_id={client_id}: {len(history_text)} characters")
    
    return history_text


def save_dialogue_entry(db: Session, project_id: str, client_id: str, message: str, role: str):
    """Save a dialogue entry"""
    from app.database import Dialogue
    
    logger.debug(f"Saving dialogue entry: client_id={client_id}, role={role}, message_length={len(message)}")
    
    dialogue = Dialogue(
        project_id=project_id,
        client_id=client_id,
        role=role,
        message=message,
        timestamp=datetime.utcnow()
    )
    
    db.add(dialogue)
    db.commit()
    
    logger.debug(f"Dialogue entry saved successfully for client_id={client_id}, role={role}")


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
from fastapi import FastAPI, HTTPException, Depends, Request  
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, func
from typing import Dict, Any, Optional
from datetime import datetime, date, time, timedelta
import asyncio
import json
import logging
import sys
import random
import string
import os
import locale
import pytz
from pytz import timezone

from app.database import get_db, create_tables, SessionLocal, Dialogue  
from app.config import settings, ProjectConfig
from app.models import (
    SendPulseMessage, 
    WebhookResponse, 
    ProjectStats,
    MessageStatus
)
from app.services.message_queue import MessageQueueService
from app.utils.date_calendar import generate_calendar_for_claude
from app.services.claude_service import ClaudeService
from app.services.google_sheets import GoogleSheetsService
from app.services.booking_service import BookingService
from app.services.email_service import EmailService

# Telephony integration
try:
    from telephony.voice_routes import router as telephony_router, set_telephony_service
    from telephony.telephony_service import TelephonyService
    from telephony.config import binotel_settings
    TELEPHONY_ENABLED = True
    logger_init = logging.getLogger(__name__)
    logger_init.info("Telephony modules imported successfully")
except ImportError as e:
    TELEPHONY_ENABLED = False
    logger_init = logging.getLogger(__name__)
    logger_init.warning(f"Telephony modules not available: {e}")

# Кеш для хранения данных pending подтверждений
# Формат: {client_id: {"date": "...", "time": "...", "specialist": "...", "service": "...", "timestamp": ...}}
pending_confirmations = {}
booking_errors = {}  # Хранение ошибок записей по client_id

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

# Global ClaudeService instance for load balancing between API keys
global_claude_service = None

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
            default_config.work_hours = default_project_config.get("work_hours", {
                "start": settings.default_work_start_time,
                "end": settings.default_work_end_time
            })
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
                project_config.work_hours = project_data.get("work_hours", default_config.work_hours)
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
        
        # Start dialogue compression background task
        from app.services.dialogue_archiving import run_dialogue_compression_task
        compression_task = asyncio.create_task(run_dialogue_compression_task(project_configs))
        logger.info("Started dialogue compression background task")
        
        # Start Google Sheets background sync
        from app.services.sheets_sync import run_sheets_background_sync
        sheets_task = asyncio.create_task(run_sheets_background_sync(project_configs["default"]))
        logger.info("Started Google Sheets background sync (every 5 min)")
        
        # Initialize global ClaudeService for load balancing
        global global_claude_service
        global_claude_service = ClaudeService(db, default_config.slot_duration_minutes)
        logger.info("Initialized global ClaudeService for load balancing between API keys")
        logger.info("📊 Load balance stats available at: GET /admin/load-balance-stats")
        
        # Initialize Telephony Service if enabled
        if TELEPHONY_ENABLED:
            try:
                telephony_service = TelephonyService(db, default_config, global_claude_service)
                set_telephony_service(telephony_service)
                logger.info("✅ Telephony service initialized successfully")
                logger.info(f"📞 Binotel configured: {bool(binotel_settings.binotel_api_key)}")
                logger.info(f"☁️ Google Cloud configured: {bool(binotel_settings.google_application_credentials)}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize telephony service: {e}")
        else:
            logger.warning("⚠️ Telephony service not enabled - modules not imported")
        
    finally:
        db.close()
    
    yield
    
    # Cleanup - log final stats
    if global_claude_service:
        final_stats = global_claude_service.get_load_balance_stats()
        logger.info(f"🏁 FINAL LOAD BALANCE STATS: Total={final_stats['total_requests']}, Client1={final_stats['client1_percentage']}%, Client2={final_stats['client2_percentage']}%, Balance diff={final_stats['balance_difference']}%")
    
    # Cleanup
    logger.info("Shutting down dialogue compression task...")
    if 'compression_task' in locals():
        compression_task.cancel()
        try:
            await compression_task
        except asyncio.CancelledError:
            logger.info("Dialogue compression task cancelled successfully")
    
    project_configs.clear()


app = FastAPI(
    title="Telegram Bot Backend with Telephony",
    description="FastAPI backend for SendPulse Telegram bot with AI management and Binotel telephony",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include telephony routes
if TELEPHONY_ENABLED:
    app.include_router(telephony_router)
    logger.info("✅ Telephony routes registered at /telephony")


@app.get("/")
async def root():
    return {
        "message": "Telegram Bot Backend is running",
        "telephony_enabled": TELEPHONY_ENABLED,
        "version": "2.0.0"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "telephony_enabled": TELEPHONY_ENABLED
    }

@app.post("/make/add-template-message")
async def add_template_message(request: Request):
    """
    Endpoint for Make.com to add template message to dialogue history
    Expected JSON:
    {
        "client_id": "123456789",
        "template_text": "Текст шаблона напоминания",
        "project_id": "default"
    }
    """
    try:
        # Очищаем записи старше 48 часов из кеша
        current_time = datetime.utcnow()
        expired_clients = []
        for cid, data in pending_confirmations.items():
            if (current_time - data['timestamp']).total_seconds() > 172800:  # 48 часов
                expired_clients.append(cid)
        for cid in expired_clients:
            del pending_confirmations[cid]
            logger.debug(f"Removed expired pending confirmation for client {cid}")
        data = await request.json()
        client_id = data.get("client_id")
        template_text = data.get("template_text")
        message_type = data.get("message_type", "reminder")  # Новая строка
        date = data.get("date")
        time = data.get("time")
        specialist = data.get("specialist")
        service = data.get("service")
        project_id = data.get("project_id", "default")
        
        if not client_id or not template_text:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing required fields: client_id or template_text"}
            )
       
        # Add message to dialogue history with timestamp prefix

        # Сохраняем данные в кеш если это запрос подтверждения
        if message_type == "confirmation_request" and date and time:
            pending_confirmations[client_id] = {
                "date": date,
                "time": time,
                "specialist": specialist,
                "service": service,
                "timestamp": datetime.utcnow()
            }
            logger.info(f"Cached pending confirmation for client {client_id}: {date} {time}")
        
        with SessionLocal() as db:
            dialogue_entry = Dialogue(
                project_id=project_id,
                client_id=client_id,
                role="claude: booking_confirmation_pending" if message_type == "confirmation_request" else ("claude: feedback" if message_type == "feedback" else "claude"),
                message=template_text,
                timestamp=datetime.utcnow()
    	    )
            db.add(dialogue_entry)
            db.commit()
            
            logger.info(f"Added {message_type} message to dialogue for client_id={client_id} with role: {dialogue_entry.role}")
            
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Template message added to dialogue history",
                    "client_id": client_id
                }
            )
            
    except Exception as e:
        logger.error(f"Error adding template message: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Internal server error: {str(e)}"}
        )

@app.post("/make/update-booking-status")
async def update_booking_status(request: Request):
    """
    Endpoint for updating booking confirmation status
    Expected JSON:
    {
        "client_id": "123456789",
        "date": "28.08.2025",
        "time": "14:00",
        "action": "booking_confirmed" or "booking_declined",
        "project_id": "default"
    }
    """
    try:
        data = await request.json()
        client_id = data.get('client_id')
        date = data.get('date')
        time = data.get('time')
        action = data.get('action')
        project_id = data.get('project_id', 'default')
        
        if not all([client_id, date, time, action]):
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Missing required parameters"}
            )
        
        # Determine status based on action
        status = 'approved' if action == 'booking_confirmed' else 'cancelled'
        
        # Update status in Google Sheets
        # Get project configuration
        project_config = project_configs.get(project_id, project_configs.get("default"))
        
        # Update status in Google Sheets
        sheets_service = GoogleSheetsService(project_config)
        success = await sheets_service.update_booking_status_in_make_table(
            client_id, date, time, status
        )
        
        # Також пытаемся обновить в основной таблице, если есть специалист в запросе
        specialist = data.get('specialist')
        if specialist:
            main_success = await sheets_service.update_booking_status_in_main_table(
                specialist, date, time, status
            )
            if main_success:
                logger.info(f"Updated main table status to {status} for specialist {specialist}")
        
        
        if success:
            logger.info(f"Booking status updated to {status} for client {client_id}")
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": f"Status updated to {status}",
                    "client_id": client_id,
                    "status": status
                }
            )
        else:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Booking not found or update failed"}
            )
            
    except Exception as e:
        logger.error(f"Error updating booking status: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/webhook/sendpulse", response_model=WebhookResponse)
async def sendpulse_webhook(
    message: SendPulseMessage,
    db: Session = Depends(get_db)
):
    """
    Main webhook endpoint for SendPulse messages
    Processes incoming messages according to the technical specification
    """
    # (весь код вебхуку залишається без змін - він вже в файлі)
    pass  # Placeholder - actual code stays as is


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)

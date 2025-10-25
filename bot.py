"""
Main bot file - aiogram polling mode
Run this file to start the bot: python bot.py
"""
import asyncio
import logging
import sys
from datetime import datetime
from typing import Dict, Any

# Configure logging FIRST
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Application imports
from telegram.config import settings, ProjectConfig
from telegram.database import create_tables, SessionLocal

# Global project configs (MUST BE INITIALIZED BEFORE HANDLER IMPORTS!)
project_configs: Dict[str, ProjectConfig] = {}

# Global ClaudeService instance
global_claude_service = None


def load_local_config() -> Dict[str, Any]:
    """Load local configuration from local_config.json"""
    import json
    import os
    
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
                }
            }
        }
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            logger.info(f"Loaded local configuration from '{config_file}'")
            return config
    except Exception as e:
        logger.error(f"Error loading local config: {e}")
        return {}


async def setup_bot() -> None:
    """Setup bot configuration and database"""
    global global_claude_service, project_configs
    
    logger.info("🚀 Setting up bot...")
    
    # Create database tables
    create_tables()
    logger.info("✅ Database tables created/verified")
    
    # Load local configuration
    local_config = load_local_config()
    
    # Setup default project config
    default_config = ProjectConfig("default")
    
    if "default" in local_config:
        default_project_config = local_config["default"]
        default_config.specialists = default_project_config.get("specialists", ["Арина", "Эдуард", "Инна", "Жанна"])
        default_config.services = default_project_config.get("services", {})
        default_config.work_hours = default_project_config.get("work_hours", {
            "start": settings.default_work_start_time,
            "end": settings.default_work_end_time
        })
    
    project_configs["default"] = default_config
    logger.info(f"✅ Loaded configuration for project 'default'")
    logger.info(f"   Specialists: {default_config.specialists}")
    logger.info(f"   Services: {len(default_config.services)} services configured")
    
    # Create database record for default project
    db = SessionLocal()
    try:
        from telegram.database import Project
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
            logger.info("✅ Created default project in database")
        else:
            logger.info("✅ Default project exists in database")
    finally:
        db.close()
    
    # Initialize global ClaudeService
    from telegram.services.claude_service import ClaudeService
    db = SessionLocal()
    try:
        global_claude_service = ClaudeService(db, default_config.slot_duration_minutes)
        logger.info("✅ Initialized global ClaudeService")
    finally:
        db.close()
    
    # Start background tasks
    logger.info("🔄 Starting background tasks...")
    
    # Dialogue compression
    from telegram.services.dialogue_archiving import run_dialogue_compression_task
    asyncio.create_task(run_dialogue_compression_task(project_configs))
    logger.info("✅ Started dialogue compression task")
    
    # Google Sheets sync
    from telegram.services.sheets_sync import run_sheets_background_sync
    asyncio.create_task(run_sheets_background_sync(project_configs["default"]))
    logger.info("✅ Started Google Sheets sync task")
    
    logger.info("✅ Bot setup completed!")


async def main():
    """Main bot entry point"""
    logger.info("=" * 60)
    logger.info("🤖 Starting Telegram Bot (aiogram + polling)")
    logger.info("=" * 60)
    
    # Check bot token
    if not settings.telegram_bot_token:
        logger.error("❌ TELEGRAM_BOT_TOKEN is not set in .env file!")
        logger.error("Please add TELEGRAM_BOT_TOKEN=your_token_here to .env")
        sys.exit(1)
    
    logger.info(f"✅ Bot token loaded: {settings.telegram_bot_token[:10]}...")
    
    # Setup bot configuration FIRST
    await setup_bot()
    
    # NOW import handlers (after project_configs is initialized)
    from telegram.handlers import start_router, messages_router
    from telegram.handlers.messages import init_handler
    from telegram.middlewares import LoggingMiddleware
    
    # Initialize message handler with project configs
    init_handler(project_configs, global_claude_service)
    
    # Initialize bot and dispatcher
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()
    
    # Register middlewares
    dp.update.middleware(LoggingMiddleware())
    logger.info("✅ Registered logging middleware")
    
    # Register routers
    dp.include_router(start_router)
    dp.include_router(messages_router)
    logger.info("✅ Registered message handlers")
    
    # Start polling
    logger.info("=" * 60)
    logger.info("✅ Bot is running! Press Ctrl+C to stop.")
    logger.info("=" * 60)
    
    try:
        # Delete webhook
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook deleted, starting polling...")
        
        # Start polling
        await dp.start_polling(bot)
    
    except Exception as e:
        logger.error(f"❌ Error running bot: {e}", exc_info=True)
    
    finally:
        await bot.session.close()
        logger.info("✅ Bot stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("✅ Bot stopped by user")

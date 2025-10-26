"""
Telegram webhook handler for FastAPI
"""
from fastapi import APIRouter, Request, HTTPException
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import logging

from app.config import settings
from telegram.handlers.messages import router as messages_router, init_handler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/app", tags=["app"])

# Global bot and dispatcher instances
_bot = None
_dp = None
_project_configs = None
_global_claude_service = None


async def init_telegram_webhook_handler(project_configs, claude_service):
    """Initialize Telegram webhook handler"""
    global _bot, _dp, _project_configs, _global_claude_service
    
    if not settings.telegram_bot_token:
        logger.warning("⚠️ Telegram bot token not configured, skipping webhook initialization")
        return
    
    _project_configs = project_configs
    _global_claude_service = claude_service
    
    try:
        # Initialize bot
        _bot = Bot(
            token=settings.telegram_bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        # Initialize dispatcher
        _dp = Dispatcher()
        
        # Initialize message handler
        init_handler(project_configs, claude_service)
        
        # Include routers
        _dp.include_router(messages_router)
        
        # Set webhook if webhook mode is enabled
        if settings.telegram_mode == "webhook" and settings.telegram_webhook_url:
            webhook_url = f"{settings.telegram_webhook_url}/app/webhook"
            await _bot.set_webhook(
                url=webhook_url,
                drop_pending_updates=True
            )
            logger.info(f"✅ Telegram webhook set to: {webhook_url}")
        else:
            logger.info("ℹ️ Telegram webhook mode not enabled, use polling instead")
        
        logger.info("✅ Telegram webhook handler initialized successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize Telegram webhook handler: {e}")
        raise


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Telegram webhook endpoint
    Receives updates from Telegram and processes them through aiogram
    """
    if not _bot or not _dp:
        raise HTTPException(status_code=503, detail="Telegram bot not initialized")
    
    try:
        # Get update data
        update_dict = await request.json()
        
        # Create Update object
        update = Update(**update_dict)
        
        logger.debug(f"📨 Received Telegram update: {update.update_id}")
        
        # Process update through dispatcher
        await _dp.feed_update(_bot, update)
        
        return {"ok": True}
        
    except Exception as e:
        logger.error(f"❌ Error processing Telegram webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/webhook/info")
async def webhook_info():
    """Get current webhook information"""
    if not _bot:
        raise HTTPException(status_code=503, detail="Telegram bot not initialized")
    
    try:
        webhook_info = await _bot.get_webhook_info()
        return {
            "url": webhook_info.url,
            "has_custom_certificate": webhook_info.has_custom_certificate,
            "pending_update_count": webhook_info.pending_update_count,
            "last_error_date": webhook_info.last_error_date,
            "last_error_message": webhook_info.last_error_message,
            "max_connections": webhook_info.max_connections,
            "allowed_updates": webhook_info.allowed_updates
        }
    except Exception as e:
        logger.error(f"❌ Error getting webhook info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook/set")
async def set_webhook(webhook_url: str = None):
    """Manually set or update webhook URL"""
    if not _bot:
        raise HTTPException(status_code=503, detail="Telegram bot not initialized")
    
    try:
        url = webhook_url or f"{settings.telegram_webhook_url}/app/webhook"
        await _bot.set_webhook(url=url, drop_pending_updates=True)
        logger.info(f"✅ Webhook updated to: {url}")
        return {"ok": True, "url": url}
    except Exception as e:
        logger.error(f"❌ Error setting webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/webhook")
async def delete_webhook():
    """Delete current webhook (switch to polling mode)"""
    if not _bot:
        raise HTTPException(status_code=503, detail="Telegram bot not initialized")
    
    try:
        await _bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook deleted")
        return {"ok": True, "message": "Webhook deleted"}
    except Exception as e:
        logger.error(f"❌ Error deleting webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

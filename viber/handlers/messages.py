"""
Viber Bot Handler - Viber Bot API
"""
from fastapi import APIRouter, Request
import logging
import json
from datetime import datetime
import httpx
import os

from telegram.database import SessionLocal
from telegram.services.message_queue import MessageQueueService
from telegram.models import SendPulseMessage
from telegram.bot_processor import process_message_async

logger = logging.getLogger(__name__)
router = APIRouter()

project_configs = None
global_claude_service = None


def init_viber_handler(configs, claude_service):
    global project_configs, global_claude_service
    project_configs = configs
    global_claude_service = claude_service
    logger.info("✅ Viber handler initialized")


def generate_message_id() -> str:
    import random, string
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))


async def send_viber_message(user_id: str, message: str, bot_token: str):
    """Відправка текстового повідомлення"""
    url = "https://chatapi.viber.com/pa/send_message"
    
    headers = {
        "X-Viber-Auth-Token": bot_token,
        "Content-Type": "application/json"
    }
    
    data = {
        "receiver": user_id,
        "type": "text",
        "text": message,
        "sender": {"name": os.getenv("VIBER_BOT_NAME", "Бот")}
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        result = response.json()
        
        if result.get("status") != 0:
            logger.error(f"Viber API error: {result}")
        
        return result


async def send_viber_picture(user_id: str, image_url: str, text: str, bot_token: str):
    """Відправка зображення"""
    url = "https://chatapi.viber.com/pa/send_message"
    
    headers = {
        "X-Viber-Auth-Token": bot_token,
        "Content-Type": "application/json"
    }
    
    data = {
        "receiver": user_id,
        "type": "picture",
        "text": text,
        "media": image_url,
        "sender": {"name": os.getenv("VIBER_BOT_NAME", "Бот")}
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        result = response.json()
        
        if result.get("status") != 0:
            logger.error(f"Viber picture error: {result}")
        
        return result


@router.post("/viber/webhook")
async def viber_webhook(request: Request):
    """Обробка повідомлень Viber"""
    try:
        body = await request.json()
        logger.info(f"💬 Viber: {json.dumps(body, indent=2)}")
        
        event_type = body.get("event")
        
        if event_type == "webhook":
            logger.info("✅ Viber webhook set")
            return {"status": 0, "status_message": "ok"}
        
        elif event_type == "conversation_started":
            user = body.get("user", {})
            user_id = user.get("id")
            user_name = user.get("name", "")
            
            logger.info(f"👋 Viber conversation started: {user_name} ({user_id})")
            
            return {
                "status": 0,
                "status_message": "ok",
                "type": "text",
                "text": "Вітаю! Чим можу допомогти?"
            }
        
        elif event_type == "message":
            sender = body.get("sender", {})
            user_id = sender.get("id")
            user_name = sender.get("name", "")
            
            message = body.get("message", {})
            message_type = message.get("type")
            
            if message_type == "text":
                text = message.get("text", "")
                logger.info(f"📨 Viber from {user_name}: {text[:100]}")
                
                await process_viber_message(user_id, user_name, text)
            
            elif message_type == "picture":
                media_url = message.get("media")
                text = message.get("text", "")
                full_text = f"{text} {media_url}".strip()
                
                await process_viber_message(user_id, user_name, full_text)
            
            return {"status": 0, "status_message": "ok"}
        
        elif event_type == "subscribed":
            user = body.get("user", {})
            user_id = user.get("id")
            logger.info(f"➕ Viber subscribed: {user_id}")
            return {"status": 0, "status_message": "ok"}
        
        elif event_type == "unsubscribed":
            user_id = body.get("user_id")
            logger.info(f"➖ Viber unsubscribed: {user_id}")
            return {"status": 0, "status_message": "ok"}
        
        elif event_type in ["delivered", "seen"]:
            return {"status": 0, "status_message": "ok"}
        
        else:
            logger.warning(f"⚠️ Unknown Viber event: {event_type}")
            return {"status": 0, "status_message": "ok"}
    
    except Exception as e:
        logger.error(f"❌ Viber error: {e}", exc_info=True)
        return {"status": 1, "status_message": str(e)}


async def process_viber_message(user_id: str, user_name: str, text: str):
    """Обробка через bot_processor"""
    db = SessionLocal()
    
    try:
        message_data = SendPulseMessage(
            date=datetime.now().strftime("%d.%m.%Y %H:%M"),
            response=text,
            project_id="default",
            tg_id=user_id,
            contact_send_id=user_id,
            count=0,
            retry=False
        )
        
        message_id = generate_message_id()
        logger.info(f"📝 Message ID: {message_id} - Viber from {user_name}")
        
        queue_service = MessageQueueService(db)
        queue_result = queue_service.process_incoming_message(message_data, message_id)
        
        if "error" in queue_result:
            logger.error(f"❌ Queue error: {queue_result['error']}")
            return
        
        if queue_result.get("send_status") == "FALSE":
            logger.info(f"⏭️ Message skipped")
            return
        
        response_data = await process_message_async(
            project_id="default",
            client_id=user_id,
            queue_item_id=queue_result["queue_item_id"],
            message_id=message_id,
            contact_send_id=user_id,
            project_configs=project_configs,
            global_claude_service=global_claude_service
        )
        
        if not response_data or response_data.get("error"):
            logger.error(f"❌ Processing error")
            return
        
        is_winner = queue_service.try_claim_as_winner(
            "default",
            user_id,
            queue_result["queue_item_id"],
            message_id
        )
        
        if not is_winner:
            logger.info(f"⏭️ Message superseded")
            return
        
        gpt_response = response_data.get("gpt_response", "")
        pic = response_data.get("pic", "")
        bot_token = os.getenv("VIBER_BOT_TOKEN")
        
        if gpt_response:
            logger.info(f"✅ Sending Viber response: {len(gpt_response)} chars")
            
            if pic:
                try:
                    await send_viber_picture(user_id, pic, gpt_response, bot_token)
                    logger.info(f"📸 Sent picture")
                except Exception as e:
                    logger.error(f"❌ Picture error: {e}")
                    await send_viber_message(user_id, gpt_response, bot_token)
            else:
                await send_viber_message(user_id, gpt_response, bot_token)
            
            logger.info(f"✅ Viber sent")
    
    except Exception as e:
        logger.error(f"❌ Viber processing error: {e}", exc_info=True)
    
    finally:
        db.close()

"""
WhatsApp Bot Handler - Meta Business API
"""
from fastapi import APIRouter, Request, HTTPException, Response
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


def init_whatsapp_handler(configs, claude_service):
    global project_configs, global_claude_service
    project_configs = configs
    global_claude_service = claude_service
    logger.info("✅ WhatsApp handler initialized")


def generate_message_id() -> str:
    import random, string
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))


async def send_whatsapp_message(phone_number_id: str, to: str, message: str, access_token: str):
    """Відправка текстового повідомлення"""
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        if response.status_code != 200:
            logger.error(f"WhatsApp send error: {response.text}")
            raise HTTPException(status_code=500, detail="Failed to send")
        return response.json()


async def send_whatsapp_image(phone_number_id: str, to: str, image_url: str, caption: str, access_token: str):
    """Відправка зображення"""
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "image",
        "image": {"link": image_url, "caption": caption}
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        if response.status_code != 200:
            logger.error(f"WhatsApp image error: {response.text}")
            raise HTTPException(status_code=500, detail="Failed to send image")
        return response.json()


@router.get("/whatsapp/webhook")
async def verify_whatsapp_webhook(request: Request):
    """Верифікація webhook"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN")
    
    if mode == "subscribe" and token == verify_token:
        logger.info("✅ WhatsApp webhook verified")
        return Response(content=challenge, media_type="text/plain")
    else:
        logger.warning("❌ WhatsApp verification failed")
        raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    """Обробка повідомлень WhatsApp"""
    try:
        body = await request.json()
        logger.info(f"📱 WhatsApp: {json.dumps(body, indent=2)}")
        
        if "entry" not in body:
            return {"status": "ok"}
        
        for entry in body["entry"]:
            if "changes" not in entry:
                continue
            
            for change in entry["changes"]:
                if change.get("field") != "messages":
                    continue
                
                value = change.get("value", {})
                messages = value.get("messages", [])
                
                if not messages:
                    continue
                
                metadata = value.get("metadata", {})
                phone_number_id = metadata.get("phone_number_id")
                
                for message in messages:
                    message_type = message.get("type")
                    from_number = message.get("from")
                    
                    if message_type == "text":
                        text = message.get("text", {}).get("body", "")
                        logger.info(f"📨 WhatsApp from {from_number}: {text[:100]}")
                        
                        await process_whatsapp_message(
                            phone_number_id=phone_number_id,
                            from_number=from_number,
                            text=text
                        )
                    
                    elif message_type == "image":
                        image = message.get("image", {})
                        caption = image.get("caption", "")
                        text = caption if caption else "Надіслано зображення"
                        
                        await process_whatsapp_message(
                            phone_number_id=phone_number_id,
                            from_number=from_number,
                            text=text
                        )
        
        return {"status": "ok"}
    
    except Exception as e:
        logger.error(f"❌ WhatsApp error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


async def process_whatsapp_message(phone_number_id: str, from_number: str, text: str):
    """Обробка через bot_processor"""
    db = SessionLocal()
    
    try:
        message_data = SendPulseMessage(
            date=datetime.now().strftime("%d.%m.%Y %H:%M"),
            response=text,
            project_id="default",
            tg_id=from_number,
            contact_send_id=from_number,
            count=0,
            retry=False
        )
        
        message_id = generate_message_id()
        logger.info(f"📝 Message ID: {message_id} - WhatsApp from {from_number}")
        
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
            client_id=from_number,
            queue_item_id=queue_result["queue_item_id"],
            message_id=message_id,
            contact_send_id=from_number,
            project_configs=project_configs,
            global_claude_service=global_claude_service
        )
        
        if not response_data or response_data.get("error"):
            logger.error(f"❌ Processing error")
            return
        
        is_winner = queue_service.try_claim_as_winner(
            "default",
            from_number,
            queue_result["queue_item_id"],
            message_id
        )
        
        if not is_winner:
            logger.info(f"⏭️ Message superseded")
            return
        
        gpt_response = response_data.get("gpt_response", "")
        pic = response_data.get("pic", "")
        access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
        
        if gpt_response:
            logger.info(f"✅ Sending WhatsApp response: {len(gpt_response)} chars")
            
            if pic:
                try:
                    await send_whatsapp_image(phone_number_id, from_number, pic, gpt_response, access_token)
                    logger.info(f"📸 Sent image")
                except Exception as e:
                    logger.error(f"❌ Image error: {e}")
                    await send_whatsapp_message(phone_number_id, from_number, gpt_response, access_token)
            else:
                await send_whatsapp_message(phone_number_id, from_number, gpt_response, access_token)
            
            logger.info(f"✅ WhatsApp sent")
    
    except Exception as e:
        logger.error(f"❌ WhatsApp processing error: {e}", exc_info=True)
    
    finally:
        db.close()

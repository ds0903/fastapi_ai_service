"""
Instagram Bot Handler - Meta Instagram Messaging API
"""
from fastapi import APIRouter, Request, HTTPException, Response
import logging
import json
from datetime import datetime
import httpx
import os

from app.database import SessionLocal
from app.services.message_queue import MessageQueueService
from app.models import SendPulseMessage
from app.bot_processor import process_message_async

logger = logging.getLogger(__name__)
router = APIRouter()

project_configs = None
global_claude_service = None


def init_instagram_handler(configs, claude_service):
    global project_configs, global_claude_service
    project_configs = configs
    global_claude_service = claude_service
    logger.info("✅ Instagram handler initialized")


def generate_message_id() -> str:
    import random, string
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))


async def send_instagram_message(recipient_id: str, message: str, access_token: str):
    """Відправка текстового повідомлення"""
    url = f"https://graph.facebook.com/v18.0/me/messages"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message}
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data, params={"access_token": access_token})
        
        if response.status_code != 200:
            logger.error(f"Instagram send error: {response.text}")
            raise HTTPException(status_code=500, detail="Failed to send")
        
        return response.json()


async def send_instagram_image(recipient_id: str, image_url: str, access_token: str):
    """Відправка зображення"""
    url = f"https://graph.facebook.com/v18.0/me/messages"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "recipient": {"id": recipient_id},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {
                    "url": image_url,
                    "is_reusable": True
                }
            }
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data, params={"access_token": access_token})
        
        if response.status_code != 200:
            logger.error(f"Instagram image error: {response.text}")
            raise HTTPException(status_code=500, detail="Failed to send image")
        
        return response.json()


@router.get("/instagram/webhook")
async def verify_instagram_webhook(request: Request):
    """Верифікація webhook"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    verify_token = os.getenv("INSTAGRAM_VERIFY_TOKEN")
    
    if mode == "subscribe" and token == verify_token:
        logger.info("✅ Instagram webhook verified")
        return Response(content=challenge, media_type="text/plain")
    else:
        logger.warning("❌ Instagram verification failed")
        raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/instagram/webhook")
async def instagram_webhook(request: Request):
    """Обробка повідомлень Instagram"""
    try:
        body = await request.json()
        logger.info(f"📸 Instagram: {json.dumps(body, indent=2)}")
        
        if "entry" not in body:
            return {"status": "ok"}
        
        for entry in body["entry"]:
            if "messaging" not in entry:
                continue
            
            for messaging_event in entry["messaging"]:
                sender_id = messaging_event.get("sender", {}).get("id")
                
                if "message" in messaging_event:
                    message = messaging_event["message"]
                    
                    if "text" in message:
                        text = message.get("text", "")
                        logger.info(f"📨 Instagram from {sender_id}: {text[:100]}")
                        
                        await process_instagram_message(sender_id, text)
                    
                    elif "attachments" in message:
                        attachments = message.get("attachments", [])
                        for attachment in attachments:
                            if attachment.get("type") == "image":
                                image_url = attachment.get("payload", {}).get("url", "")
                                text = f"Надіслано зображення: {image_url}"
                                
                                await process_instagram_message(sender_id, text)
                
                elif "postback" in messaging_event:
                    postback = messaging_event["postback"]
                    payload = postback.get("payload", "")
                    title = postback.get("title", "")
                    
                    text = title if title else payload
                    await process_instagram_message(sender_id, text)
        
        return {"status": "ok"}
    
    except Exception as e:
        logger.error(f"❌ Instagram error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


async def process_instagram_message(sender_id: str, text: str):
    """Обробка через bot_processor"""
    db = SessionLocal()
    
    try:
        message_data = SendPulseMessage(
            date=datetime.now().strftime("%d.%m.%Y %H:%M"),
            response=text,
            project_id="default",
            tg_id=sender_id,
            contact_send_id=sender_id,
            count=0,
            retry=False
        )
        
        message_id = generate_message_id()
        logger.info(f"📝 Message ID: {message_id} - Instagram from {sender_id}")
        
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
            client_id=sender_id,
            queue_item_id=queue_result["queue_item_id"],
            message_id=message_id,
            contact_send_id=sender_id,
            project_configs=project_configs,
            global_claude_service=global_claude_service
        )
        
        if not response_data or response_data.get("error"):
            logger.error(f"❌ Processing error")
            return
        
        is_winner = queue_service.try_claim_as_winner(
            "default",
            sender_id,
            queue_result["queue_item_id"],
            message_id
        )
        
        if not is_winner:
            logger.info(f"⏭️ Message superseded")
            return
        
        gpt_response = response_data.get("gpt_response", "")
        pic = response_data.get("pic", "")
        access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        
        if gpt_response:
            logger.info(f"✅ Sending Instagram response: {len(gpt_response)} chars")
            
            await send_instagram_message(sender_id, gpt_response, access_token)
            
            if pic:
                try:
                    await send_instagram_image(sender_id, pic, access_token)
                    logger.info(f"📸 Sent image")
                except Exception as e:
                    logger.error(f"❌ Image error: {e}")
            
            logger.info(f"✅ Instagram sent")
    
    except Exception as e:
        logger.error(f"❌ Instagram processing error: {e}", exc_info=True)
    
    finally:
        db.close()

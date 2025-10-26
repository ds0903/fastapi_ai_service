"""
Messages handler - processes all text messages through AI
"""
from aiogram import Router, F
from aiogram.types import Message
import logging
import random
import string
from datetime import datetime

from telegram.database import SessionLocal
from telegram.services.message_queue import MessageQueueService
from telegram.models import MessageStatus, SendPulseMessage

logger = logging.getLogger(__name__)
router = Router()

# Global references (initialized by bot.py)
_project_configs = None
_global_claude_service = None


def init_handler(project_configs, claude_service):
    """Initialize handler with global configs"""
    global _project_configs, _global_claude_service
    _project_configs = project_configs
    _global_claude_service = claude_service
    logger.info("✅ Messages handler initialized with project configs")


def generate_message_id() -> str:
    """Generate unique message ID"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))


@router.message(F.text)
async def handle_text_message(message: Message):
    """
    Handle all text messages through AI processing
    """
    user_id = str(message.from_user.id)
    text = message.text
    
    logger.info(f"📨 Received message from user {user_id}: '{text[:100]}...'")
    
    # Get database session
    db = SessionLocal()
    
    try:
        # Create queue service
        queue_service = MessageQueueService(db)
        
        # Create message object for processing
        message_data = SendPulseMessage(
            date=datetime.now().strftime("%d.%m.%Y %H:%M"),
            response=text,
            project_id="default",
            tg_id=user_id,
            contact_send_id=user_id,
            count=0,
            retry=False
        )
        
        # Generate message ID
        message_id = generate_message_id()
        
        logger.info(f"📝 Message ID: {message_id} - Processing from user {user_id}")
        
        # Process through queue
        queue_result = queue_service.process_incoming_message(message_data, message_id)
        
        if "error" in queue_result:
            logger.error(f"❌ Queue error: {queue_result['error']}")
            await message.answer("Виникла помилка при обробці. Спробуйте ще раз.")
            return
        
        # Check if skipped
        if queue_result.get("send_status") == "FALSE":
            logger.info(f"⏭️ Message skipped due to retry logic")
            return
        
        # Send typing action
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        
        # Process message - import here to avoid circular import
        from telegram.bot_processor import process_message_async
        
        logger.info(f"🤖 Starting AI processing for message {message_id}")
        response_data = await process_message_async(
            project_id="default",
            client_id=user_id,
            queue_item_id=queue_result["queue_item_id"],
            message_id=message_id,
            contact_send_id=user_id,
            project_configs=_project_configs,
            global_claude_service=_global_claude_service
        )
        
        if not response_data:
            logger.error(f"❌ No response data")
            await message.answer("Вибачте, сталася помилка. Спробуйте ще раз.")
            return
        
        # Check for errors
        if response_data.get("error"):
            logger.error(f"❌ Processing error: {response_data['error']}")
            await message.answer("Вибачте, сталася помилка. Спробуйте ще раз.")
            return
        
        # Try to claim as winner
        is_winner = queue_service.try_claim_as_winner(
            "default",
            user_id,
            queue_result["queue_item_id"],
            message_id
        )
        
        if not is_winner:
            logger.info(f"⏭️ Message superseded by newer one")
            return
        
        # Send response
        gpt_response = response_data.get("gpt_response", "")
        pic = response_data.get("pic", "")
        
        if gpt_response:
            logger.info(f"✅ Sending response to user {user_id}: {len(gpt_response)} chars")
            
            if pic:
                try:
                    await message.answer_photo(
                        photo=pic,
                        caption=gpt_response
                    )
                    logger.info(f"📸 Sent photo with caption")
                except Exception as e:
                    logger.error(f"❌ Failed to send photo: {e}")
                    await message.answer(gpt_response)
            else:
                await message.answer(gpt_response)
            
            logger.info(f"✅ Response sent successfully")
        else:
            logger.warning(f"⚠️ Empty GPT response")
    
    except Exception as e:
        logger.error(f"❌ Error handling message: {e}", exc_info=True)
        await message.answer("Вибачте, сталася помилка. Спробуйте ще раз.")
    
    finally:
        db.close()


@router.message(F.photo)
async def handle_photo_message(message: Message):
    """Handle messages with photos"""
    user_id = str(message.from_user.id)
    
    # Get largest photo
    photo = message.photo[-1]
    file_info = await message.bot.get_file(photo.file_id)
    photo_url = f"https://api.telegram.org/file/bot{message.bot.token}/{file_info.file_path}"
    
    # Get caption
    text = message.caption or ""
    
    # Add photo URL to text
    full_text = f"{text} {photo_url}".strip()
    
    logger.info(f"📷 Received photo from user {user_id}")
    
    # Monkey-patch text and process
    message.text = full_text
    await handle_text_message(message)

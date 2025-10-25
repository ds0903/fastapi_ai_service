"""
Start command handler
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Handle /start command"""
    user_id = message.from_user.id
    username = message.from_user.username or "друг"
    
    logger.info(f"User {user_id} (@{username}) started the bot")
    
    welcome_text = f"""👋 Привіт, {message.from_user.first_name}!

Я - AI асистент косметологічної клініки. Можу допомогти вам:
✅ Записатися на процедуру
✅ Змінити або відмінити запис
✅ Підібрати час і спеціаліста
✅ Відповісти на питання про послуги

Просто напишіть мені що вас цікавить, і я допоможу! 😊"""

    await message.answer(welcome_text)
    logger.info(f"Sent welcome message to user {user_id}")

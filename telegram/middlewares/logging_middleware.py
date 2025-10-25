"""
Logging middleware for tracking all updates
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Update, Message
import logging

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    """
    Middleware for logging all incoming updates
    """
    
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any]
    ) -> Any:
        """Log update and call next handler"""
        
        if event.message:
            user_id = event.message.from_user.id
            username = event.message.from_user.username
            chat_id = event.message.chat.id
            text = event.message.text or event.message.caption or "[no text]"
            
            logger.info(
                f"📥 Update from user {user_id} (@{username}) in chat {chat_id}: '{text[:100]}...'"
            )
        
        # Call next handler
        return await handler(event, data)

import redis
import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from ..database import MessageQueue, ClientLastActivity, get_db
from ..models import SendPulseMessage, MessageQueueItem, MessageStatus
from ..config import settings

logger = logging.getLogger(__name__)

# Redis connection for real-time queue management
redis_client = redis.from_url(settings.redis_url)


class MessageQueueService:
    """Service for handling message queue operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.redis_client = redis_client
        logger.debug("MessageQueueService initialized")
    
    def process_incoming_message(self, message: SendPulseMessage) -> Dict[str, Any]:
        """
        Process incoming message from SendPulse according to the technical specification:
        1. Check if message should be processed (retry logic)
        2. Add to queue or update existing message
        3. Handle message aggregation for flood protection
        """
        client_id = message.tg_id or message.client_id
        if not client_id:
            logger.error(f"No client ID provided in message: {message}")
            return {"error": "No client ID provided"}
        
        logger.info(f"Processing incoming message from client_id={client_id}, project_id={message.project_id}")
        logger.debug(f"Message details: count={message.count}, retry={message.retry}, message='{message.response[:100]}...'")
        
        # Step 3: Check retry logic
        if not self._should_process_message(message):
            logger.info(f"Message skipped due to retry logic for client_id={client_id}")
            return {
                "send_status": "FALSE",
                "count": "1",
                "message": "Message skipped due to retry logic"
            }
        
        # Step 2: Add to queue and handle aggregation
        logger.debug(f"Adding message to queue for client_id={client_id}")
        queue_item = self._add_to_queue(message)
        
        # Update client last activity
        logger.debug(f"Updating client activity for client_id={client_id}")
        self._update_client_activity(message.project_id, client_id)
        
        logger.info(f"Message queued successfully for client_id={client_id}, queue_item_id={queue_item.id}")
        return {
            "queue_item_id": queue_item.id,
            "status": "queued",
            "aggregated_message": queue_item.aggregated_message
        }
    
    def _should_process_message(self, message: SendPulseMessage) -> bool:
        """
        Determine if message should be processed based on retry logic
        From spec: if (retry = false) or (retry = true and count != 0) - process
        """
        client_id = message.tg_id or message.client_id
        should_process = False
        
        if not message.retry:
            should_process = True
            logger.debug(f"Processing message for client_id={client_id}: not a retry")
        elif message.retry and message.count != 0:
            should_process = True
            logger.debug(f"Processing message for client_id={client_id}: retry with count={message.count}")
        else:
            logger.debug(f"Skipping message for client_id={client_id}: retry with count=0")
        
        return should_process
    
    def check_for_new_messages_during_processing(self, project_id: str, client_id: str, processing_message_id: str) -> Optional[str]:
        """
        Check if new messages arrived while a message was being processed
        If yes, return the concatenated batch of new messages
        """
        logger.debug(f"Checking for new messages during processing for client_id={client_id}")
        
        # Get messages that arrived while processing (newer than the one being processed)
        processing_message = self.db.query(MessageQueue).filter(MessageQueue.id == processing_message_id).first()
        if not processing_message:
            logger.warning(f"Processing message {processing_message_id} not found")
            return None
            
        new_messages = self.db.query(MessageQueue).filter(
            and_(
                MessageQueue.project_id == project_id,
                MessageQueue.client_id == client_id,
                MessageQueue.status == MessageStatus.PENDING,
                MessageQueue.created_at > processing_message.created_at
            )
        ).order_by(MessageQueue.created_at).all()
        
        if not new_messages:
            logger.debug(f"No new messages arrived during processing for client_id={client_id}")
            return None
            
        logger.info(f"Found {len(new_messages)} new messages that arrived during processing for client_id={client_id}")
        
        # Concatenate all new messages
        concatenated_message = " ".join([msg.original_message for msg in new_messages])
        logger.info(f"Concatenated new messages for client_id={client_id}: '{concatenated_message[:100]}...'")
        
        # Mark all these messages as cancelled since we're batching them
        for msg in new_messages:
            msg.status = MessageStatus.CANCELLED
            msg.updated_at = datetime.utcnow()
            logger.debug(f"Cancelled message {msg.id} (batching into new processing)")
            
        self.db.commit()
        
        return concatenated_message
    
    def create_batched_message(self, project_id: str, client_id: str, concatenated_message: str) -> MessageQueueItem:
        """
        Create a new queue item for a batch of concatenated messages
        """
        logger.info(f"Creating batched message for client_id={client_id}: '{concatenated_message[:100]}...'")
        
        queue_item_id = str(uuid.uuid4())
        queue_item = MessageQueue(
            id=queue_item_id,
            project_id=project_id,
            client_id=client_id,
            original_message=concatenated_message,
            aggregated_message=concatenated_message,
            status=MessageStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        self.db.add(queue_item)
        self.db.commit()
        self.db.refresh(queue_item)
        
        logger.info(f"Batched message {queue_item_id} created successfully for client_id={client_id}")
        return queue_item
    
    def is_client_currently_processing(self, project_id: str, client_id: str) -> bool:
        """
        Check if a client currently has a message being processed
        """
        processing_message = self.db.query(MessageQueue).filter(
            and_(
                MessageQueue.project_id == project_id,
                MessageQueue.client_id == client_id,
                MessageQueue.status == MessageStatus.PROCESSING
            )
        ).first()
        
        is_processing = processing_message is not None
        logger.debug(f"Client {client_id} processing status: {is_processing}")
        return is_processing

    def _add_to_queue(self, message: SendPulseMessage) -> MessageQueueItem:
        """
        Add message to queue - handles both normal queuing and batching during processing
        """
        client_id = message.tg_id or message.client_id
        
        # Check if client is currently processing a message
        if self.is_client_currently_processing(message.project_id, client_id):
            logger.info(f"Client {client_id} is currently processing - queuing new message for later batching")
            # Just queue the message as-is, it will be batched after current processing completes
            aggregated_text = message.response
        else:
            logger.debug(f"Looking for existing pending messages for client_id={client_id}")
            # Get existing pending messages for this client
            existing_messages = self.db.query(MessageQueue).filter(
                and_(
                    MessageQueue.project_id == message.project_id,
                    MessageQueue.client_id == client_id,
                    MessageQueue.status == MessageStatus.PENDING
                )
            ).all()
            
            # If there are existing pending messages, aggregate them
            if existing_messages:
                logger.info(f"Found {len(existing_messages)} existing pending messages for client_id={client_id}, aggregating")
                # Mark all existing messages as cancelled
                for msg in existing_messages:
                    msg.status = MessageStatus.CANCELLED
                    msg.updated_at = datetime.utcnow()
                    logger.debug(f"Cancelled existing message {msg.id} for client_id={client_id}")
                
                # Create aggregated message
                aggregated_text = " ".join([msg.aggregated_message for msg in existing_messages])
                aggregated_text += " " + message.response
                
                # Store aggregated message in Redis for quick access
                redis_key = f"aggregated_{message.project_id}_{client_id}"
                self.redis_client.setex(redis_key, 3600, aggregated_text)  # 1 hour expiry
                logger.debug(f"Stored aggregated message in Redis for client_id={client_id}")
            else:
                logger.debug(f"No existing pending messages for client_id={client_id}")
                aggregated_text = message.response
        
        # Create new queue item
        queue_item_id = str(uuid.uuid4())
        logger.debug(f"Creating new queue item {queue_item_id} for client_id={client_id}")
        queue_item = MessageQueue(
            id=queue_item_id,
            project_id=message.project_id,
            client_id=client_id,
            original_message=message.response,
            aggregated_message=aggregated_text,
            status=MessageStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        self.db.add(queue_item)
        self.db.commit()
        self.db.refresh(queue_item)
        
        logger.info(f"Queue item {queue_item_id} created successfully for client_id={client_id}")
        return queue_item
    
    def get_message_for_processing(self, project_id: str, client_id: str) -> Optional[MessageQueueItem]:
        """Get the latest pending message for a client"""
        logger.debug(f"Getting message for processing: project_id={project_id}, client_id={client_id}")
        
        message = self.db.query(MessageQueue).filter(
            and_(
                MessageQueue.project_id == project_id,
                MessageQueue.client_id == client_id,
                MessageQueue.status == MessageStatus.PENDING
            )
        ).order_by(desc(MessageQueue.created_at)).first()
        
        if message:
            logger.debug(f"Found pending message {message.id} for client_id={client_id}")
            return MessageQueueItem(
                id=message.id,
                project_id=message.project_id,
                client_id=message.client_id,
                original_message=message.original_message,
                aggregated_message=message.aggregated_message,
                status=MessageStatus(message.status),
                created_at=message.created_at,
                updated_at=message.updated_at,
                retry_count=message.retry_count
            )
        else:
            logger.debug(f"No pending message found for client_id={client_id}")
            return None
    
    def update_message_status(self, message_id: str, status: MessageStatus) -> bool:
        """Update message status"""
        logger.debug(f"Updating message status: message_id={message_id}, status={status.value}")
        
        message = self.db.query(MessageQueue).filter(MessageQueue.id == message_id).first()
        if message:
            old_status = message.status
            message.status = status.value
            message.updated_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"Message status updated: message_id={message_id}, {old_status} -> {status.value}")
            return True
        else:
            logger.warning(f"Message not found for status update: message_id={message_id}")
            return False
    
    def check_message_still_valid(self, message_id: str) -> bool:
        """
        Check if message is still valid for processing (not superseded by new messages)
        This is called before sending response to ensure no new messages arrived
        """
        message = self.db.query(MessageQueue).filter(MessageQueue.id == message_id).first()
        if not message:
            return False
        
        # Check if there are newer pending messages from same client
        newer_messages = self.db.query(MessageQueue).filter(
            and_(
                MessageQueue.project_id == message.project_id,
                MessageQueue.client_id == message.client_id,
                MessageQueue.status == MessageStatus.PENDING,
                MessageQueue.created_at > message.created_at
            )
        ).count()
        
        return newer_messages == 0
    
    def clear_client_queue(self, project_id: str, client_id: str) -> None:
        """Clear all messages for a client after successful processing"""
        logger.debug(f"Clearing client queue: project_id={project_id}, client_id={client_id}")
        
        messages = self.db.query(MessageQueue).filter(
            and_(
                MessageQueue.project_id == project_id,
                MessageQueue.client_id == client_id,
                MessageQueue.status.in_([MessageStatus.PENDING, MessageStatus.PROCESSING])
            )
        ).all()
        
        logger.info(f"Clearing {len(messages)} messages for client_id={client_id}")
        
        for message in messages:
            message.status = MessageStatus.COMPLETED
            message.updated_at = datetime.utcnow()
            logger.debug(f"Marked message {message.id} as completed for client_id={client_id}")
        
        self.db.commit()
        
        # Also clear Redis cache
        redis_key = f"aggregated_{project_id}_{client_id}"
        deleted_count = self.redis_client.delete(redis_key)
        if deleted_count > 0:
            logger.debug(f"Cleared Redis aggregation cache for client_id={client_id}")
        
        logger.info(f"Client queue cleared successfully for client_id={client_id}")
    
    def _update_client_activity(self, project_id: str, client_id: str) -> None:
        """Update client last activity timestamp"""
        activity = self.db.query(ClientLastActivity).filter(
            and_(
                ClientLastActivity.project_id == project_id,
                ClientLastActivity.client_id == client_id
            )
        ).first()
        
        if activity:
            activity.last_message_at = datetime.utcnow()
        else:
            activity = ClientLastActivity(
                project_id=project_id,
                client_id=client_id,
                last_message_at=datetime.utcnow()
            )
            self.db.add(activity)
        
        self.db.commit()
    
    def get_clients_for_archiving(self, hours: int = 24) -> List[Dict[str, str]]:
        """Get clients that haven't been active for specified hours"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        activities = self.db.query(ClientLastActivity).filter(
            ClientLastActivity.last_message_at < cutoff_time
        ).all()
        
        return [
            {
                "project_id": activity.project_id,
                "client_id": activity.client_id,
                "last_message_at": activity.last_message_at.isoformat()
            }
            for activity in activities
        ]
    
    def get_queue_stats(self, project_id: str) -> Dict[str, int]:
        """Get queue statistics for a project"""
        stats = {}
        
        for status in MessageStatus:
            count = self.db.query(MessageQueue).filter(
                and_(
                    MessageQueue.project_id == project_id,
                    MessageQueue.status == status.value
                )
            ).count()
            stats[status.value] = count
        
        return stats 
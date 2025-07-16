import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from ..database import Dialogue, ClientLastActivity, get_db
from ..services.claude_service import ClaudeService
from ..config import ProjectConfig, settings

logger = logging.getLogger(__name__)


class DialogueArchivingService:
    """Service for archiving old dialogues to save storage"""
    
    def __init__(self):
        self.archive_hours = settings.dialogue_archive_hours
        logger.debug(f"DialogueArchivingService initialized with archive_hours={self.archive_hours}")
    
    async def archive_old_dialogues(self, project_configs: Dict[str, ProjectConfig]):
        """Archive dialogues older than specified hours"""
        logger.info(f"Starting dialogue archiving process for {len(project_configs)} projects")
        
        # Get database session
        from ..database import SessionLocal
        db = SessionLocal()
        
        try:
            # Get clients that need archiving
            cutoff_time = datetime.utcnow() - timedelta(hours=self.archive_hours)
            logger.debug(f"Archiving dialogues older than {cutoff_time}")
            
            activities = db.query(ClientLastActivity).filter(
                ClientLastActivity.last_message_at < cutoff_time
            ).all()
            
            logger.info(f"Found {len(activities)} clients with dialogues ready for archiving")
            
            if not activities:
                logger.info("No dialogues to archive at this time")
                return
            
            archived_count = 0
            error_count = 0
            
            for activity in activities:
                try:
                    project_config = project_configs.get(activity.project_id)
                    if not project_config:
                        logger.warning(f"No project config found for project_id={activity.project_id}, skipping client {activity.client_id}")
                        continue
                    
                    logger.debug(f"Processing archival for client_id={activity.client_id}, project_id={activity.project_id}")
                    
                    # Get unarchived dialogues for this client
                    dialogues = db.query(Dialogue).filter(
                        and_(
                            Dialogue.project_id == activity.project_id,
                            Dialogue.client_id == activity.client_id,
                            Dialogue.is_archived == False
                        )
                    ).order_by(desc(Dialogue.timestamp)).all()
                    
                    if not dialogues:
                        logger.debug(f"No unarchived dialogues found for client_id={activity.client_id}")
                        continue
                    
                    logger.info(f"Archiving {len(dialogues)} dialogues for client_id={activity.client_id}")
                    
                    # Build dialogue history string
                    dialogue_history = self._build_dialogue_history(dialogues)
                    logger.debug(f"Built dialogue history ({len(dialogue_history)} chars) for client_id={activity.client_id}")
                    
                    # Compress using Claude
                    claude_service = ClaudeService(db)
                    logger.debug(f"Starting dialogue compression for client_id={activity.client_id}")
                    compressed_history = await claude_service.compress_dialogue(
                        project_config,
                        dialogue_history
                    )
                    
                    logger.debug(f"Dialogue compressed from {len(dialogue_history)} to {len(compressed_history)} chars for client_id={activity.client_id}")
                    
                    # Update client activity with compressed history
                    activity.zip_history = compressed_history
                    
                    # Mark dialogues as archived
                    for dialogue in dialogues:
                        dialogue.is_archived = True
                    
                    db.commit()
                    
                    logger.info(f"Successfully archived {len(dialogues)} dialogues for client_id={activity.client_id}")
                    archived_count += 1
                    
                    # Small delay to not overwhelm Claude API
                    await asyncio.sleep(1)
                    
                except Exception as client_error:
                    logger.error(f"Error archiving dialogues for client_id={activity.client_id}: {client_error}", exc_info=True)
                    error_count += 1
                    # Continue with next client
                    continue
            
            logger.info(f"Dialogue archiving completed: {archived_count} clients processed successfully, {error_count} errors")
            
        except Exception as e:
            logger.error(f"Error during dialogue archiving process: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()
            logger.debug("Database session closed for dialogue archiving")
    
    def _build_dialogue_history(self, dialogues: List[Dialogue]) -> str:
        """Build dialogue history string from dialogue entries"""
        logger.debug(f"Building dialogue history from {len(dialogues)} entries")
        
        history_lines = []
        
        for dialogue in reversed(dialogues):  # Reverse to chronological order
            role = "Клиент" if dialogue.role == "client" else "Бот"
            timestamp = dialogue.timestamp.strftime("%d.%m %H:%M")
            history_lines.append(f"[{timestamp}] {role}: {dialogue.message}")
        
        history_text = "\n".join(history_lines)
        logger.debug(f"Built dialogue history: {len(history_text)} characters, {len(history_lines)} lines")
        
        return history_text
    
    def get_archiving_stats(self, db: Session) -> Dict[str, Any]:
        """Get archiving statistics"""
        logger.debug("Getting dialogue archiving statistics")
        
        try:
            total_dialogues = db.query(Dialogue).count()
            archived_dialogues = db.query(Dialogue).filter(
                Dialogue.is_archived == True
            ).count()
            
            clients_with_archives = db.query(ClientLastActivity).filter(
                ClientLastActivity.zip_history.isnot(None)
            ).count()
            
            stats = {
                "total_dialogues": total_dialogues,
                "archived_dialogues": archived_dialogues,
                "active_dialogues": total_dialogues - archived_dialogues,
                "clients_with_archives": clients_with_archives
            }
            
            logger.debug(f"Archiving stats: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error getting archiving stats: {e}")
            return {
                "total_dialogues": 0,
                "archived_dialogues": 0,
                "active_dialogues": 0,
                "clients_with_archives": 0
            }


# Background task to run archiving periodically
async def run_dialogue_archiving_task(project_configs: Dict[str, ProjectConfig]):
    """Background task to run dialogue archiving every hour"""
    logger.info("Starting dialogue archiving background task")
    archiving_service = DialogueArchivingService()
    
    while True:
        try:
            logger.debug("Running scheduled dialogue archiving")
            await archiving_service.archive_old_dialogues(project_configs)
            logger.debug("Scheduled dialogue archiving completed, waiting 1 hour for next run")
            # Wait 1 hour before next run
            await asyncio.sleep(3600)
        except Exception as e:
            logger.error(f"Error in archiving task: {e}", exc_info=True)
            logger.info("Waiting 10 minutes before retry after error")
            # Wait 10 minutes before retry
            await asyncio.sleep(600) 
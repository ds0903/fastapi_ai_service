import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging
from typing import Optional, List

from telegram.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending email notifications"""
    
    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_user = settings.email_host_user
        self.smtp_password = settings.email_host_password
        self.sendpulse_bot_id = settings.sendpulse_bot_id
        
        # Parse comma-separated email lists
        self.admin_emails = [e.strip() for e in settings.admin_emails.split(',') if e.strip()]
        self.consultant_emails = [e.strip() for e in settings.consultant_emails.split(',') if e.strip()]
    
    def _get_recipient_emails(self, request_type: int) -> List[str]:
        """
        Get list of recipient emails based on request type
        
        Args:
            request_type: 1 for admin, 2 for consultant, 0 for none
            
        Returns:
            List of email addresses
        """
        if request_type == 1:
            return self.admin_emails
        elif request_type == 2:
            return self.consultant_emails
        else:
            return []
    
    async def send_human_consultant_request(
        self,
        request_type: int,
        client_id: str,
        client_name: Optional[str] = None,
        phone: Optional[str] = None,
        last_message: Optional[str] = None,
        message_id: Optional[str] = None,
        contact_send_id: Optional[str] = None
    ) -> bool:
        """
        Send email notification when client requests human consultant
        
        Args:
            request_type: 1 for admin, 2 for consultant, 0 for none
            client_id: Client telegram ID
            client_name: Client name if available
            phone: Client phone if available
            last_message: Last message from client
            message_id: Internal message ID for tracking
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Get recipient emails based on request type
            recipients = self._get_recipient_emails(request_type)
            
            if not recipients:
                logger.warning(f"Message ID: {message_id} - No recipients configured for request type {request_type}")
                return False
            
            if not self.smtp_user or not self.smtp_password:
                logger.warning(f"Message ID: {message_id} - SMTP credentials not configured, cannot send email")
                return False
            
            # Determine request type name for subject
            request_type_name = "адміністратора" if request_type == 1 else "консультанта"
            
            # Prepare email content
            subject = f"🔔 Клієнт просить {request_type_name} - {client_id}"
            
            # Build email body
            body_parts = [
                "<html><body>",
                f"<h2>Запит на підключення {request_type_name}</h2>",
                f"<p><strong>Дата та час:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>",
                f"<p><strong>ID клієнта:</strong> {client_id}</p>"
            ]
            
            if client_name:
                body_parts.append(f"<p><strong>Ім'я клієнта:</strong> {client_name}</p>")
            
            if phone:
                body_parts.append(f"<p><strong>Телефон:</strong> {phone}</p>")
            
            if last_message:
                body_parts.append(f"<p><strong>Останнє повідомлення:</strong></p>")
                body_parts.append(f"<blockquote>{last_message}</blockquote>")
            
            # Додаємо посилання на чат в SendPulse
            if contact_send_id:
                channel = settings.messenger_channel.lower()
                chat_url = f"https://login.sendpulse.com/chatbots/chats?bot_id={self.sendpulse_bot_id}&channel={channel}&status=all&assignee=all&contact_id={contact_send_id}"
                body_parts.append(f"<p><strong>Посилання на чат:</strong> <a href='{chat_url}'>Відкрити чат в SendPulse</a></p>")
            
            body_parts.append(f"<p>Клієнт очікує на відповідь від реального {request_type_name}.</p>")
            body_parts.append("<p>Будь ласка, зв'яжіться з клієнтом якомога швидше.</p>")
            body_parts.append("</body></html>")
            
            body = "".join(body_parts)
            
            # Send email to all recipients
            success_count = 0
            for recipient in recipients:
                try:
                    # Create message
                    msg = MIMEMultipart('alternative')
                    msg['From'] = self.smtp_user
                    msg['To'] = recipient
                    msg['Subject'] = subject
                    
                    # Attach HTML body
                    html_part = MIMEText(body, 'html', 'utf-8')
                    msg.attach(html_part)
                    
                    # Send email
                    logger.info(f"Message ID: {message_id} - Sending human consultant request email to {recipient}")
                    
                    with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                        server.starttls()
                        server.login(self.smtp_user, self.smtp_password)
                        server.send_message(msg)
                    
                    logger.info(f"Message ID: {message_id} - Email sent successfully to {recipient}")
                    success_count += 1
                    
                except Exception as e:
                    logger.error(f"Message ID: {message_id} - Failed to send email to {recipient}: {e}", exc_info=True)
            
            if success_count > 0:
                logger.info(f"Message ID: {message_id} - Successfully sent {success_count}/{len(recipients)} emails")
                return True
            else:
                logger.error(f"Message ID: {message_id} - Failed to send all emails")
                return False
            
        except Exception as e:
            logger.error(f"Message ID: {message_id} - Failed to send human consultant request email: {e}", exc_info=True)
            return False

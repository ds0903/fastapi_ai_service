import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending email notifications"""
    
    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_user = settings.email_host_user
        self.smtp_password = settings.email_host_password
        self.admin_email = settings.admin_email
    
    async def send_human_consultant_request(
        self,
        client_id: str,
        client_name: Optional[str] = None,
        phone: Optional[str] = None,
        last_message: Optional[str] = None,
        message_id: Optional[str] = None
    ) -> bool:
        """
        Send email notification when client requests human consultant
        
        Args:
            client_id: Client telegram ID
            client_name: Client name if available
            phone: Client phone if available
            last_message: Last message from client
            message_id: Internal message ID for tracking
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            if not self.admin_email:
                logger.warning(f"Message ID: {message_id} - Admin email not configured, cannot send notification")
                return False
            
            if not self.smtp_user or not self.smtp_password:
                logger.warning(f"Message ID: {message_id} - SMTP credentials not configured, cannot send email")
                return False
            
            # Prepare email content
            subject = f"🔔 Клієнт просить живого консультанта - {client_id}"
            
            # Build email body
            body_parts = [
                "<html><body>",
                "<h2>Запит на підключення живого консультанта</h2>",
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
            
            body_parts.append("<p>Клієнт очікує на відповідь від реального консультанта.</p>")
            body_parts.append("<p>Будь ласка, зв'яжіться з клієнтом якомога швидше.</p>")
            body_parts.append("</body></html>")
            
            body = "".join(body_parts)
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.smtp_user
            msg['To'] = self.admin_email
            msg['Subject'] = subject
            
            # Attach HTML body
            html_part = MIMEText(body, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Send email
            logger.info(f"Message ID: {message_id} - Sending human consultant request email to {self.admin_email}")
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Message ID: {message_id} - Human consultant request email sent successfully")
            return True
            
        except Exception as e:
            logger.error(f"Message ID: {message_id} - Failed to send human consultant request email: {e}", exc_info=True)
            return False

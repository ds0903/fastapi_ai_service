from typing import Dict, Any, Optional, List
from datetime import datetime, date, time, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging

from ..database import Booking, Feedback
from ..models import ClaudeMainResponse, BookingRecord
from ..config import ProjectConfig
from ..services.google_sheets import GoogleSheetsService

logger = logging.getLogger(__name__)


class BookingService:
    """Service for handling booking operations"""
    
    def __init__(self, db: Session, project_config: ProjectConfig):
        self.db = db
        self.project_config = project_config
        self.sheets_service = GoogleSheetsService(project_config)
        logger.debug(f"BookingService initialized for project {project_config.project_id}")
    
    async def process_booking_action(self, claude_response: ClaudeMainResponse, client_id: str, message_id: str) -> Dict[str, Any]:
        """Process booking action from Claude response"""
        logger.info(f"Message ID: {message_id} - Processing booking action for client_id={client_id}")
        logger.debug(f"Message ID: {message_id} - Booking action details: activate={claude_response.activate_booking}, reject={claude_response.reject_order}, change={claude_response.change_order}")
        
        result = {"success": False, "message": "", "action": None}
        
        try:
            if claude_response.activate_booking:
                logger.info(f"Message ID: {message_id} - Processing booking activation for client_id={client_id}")
                result = await self._activate_booking(claude_response, client_id, message_id)
                result["action"] = "activate"
            elif claude_response.reject_order:
                logger.info(f"Message ID: {message_id} - Processing booking rejection for client_id={client_id}")
                result = await self._reject_booking(claude_response, client_id, message_id)
                result["action"] = "reject"
            elif claude_response.change_order:
                logger.info(f"Message ID: {message_id} - Processing booking change for client_id={client_id}")
                result = await self._change_booking(claude_response, client_id, message_id)
                result["action"] = "change"
            else:
                logger.debug(f"Message ID: {message_id} - No booking action required for client_id={client_id}")
                result = {"success": True, "message": "No booking action required", "action": "none"}
            
            # Save feedback if provided
            if claude_response.feedback:
                logger.info(f"Message ID: {message_id} - Saving client feedback for client_id={client_id}")
                self._save_feedback(claude_response, client_id, message_id)
            
            logger.info(f"Message ID: {message_id} - Booking action completed for client_id={client_id}: {result['action']} - success={result['success']}")
            return result
            
        except Exception as e:
            logger.error(f"Message ID: {message_id} - Error processing booking action for client_id={client_id}: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Ошибка при обработке заказа: {str(e)}",
                "action": "error"
            }
    
    async def _activate_booking(self, response: ClaudeMainResponse, client_id: str, message_id: str) -> Dict[str, Any]:
        """Activate a new booking"""
        logger.info(f"Message ID: {message_id} - Activating booking for client_id={client_id}")
        
        try:
            # Validate required fields
            if not response.cosmetolog or not response.date_order or not response.time_set_up:
                logger.warning(f"Message ID: {message_id} - Missing required booking fields for client_id={client_id}: specialist={response.cosmetolog}, date={response.date_order}, time={response.time_set_up}")
                return {
                    "success": False,
                    "message": "Недостаточно данных для создания записи"
                }
            
            # Parse date and time
            try:
                booking_date = datetime.strptime(response.date_order, "%d.%m.%Y").date()
            except ValueError:
                try:
                    booking_date = datetime.strptime(response.date_order, "%d.%m").date().replace(year=datetime.now().year)
                except ValueError:
                    logger.warning(f"Message ID: {message_id} - Invalid date format for client_id={client_id}: {response.date_order}")
                    return {
                        "success": False,
                        "message": f"Неверный формат даты: {response.date_order}"
                    }
            
            try:
                booking_time = datetime.strptime(response.time_set_up, "%H:%M").time()
            except ValueError:
                logger.warning(f"Message ID: {message_id} - Invalid time format for client_id={client_id}: {response.time_set_up}")
                return {
                    "success": False,
                    "message": f"Неверный формат времени: {response.time_set_up}"
                }
            
            # Check if specialist exists
            if response.cosmetolog not in self.project_config.specialists:
                logger.warning(f"Message ID: {message_id} - Unknown specialist requested: {response.cosmetolog}, available: {self.project_config.specialists}")
                return {
                    "success": False,
                    "message": f"Специалист {response.cosmetolog} не найден"
                }
            
            # Determine service duration
            duration_slots = 1
            if response.procedure and response.procedure in self.project_config.services:
                duration_slots = self.project_config.services[response.procedure]
                logger.info(f"Message ID: {message_id} - Service '{response.procedure}' requires {duration_slots} slots ({duration_slots * 30} minutes)")
            else:
                logger.warning(f"Message ID: {message_id} - Unknown service '{response.procedure}', using default duration: 1 slot (30 minutes). Available services: {list(self.project_config.services.keys())}")
            
            # Check if time slot is available (double-check both database and Google Sheets)
            logger.debug(f"Message ID: {message_id} - Checking slot availability: specialist={response.cosmetolog}, date={booking_date}, time={booking_time}, duration={duration_slots}")
            
            # Check database availability first
            if not self._is_slot_available(response.cosmetolog, booking_date, booking_time, duration_slots):
                logger.warning(f"Message ID: {message_id} - Time slot not available in database: specialist={response.cosmetolog}, date={booking_date}, time={booking_time}")
                return {
                    "success": False,
                    "message": "Выбранное время уже занято"
                }
            
            # Double-check with Google Sheets to prevent race conditions (async)
            try:
                if not await self.sheets_service.is_slot_available_in_sheets_async(response.cosmetolog, booking_date, booking_time):
                    logger.warning(f"Message ID: {message_id} - Time slot not available in Google Sheets: specialist={response.cosmetolog}, date={booking_date}, time={booking_time}")
                    return {
                        "success": False,
                        "message": "Выбранное время уже занято"
                    }
            except Exception as sheets_check_error:
                logger.warning(f"Message ID: {message_id} - Could not verify slot availability in Google Sheets: {sheets_check_error}")
                # Continue with booking if sheets check fails
            
            # Create booking
            end_time = datetime.combine(booking_date, booking_time) + timedelta(minutes=30 * duration_slots)
            logger.info(f"Message ID: {message_id} - Creating new booking: client_id={client_id}, specialist={response.cosmetolog}")
            logger.info(f"Message ID: {message_id} -   Service: {response.procedure} ({duration_slots} slots)")
            logger.info(f"Message ID: {message_id} -   Time: {booking_date} {booking_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
            
            booking = Booking(
                project_id=self.project_config.project_id,
                specialist_name=response.cosmetolog,
                appointment_date=booking_date,
                appointment_time=booking_time,
                client_id=client_id,
                client_name=response.name,
                service_name=response.procedure,
                client_phone=response.phone,
                duration_minutes=duration_slots * 30,
                status="active"
            )
            
            self.db.add(booking)
            self.db.commit()
            self.db.refresh(booking)
            
            logger.info(f"Message ID: {message_id} - Booking created successfully: booking_id={booking.id}, client_id={client_id}")
            
            # Update Google Sheets - targeted update for this specific booking (async)
            try:
                logger.debug(f"Message ID: {message_id} - Updating specific booking slot {booking.id} in Google Sheets")
                sheets_success = await self.sheets_service.update_single_booking_slot_async(booking.specialist_name, booking)
                if sheets_success:
                    logger.debug(f"Message ID: {message_id} - Google Sheets slot update completed successfully")
                else:
                    logger.warning(f"Message ID: {message_id} - Google Sheets slot update returned false")
            except Exception as sheets_error:
                logger.error(f"Message ID: {message_id} - Failed to update booking slot in Google Sheets: {sheets_error}")
                # Don't fail the booking for sheets sync issues
            
            return {
                "success": True,
                "message": f"Запись создана: {response.cosmetolog}, {booking_date.strftime('%d.%m.%Y')} {booking_time.strftime('%H:%M')}",
                "booking_id": booking.id
            }
            
        except Exception as e:
            logger.error(f"Message ID: {message_id} - Error creating booking for client_id={client_id}: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Ошибка при создании записи: {str(e)}"
            }
    
    async def _reject_booking(self, response: ClaudeMainResponse, client_id: str, message_id: str) -> Dict[str, Any]:
        """Reject/cancel a booking"""
        try:
            # Validate required fields for rejection
            if not all([response.cosmetolog, response.time_reject, response.date_reject]):
                return {
                    "success": False,
                    "message": "Отсутствуют обязательные поля для отмены"
                }
            
            # Parse date and time
            booking_date = self._parse_date(response.date_reject)
            booking_time = self._parse_time(response.time_reject)
            
            if not booking_date or not booking_time:
                return {
                    "success": False,
                    "message": "Неверный формат даты или времени"
                }
            
            # Find booking to cancel
            booking = self.db.query(Booking).filter(
                and_(
                    Booking.project_id == self.project_config.project_id,
                    Booking.client_id == client_id,
                    Booking.specialist_name == response.cosmetolog,
                    Booking.appointment_date == booking_date,
                    Booking.appointment_time == booking_time,
                    Booking.status == "active"
                )
            ).first()
            
            if not booking:
                return {
                    "success": False,
                    "message": "Запись не найдена"
                }
            
            # Cancel booking
            booking.status = "cancelled"
            booking.updated_at = datetime.utcnow()
            self.db.commit()
            
            # Clear the specific booking slot in Google Sheets (with proper duration for multi-slot bookings)
            try:
                duration_slots = booking.duration_minutes // 30
                logger.debug(f"Message ID: {message_id} - Clearing booking slot in Google Sheets for {booking.specialist_name} ({duration_slots} slots)")
                sheets_success = await self.sheets_service.clear_booking_slot_async(
                    booking.specialist_name, 
                    booking.appointment_date, 
                    booking.appointment_time,
                    duration_slots
                )
                if sheets_success:
                    logger.debug(f"Message ID: {message_id} - Google Sheets slot cleared successfully")
                else:
                    logger.warning(f"Message ID: {message_id} - Google Sheets slot clearing returned false")
            except Exception as sheets_error:
                logger.error(f"Message ID: {message_id} - Failed to clear booking slot in Google Sheets: {sheets_error}")
                # Don't fail the cancellation for sheets issues
            
            return {
                "success": True,
                "message": f"Запись отменена: {response.cosmetolog}, {booking_date.strftime('%d.%m.%Y')} {booking_time.strftime('%H:%M')}",
                "booking_id": booking.id
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Ошибка при отмене записи: {str(e)}"
            }
    
    async def _change_booking(self, response: ClaudeMainResponse, client_id: str, message_id: str) -> Dict[str, Any]:
        """Change an existing booking"""
        try:
            # First, find the old booking to change
            old_bookings = self.db.query(Booking).filter(
                and_(
                    Booking.project_id == self.project_config.project_id,
                    Booking.client_id == client_id,
                    Booking.status == "active"
                )
            ).all()
            
            if not old_bookings:
                return {
                    "success": False,
                    "message": "Активная запись не найдена"
                }
            
            # Find the booking that matches the service being changed
            old_booking = None
            
            # First, try to find by service name if provided
            if response.procedure:
                matching_bookings = [b for b in old_bookings if response.procedure.lower() in b.service_name.lower()]
                if matching_bookings:
                    old_booking = sorted(matching_bookings, key=lambda x: x.created_at, reverse=True)[0]
                    logger.info(f"Message ID: {message_id} - Found booking by service match: {old_booking.service_name}")
            
            # If no service match found, try to find by date/time if provided in reject fields
            if not old_booking and response.date_reject and response.time_reject:
                try:
                    reject_date = self._parse_date(response.date_reject)
                    reject_time = self._parse_time(response.time_reject)
                    if reject_date and reject_time:
                        date_time_bookings = [b for b in old_bookings 
                                            if b.appointment_date == reject_date and b.appointment_time == reject_time]
                        if date_time_bookings:
                            old_booking = date_time_bookings[0]
                            logger.info(f"Message ID: {message_id} - Found booking by date/time match: {old_booking.appointment_date} {old_booking.appointment_time}")
                except Exception as e:
                    logger.warning(f"Message ID: {message_id} - Error parsing reject date/time: {e}")
            
            # Fallback to most recent booking if no specific match found
            if not old_booking:
                old_booking = sorted(old_bookings, key=lambda x: x.created_at, reverse=True)[0]
                logger.warning(f"Message ID: {message_id} - No specific booking match found, using most recent: {old_booking.service_name}")
            
            # Validate new booking data
            if not all([response.cosmetolog, response.time_set_up, response.date_order]):
                return {
                    "success": False,
                    "message": "Отсутствуют обязательные поля для изменения"
                }
            
            # Parse new date and time
            new_date = self._parse_date(response.date_order)
            new_time = self._parse_time(response.time_set_up)
            
            if not new_date or not new_time:
                return {
                    "success": False,
                    "message": "Неверный формат даты или времени"
                }
            
            # Check if specialist exists
            if response.cosmetolog not in self.project_config.specialists:
                return {
                    "success": False,
                    "message": f"Специалист {response.cosmetolog} не найден"
                }
            
            # Determine service duration
            duration_slots = 1
            if response.procedure and response.procedure in self.project_config.services:
                duration_slots = self.project_config.services[response.procedure]
            
            # Check if new time slot is available (excluding the current booking)
            if not self._is_slot_available(response.cosmetolog, new_date, new_time, duration_slots, exclude_booking_id=old_booking.id):
                return {
                    "success": False,
                    "message": "Выбранное время уже занято"
                }
            
            # Store old booking details for clearing the old slot
            old_specialist = old_booking.specialist_name
            old_date = old_booking.appointment_date
            old_time = old_booking.appointment_time
            old_duration_slots = old_booking.duration_minutes // 30  # Calculate slots from duration
            
            # Update the booking
            old_booking.specialist_name = response.cosmetolog
            old_booking.appointment_date = new_date
            old_booking.appointment_time = new_time
            old_booking.client_name = response.name or old_booking.client_name
            old_booking.service_name = response.procedure or old_booking.service_name
            old_booking.client_phone = response.phone or old_booking.client_phone
            old_booking.duration_minutes = duration_slots * 30
            old_booking.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            # Update Google Sheets - clear old slot and add new slot
            try:
                # Clear the old booking slot (with proper duration for multi-slot bookings)
                logger.debug(f"Message ID: {message_id} - Clearing old booking slot: {old_specialist} {old_date} {old_time} ({old_duration_slots} slots)")
                await self.sheets_service.clear_booking_slot_async(old_specialist, old_date, old_time, old_duration_slots)
                
                # Add the new booking slot
                logger.debug(f"Message ID: {message_id} - Adding new booking slot: {old_booking.specialist_name} {new_date} {new_time}")
                sheets_success = await self.sheets_service.update_single_booking_slot_async(old_booking.specialist_name, old_booking)
                if sheets_success:
                    logger.debug(f"Message ID: {message_id} - Google Sheets booking change completed successfully")
                else:
                    logger.warning(f"Message ID: {message_id} - Google Sheets booking change returned false")
            except Exception as sheets_error:
                logger.error(f"Message ID: {message_id} - Failed to update booking change in Google Sheets: {sheets_error}")
                # Don't fail the booking change for sheets issues
            
            return {
                "success": True,
                "message": f"Запись изменена: {response.cosmetolog}, {new_date.strftime('%d.%m.%Y')} {new_time.strftime('%H:%M')}",
                "booking_id": old_booking.id
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Ошибка при изменении записи: {str(e)}"
            }
    
    def _is_slot_available(self, specialist: str, booking_date: date, booking_time: time, duration_slots: int, exclude_booking_id: Optional[int] = None) -> bool:
        """Check if a time slot is available for booking"""
        # Generate all time slots that would be occupied
        occupied_slots = []
        for i in range(duration_slots):
            slot_datetime = datetime.combine(booking_date, booking_time) + timedelta(minutes=30*i)
            occupied_slots.append(slot_datetime.time())
        
        # Check for conflicts
        query = self.db.query(Booking).filter(
            and_(
                Booking.project_id == self.project_config.project_id,
                Booking.specialist_name == specialist,
                Booking.appointment_date == booking_date,
                Booking.status == "active"
            )
        )
        
        if exclude_booking_id:
            query = query.filter(Booking.id != exclude_booking_id)
        
        existing_bookings = query.all()
        
        for booking in existing_bookings:
            # Check if any of the required slots conflict with existing bookings
            booking_duration_slots = booking.duration_minutes // 30
            for i in range(booking_duration_slots):
                existing_slot = datetime.combine(booking_date, booking.appointment_time) + timedelta(minutes=30*i)
                if existing_slot.time() in occupied_slots:
                    return False
        
        return True
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string in various formats"""
        try:
            # Try DD.MM.YYYY format
            if len(date_str.split('.')) == 3:
                return datetime.strptime(date_str, "%d.%m.%Y").date()
            # Try DD.MM format (assume current year)
            elif len(date_str.split('.')) == 2:
                current_year = datetime.now().year
                return datetime.strptime(f"{date_str}.{current_year}", "%d.%m.%Y").date()
            return None
        except Exception:
            return None
    
    def _parse_time(self, time_str: str) -> Optional[time]:
        """Parse time string in HH:MM format"""
        try:
            return datetime.strptime(time_str, "%H:%M").time()
        except Exception:
            return None
    
    def get_client_bookings(self, client_id: str) -> List[BookingRecord]:
        """Get all bookings for a client"""
        bookings = self.db.query(Booking).filter(
            and_(
                Booking.project_id == self.project_config.project_id,
                Booking.client_id == client_id,
                Booking.status == "active"
            )
        ).all()
        
        return [
            BookingRecord(
                id=booking.id,
                project_id=booking.project_id,
                specialist_name=booking.specialist_name,
                date=booking.appointment_date,
                time=booking.appointment_time,
                client_id=booking.client_id,
                client_name=booking.client_name,
                service_name=booking.service_name,
                phone=booking.client_phone,
                duration_slots=booking.duration_minutes // 30,
                status=booking.status,
                created_at=booking.created_at,
                updated_at=booking.updated_at
            )
            for booking in bookings
        ]
    
    def get_client_bookings_as_string(self, client_id: str) -> str:
        """Get client bookings formatted as string for Claude"""
        bookings = self.get_client_bookings(client_id)
        
        if not bookings:
            return "У клиента нет активных записей"
        
        booking_strings = []
        for booking in bookings:
            booking_str = f"{booking.specialist_name} - {booking.date.strftime('%d.%m.%Y')} {booking.time.strftime('%H:%M')}"
            if booking.service_name:
                booking_str += f" ({booking.service_name})"
            booking_strings.append(booking_str)
        
        return "\n".join(booking_strings)
    
    def _save_feedback(self, response: ClaudeMainResponse, client_id: str, message_id: str) -> None:
        """Save client feedback"""
        try:
            logger.debug(f"Message ID: {message_id} - Creating feedback record for client_id={client_id}")
            feedback = Feedback(
                project_id=self.project_config.project_id,
                client_id=client_id,
                comment=response.feedback
            )
            
            self.db.add(feedback)
            self.db.commit()
            logger.info(f"Message ID: {message_id} - Feedback saved successfully for client_id={client_id}")
            
        except Exception as e:
            logger.error(f"Message ID: {message_id} - Error saving feedback for client_id={client_id}: {e}")
    
    def get_booking_stats(self) -> Dict[str, Any]:
        """Get booking statistics for the project"""
        total_bookings = self.db.query(Booking).filter(
            Booking.project_id == self.project_config.project_id
        ).count()
        
        active_bookings = self.db.query(Booking).filter(
            and_(
                Booking.project_id == self.project_config.project_id,
                Booking.status == "active"
            )
        ).count()
        
        cancelled_bookings = self.db.query(Booking).filter(
            and_(
                Booking.project_id == self.project_config.project_id,
                Booking.status == "cancelled"
            )
        ).count()
        
        return {
            "total_bookings": total_bookings,
            "active_bookings": active_bookings,
            "cancelled_bookings": cancelled_bookings,
            "specialists": self.project_config.specialists,
            "services": self.project_config.services
        } 
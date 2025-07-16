import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any, Optional
from datetime import datetime, date, time, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import logging

from ..config import settings, ProjectConfig
from ..models import BookingRecord, AvailableSlots
from ..database import Booking

logger = logging.getLogger(__name__)


class GoogleSheetsService:
    """Service for Google Sheets integration"""
    
    def __init__(self, project_config: ProjectConfig):
        self.project_config = project_config
        logger.debug(f"Initializing GoogleSheetsService for project {project_config.project_id}")
        
        try:
            self.client = self._get_sheets_client()
            logger.debug("Google Sheets client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {e}")
            self.client = None
        
        self.spreadsheet = None
        
        if self.client and project_config.google_sheet_id:
            try:
                logger.debug(f"Opening spreadsheet: {project_config.google_sheet_id}")
                self.spreadsheet = self.client.open_by_key(project_config.google_sheet_id)
                logger.info(f"Successfully connected to Google Spreadsheet: {self.spreadsheet.title}")
            except Exception as e:
                logger.error(f"Failed to open spreadsheet {project_config.google_sheet_id}: {e}")
                self.spreadsheet = None
        elif not project_config.google_sheet_id:
            logger.warning("No Google Sheet ID configured for this project")
        else:
            logger.warning("Google Sheets client not available, skipping spreadsheet connection")
    
    def _get_sheets_client(self) -> gspread.Client:
        """Initialize Google Sheets client"""
        logger.debug(f"Loading Google credentials from: {settings.google_credentials_file}")
        
        try:
            credentials = Credentials.from_service_account_file(
                settings.google_credentials_file,
                scopes=settings.google_sheets_scopes
            )
            client = gspread.authorize(credentials)
            logger.debug("Google Sheets client authorized successfully")
            return client
        except Exception as e:
            logger.error(f"Failed to create Google Sheets client: {e}")
            raise
    
    def sync_bookings_to_sheets(self, db: Session) -> bool:
        """Sync all bookings from database to Google Sheets"""
        if not self.spreadsheet:
            logger.warning("Cannot sync bookings: no spreadsheet connection")
            return False
        
        logger.info(f"Starting booking sync to Google Sheets for project {self.project_config.project_id}")
        
        try:
            # Get all active bookings for this project
            bookings = db.query(Booking).filter(
                and_(
                    Booking.project_id == self.project_config.project_id,
                    Booking.status == "active"
                )
            ).all()
            
            logger.info(f"Found {len(bookings)} active bookings to sync")
            
            if not bookings:
                logger.debug("No active bookings to sync")
                return True
            
            # Group bookings by specialist
            bookings_by_specialist = {}
            for booking in bookings:
                if booking.specialist_name not in bookings_by_specialist:
                    bookings_by_specialist[booking.specialist_name] = []
                bookings_by_specialist[booking.specialist_name].append(booking)
            
            logger.debug(f"Bookings grouped by specialist: {list(bookings_by_specialist.keys())}")
            
            # Update each specialist's worksheet
            sync_success = True
            for specialist_name, specialist_bookings in bookings_by_specialist.items():
                try:
                    logger.debug(f"Syncing {len(specialist_bookings)} bookings for specialist: {specialist_name}")
                    self._update_specialist_worksheet(specialist_name, specialist_bookings)
                    logger.debug(f"Successfully synced bookings for specialist: {specialist_name}")
                except Exception as specialist_error:
                    logger.error(f"Failed to sync bookings for specialist {specialist_name}: {specialist_error}")
                    sync_success = False
            
            if sync_success:
                logger.info("All bookings synced to Google Sheets successfully")
            else:
                logger.warning("Some bookings failed to sync to Google Sheets")
            
            return sync_success
            
        except Exception as e:
            logger.error(f"Error syncing bookings to sheets: {e}", exc_info=True)
            return False
    
    def _update_specialist_worksheet(self, specialist_name: str, bookings: List[Booking]) -> None:
        """Update a specific specialist's worksheet"""
        try:
            # Get or create worksheet for specialist
            try:
                worksheet = self.spreadsheet.worksheet(specialist_name)
            except gspread.WorksheetNotFound:
                worksheet = self.spreadsheet.add_worksheet(
                    title=specialist_name,
                    rows=1000,
                    cols=10
                )
                self._setup_worksheet_headers(worksheet)
            
            # Clear existing data (keep headers)
            worksheet.clear()
            self._setup_worksheet_headers(worksheet)
            
            # Generate time slots and fill bookings
            self._fill_worksheet_with_bookings(worksheet, bookings)
            
        except Exception as e:
            logger.error(f"Error updating worksheet for {specialist_name}: {e}", exc_info=True)
    
    def _setup_worksheet_headers(self, worksheet) -> None:
        """Setup worksheet column headers"""
        headers = [
            "Дата (ДД.ММ)",      # A
            "Дата (ДД.ММ.ГГГГ)",  # B
            "Время",              # C
            "ID клиента",         # D
            "Имя",               # E
            "Услуга"             # F
        ]
        worksheet.update('A1:F1', [headers])
    
    def _fill_worksheet_with_bookings(self, worksheet, bookings: List[Booking]) -> None:
        """Fill worksheet with booking data"""
        # Group bookings by date
        bookings_by_date = {}
        for booking in bookings:
            date_key = booking.date
            if date_key not in bookings_by_date:
                bookings_by_date[date_key] = []
            bookings_by_date[date_key].append(booking)
        
        # Sort dates
        sorted_dates = sorted(bookings_by_date.keys())
        
        row = 2  # Start from row 2 (after headers)
        
        for current_date in sorted_dates:
            date_bookings = bookings_by_date[current_date]
            date_bookings.sort(key=lambda b: b.time)
            
            # Generate time slots for the day
            work_start = datetime.strptime(self.project_config.work_hours["start"], "%H:%M").time()
            work_end = datetime.strptime(self.project_config.work_hours["end"], "%H:%M").time()
            
            current_time = datetime.combine(current_date, work_start)
            end_time = datetime.combine(current_date, work_end)
            
            booking_dict = {booking.time: booking for booking in date_bookings}
            
            # First row of the day - show date in format DD.MM
            first_row_of_day = True
            
            while current_time < end_time:
                slot_time = current_time.time()
                
                # Check if this slot has a booking
                booking = booking_dict.get(slot_time)
                
                if booking:
                    # Fill with booking data
                    row_data = [
                        current_date.strftime("%d.%m") if first_row_of_day else "",  # A
                        current_date.strftime("%d.%m.%Y"),                          # B
                        slot_time.strftime("%H:%M"),                               # C
                        booking.client_id,                                         # D
                        booking.client_name or "",                                 # E
                        booking.service_name or ""                                 # F
                    ]
                    
                    # Fill additional slots for multi-slot bookings
                    for i in range(booking.duration_slots):
                        if i == 0:
                            worksheet.update(f'A{row}:F{row}', [row_data])
                        else:
                            # Fill subsequent slots with dashes
                            dash_row = ["", current_date.strftime("%d.%m.%Y"), 
                                       (current_time + timedelta(minutes=30*i)).strftime("%H:%M"),
                                       "-", "-", "-"]
                            worksheet.update(f'A{row}:F{row}', [dash_row])
                        row += 1
                    
                    # Skip the additional slots in the loop
                    current_time += timedelta(minutes=30 * booking.duration_slots)
                else:
                    # Empty slot
                    row_data = [
                        current_date.strftime("%d.%m") if first_row_of_day else "",  # A
                        current_date.strftime("%d.%m.%Y"),                          # B
                        slot_time.strftime("%H:%M"),                               # C
                        "",                                                        # D
                        "",                                                        # E
                        ""                                                         # F
                    ]
                    worksheet.update(f'A{row}:F{row}', [row_data])
                    row += 1
                    current_time += timedelta(minutes=30)
                
                first_row_of_day = False
    
    def get_available_slots(self, db: Session, target_date: date, time_fraction: int) -> AvailableSlots:
        """Get available slots for a specific date"""
        # Get all bookings for the date
        bookings = db.query(Booking).filter(
            and_(
                Booking.project_id == self.project_config.project_id,
                Booking.date == target_date,
                Booking.status == "active"
            )
        ).all()
        
        # Group bookings by specialist
        bookings_by_specialist = {}
        for booking in bookings:
            if booking.specialist_name not in bookings_by_specialist:
                bookings_by_specialist[booking.specialist_name] = []
            bookings_by_specialist[booking.specialist_name].append(booking)
        
        # Generate available slots for each specialist
        available_slots = {}
        
        for specialist in self.project_config.specialists:
            specialist_bookings = bookings_by_specialist.get(specialist, [])
            slots = self._get_available_slots_for_specialist(
                specialist_bookings, target_date, time_fraction
            )
            available_slots[f"available_slots_{specialist.lower()}"] = slots
        
        return AvailableSlots(
            date_of_checking=target_date.strftime("%d.%m"),
            slots_by_specialist=available_slots
        )
    
    def get_available_slots_by_time_range(
        self, 
        db: Session, 
        start_time: time, 
        end_time: time, 
        time_fraction: int,
        days_ahead: int = 7
    ) -> AvailableSlots:
        """Get available slots within time range for next N days"""
        all_slots = {}
        
        # Check each day for the next week
        for day_offset in range(days_ahead):
            check_date = date.today() + timedelta(days=day_offset)
            
            # Get bookings for this date
            bookings = db.query(Booking).filter(
                and_(
                    Booking.project_id == self.project_config.project_id,
                    Booking.date == check_date,
                    Booking.status == "active"
                )
            ).all()
            
            # Group by specialist
            bookings_by_specialist = {}
            for booking in bookings:
                if booking.specialist_name not in bookings_by_specialist:
                    bookings_by_specialist[booking.specialist_name] = []
                bookings_by_specialist[booking.specialist_name].append(booking)
            
            # Check each specialist
            for specialist in self.project_config.specialists:
                specialist_key = f"available_slots_{specialist.lower()}"
                if specialist_key not in all_slots:
                    all_slots[specialist_key] = []
                
                specialist_bookings = bookings_by_specialist.get(specialist, [])
                slots = self._get_available_slots_for_specialist_in_time_range(
                    specialist_bookings, check_date, start_time, end_time, time_fraction
                )
                
                for slot in slots:
                    all_slots[specialist_key].append(f"{check_date.strftime('%d.%m')} {slot}")
        
        # Keep as list format (no need to join)
        formatted_slots = {}
        for specialist_key, slots in all_slots.items():
            formatted_slots[specialist_key] = slots
        
        return AvailableSlots(
            date_of_checking=date.today().strftime("%d.%m"),
            slots_by_specialist=formatted_slots
        )
    
    def _get_available_slots_for_specialist(
        self, 
        bookings: List[Booking], 
        target_date: date, 
        time_fraction: int
    ) -> List[str]:
        """Get available slots for a specific specialist on a specific date"""
        work_start = datetime.strptime(self.project_config.work_hours["start"], "%H:%M").time()
        work_end = datetime.strptime(self.project_config.work_hours["end"], "%H:%M").time()
        
        # Create set of occupied time slots
        occupied_slots = set()
        for booking in bookings:
            booking_time = datetime.combine(target_date, booking.time)
            for i in range(booking.duration_slots):
                slot_time = (booking_time + timedelta(minutes=30*i)).time()
                occupied_slots.add(slot_time)
        
        # Generate available slots
        available_slots = []
        current_time = datetime.combine(target_date, work_start)
        end_time = datetime.combine(target_date, work_end)
        
        while current_time + timedelta(minutes=30 * time_fraction) <= end_time:
            slot_time = current_time.time()
            
            # Check if this slot and required consecutive slots are free
            is_available = True
            for i in range(time_fraction):
                check_time = (current_time + timedelta(minutes=30*i)).time()
                if check_time in occupied_slots:
                    is_available = False
                    break
            
            if is_available:
                available_slots.append(slot_time.strftime("%H:%M"))
            
            current_time += timedelta(minutes=30)
        
        return available_slots
    
    def _get_available_slots_for_specialist_in_time_range(
        self, 
        bookings: List[Booking], 
        target_date: date, 
        start_time: time, 
        end_time: time, 
        time_fraction: int
    ) -> List[str]:
        """Get available slots for specialist within specific time range"""
        work_start = max(
            datetime.strptime(self.project_config.work_hours["start"], "%H:%M").time(),
            start_time
        )
        work_end = min(
            datetime.strptime(self.project_config.work_hours["end"], "%H:%M").time(),
            end_time
        )
        
        # Create set of occupied time slots
        occupied_slots = set()
        for booking in bookings:
            booking_time = datetime.combine(target_date, booking.time)
            for i in range(booking.duration_slots):
                slot_time = (booking_time + timedelta(minutes=30*i)).time()
                occupied_slots.add(slot_time)
        
        # Generate available slots within time range
        available_slots = []
        current_time = datetime.combine(target_date, work_start)
        end_datetime = datetime.combine(target_date, work_end)
        
        while current_time + timedelta(minutes=30 * time_fraction) <= end_datetime:
            slot_time = current_time.time()
            
            # Check if this slot and required consecutive slots are free
            is_available = True
            for i in range(time_fraction):
                check_time = (current_time + timedelta(minutes=30*i)).time()
                if check_time in occupied_slots:
                    is_available = False
                    break
            
            if is_available:
                available_slots.append(slot_time.strftime("%H:%M"))
            
            current_time += timedelta(minutes=30)
        
        return available_slots
    
    def create_dialogue_document(self, client_id: str, project_id: str) -> Optional[str]:
        """Create Google Doc for dialogue storage"""
        try:
            # This would use Google Drive API to create a document
            # For now, return placeholder
            return f"doc_id_for_{project_id}_{client_id}"
        except Exception as e:
            logger.error(f"Error creating dialogue document: {e}", exc_info=True)
            return None 

    def update_single_booking_slot(self, specialist_name: str, booking: Booking) -> bool:
        """Update only the specific row for a single booking without clearing the table"""
        if not self.spreadsheet:
            logger.warning("Cannot update booking slot: no spreadsheet connection")
            return False
        
        logger.info(f"Updating single booking slot for {specialist_name}: {booking.date} {booking.time}")
        
        try:
            # Get or create worksheet for specialist
            try:
                worksheet = self.spreadsheet.worksheet(specialist_name)
            except gspread.WorksheetNotFound:
                logger.info(f"Creating new worksheet for specialist: {specialist_name}")
                worksheet = self.spreadsheet.add_worksheet(
                    title=specialist_name,
                    rows=1000,
                    cols=10
                )
                self._setup_worksheet_static_structure(worksheet)
            
            # Find the correct row for this time slot
            target_row = self._find_row_for_time_slot(worksheet, booking.date, booking.time)
            
            if target_row:
                # Update only the booking data columns (D, E, F)
                booking_data = [
                    booking.client_id or "",           # D
                    booking.client_name or "",         # E
                    booking.service_name or ""         # F
                ]
                
                # Update only columns D, E, F for this specific row
                range_update = f'D{target_row}:F{target_row}'
                worksheet.update(range_update, [booking_data])
                
                # If this is a multi-slot booking, fill additional rows with dashes
                if booking.duration_slots > 1:
                    logger.info(f"Booking requires {booking.duration_slots} slots, filling additional {booking.duration_slots - 1} rows with dashes")
                    for i in range(1, booking.duration_slots):
                        additional_row = target_row + i
                        dash_data = ["-", "-", "-"]  # D, E, F columns
                        dash_range = f'D{additional_row}:F{additional_row}'
                        worksheet.update(dash_range, [dash_data])
                        logger.debug(f"  Filled row {additional_row} with dashes for multi-slot booking")
                
                logger.info(f"Successfully updated booking slot(s) starting at row {target_row} for {specialist_name} ({booking.duration_slots} slots total)")
                return True
            else:
                logger.error(f"Could not find row for time slot {booking.time} on {booking.date}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating single booking slot for {specialist_name}: {e}", exc_info=True)
            return False

    def clear_booking_slot(self, specialist_name: str, booking_date: date, booking_time: time) -> bool:
        """Clear a specific booking slot (for cancellations)"""
        if not self.spreadsheet:
            logger.warning("Cannot clear booking slot: no spreadsheet connection")
            return False
        
        logger.info(f"Clearing booking slot for {specialist_name}: {booking_date} {booking_time}")
        
        try:
            # Get worksheet for specialist
            try:
                worksheet = self.spreadsheet.worksheet(specialist_name)
            except gspread.WorksheetNotFound:
                logger.warning(f"Worksheet not found for specialist: {specialist_name}")
                return False
            
            # Find the correct row for this time slot
            target_row = self._find_row_for_time_slot(worksheet, booking_date, booking_time)
            
            if target_row:
                # Clear booking data columns (D, E, F)
                empty_data = ["", "", ""]  # Empty client_id, name, service
                
                # Update only columns D, E, F for this specific row
                range_update = f'D{target_row}:F{target_row}'
                worksheet.update(range_update, [empty_data])
                
                logger.info(f"Successfully cleared booking slot at row {target_row} for {specialist_name}")
                return True
            else:
                logger.error(f"Could not find row for time slot {booking_time} on {booking_date}")
                return False
                
        except Exception as e:
            logger.error(f"Error clearing booking slot for {specialist_name}: {e}", exc_info=True)
            return False

    def is_slot_available_in_sheets(self, specialist_name: str, booking_date: date, booking_time: time) -> bool:
        """Check if a time slot is available by reading directly from Google Sheets"""
        if not self.spreadsheet:
            logger.warning("Cannot check slot availability: no spreadsheet connection")
            return False
        
        logger.debug(f"Checking slot availability in sheets for {specialist_name}: {booking_date} {booking_time}")
        
        try:
            # Get worksheet for specialist
            try:
                worksheet = self.spreadsheet.worksheet(specialist_name)
            except gspread.WorksheetNotFound:
                logger.debug(f"Worksheet not found for specialist {specialist_name}, slot is available")
                return True  # If no worksheet exists, slot is available
            
            # Find the correct row for this time slot
            target_row = self._find_row_for_time_slot(worksheet, booking_date, booking_time)
            
            if target_row:
                # Check if client_id column (D) is empty
                client_id_cell = worksheet.cell(target_row, 4).value  # Column D
                is_available = not client_id_cell or client_id_cell.strip() == ""
                
                logger.debug(f"Slot availability check result: {is_available} (client_id: '{client_id_cell}')")
                return is_available
            else:
                logger.warning(f"Time slot not found in sheets structure: {booking_date} {booking_time}")
                return False
                
        except Exception as e:
            logger.error(f"Error checking slot availability in sheets: {e}", exc_info=True)
            return False  # Assume not available on error to be safe

    def _find_row_for_time_slot(self, worksheet, target_date: date, target_time: time) -> Optional[int]:
        """Find the row number for a specific date and time slot"""
        try:
            # Get all data from columns B and C (full date and time)
            date_column = worksheet.col_values(2)  # Column B: DD.MM.YYYY
            time_column = worksheet.col_values(3)  # Column C: HH:MM
            
            target_date_str = target_date.strftime("%d.%m.%Y")
            target_time_str = target_time.strftime("%H:%M")
            
            # Find matching row (starting from row 2, since row 1 is headers)
            for i, (date_val, time_val) in enumerate(zip(date_column[1:], time_column[1:]), start=2):
                if date_val == target_date_str and time_val == target_time_str:
                    logger.debug(f"Found matching slot at row {i}: {date_val} {time_val}")
                    return i
            
            logger.warning(f"No matching row found for {target_date_str} {target_time_str}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding row for time slot: {e}")
            return None

    def _setup_worksheet_static_structure(self, worksheet) -> None:
        """Setup worksheet with static structure (headers + time slots) that won't be cleared"""
        logger.info("Setting up static worksheet structure")
        
        # Setup headers
        headers = [
            "Дата (ДД.ММ)",      # A
            "Дата (ДД.ММ.ГГГГ)",  # B
            "Время",              # C
            "ID клиента",         # D
            "Имя",               # E
            "Услуга"             # F
        ]
        worksheet.update('A1:F1', [headers])
        
        # Generate time slots for the next 30 days
        from datetime import datetime, timedelta
        
        start_date = datetime.now().date()
        end_date = start_date + timedelta(days=30)
        
        # Work hours: 9:00 to 17:30 in 30-minute intervals
        work_start = time(9, 0)
        work_end = time(17, 30)
        
        rows_data = []
        current_date = start_date
        
        while current_date <= end_date:
            # Skip weekends if needed (can be configured later)
            current_time = datetime.combine(current_date, work_start)
            end_time = datetime.combine(current_date, work_end)
            
            first_row_of_day = True
            
            while current_time <= end_time:
                slot_time = current_time.time()
                
                row_data = [
                    current_date.strftime("%d.%m") if first_row_of_day else "",  # A
                    current_date.strftime("%d.%m.%Y"),                          # B
                    slot_time.strftime("%H:%M"),                               # C
                    "",                                                         # D (empty for client_id)
                    "",                                                         # E (empty for client_name)
                    ""                                                          # F (empty for service)
                ]
                
                rows_data.append(row_data)
                first_row_of_day = False
                current_time += timedelta(minutes=30)
            
            current_date += timedelta(days=1)
        
        # Batch update all rows at once
        if rows_data:
            range_str = f'A2:F{len(rows_data) + 1}'
            worksheet.update(range_str, rows_data)
            logger.info(f"Created static structure with {len(rows_data)} time slots") 
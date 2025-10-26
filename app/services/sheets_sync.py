"""
Сервис синхронизации данных между Google Sheets и локальной БД
"""
import logging
from datetime import datetime, date, time
from typing import Optional, Dict, Any
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class SheetsSyncService:
    def __init__(self, db: Session):
        self.db = db
    
    def parse_sheet_update(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Парсит данные из webhook и определяет тип изменения
        """
        try:
            sheet_name = data.get('sheetName', '')
            row = data.get('row')
            column = data.get('column')
            value = data.get('value', '')
            
            # Определяем специалиста по имени листа
            specialist = sheet_name
            
            # Парсим дату из первых двух колонок (A - дата DD.MM, B - полная дата)
            # Предполагаем структуру: A=дата, B=полная дата, C и далее - временные слоты
            
            # Для примера, пока простая логика
            # TODO: Добавить полный парсинг в зависимости от колонки
            
            result = {
                'specialist': specialist,
                'sheet_row': row,
                'sheet_column': column,
                'sheet_name': sheet_name,
                'value': value
            }
            
            logger.info(f"Parsed sheet update: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing sheet update: {e}")
            return None
    
    def update_sheets_slot(self, slot_data: Dict[str, Any]) -> bool:
        """
        Обновляет или создает запись в таблице sheets_slots
        """
        try:
            # Проверяем существует ли запись
            check_query = text("""
                SELECT id FROM sheets_slots 
                WHERE sheet_name = :sheet_name 
                AND sheet_row = :sheet_row 
                AND sheet_column = :sheet_column
            """)
            
            existing = self.db.execute(check_query, {
                'sheet_name': slot_data['sheet_name'],
                'sheet_row': slot_data['sheet_row'],
                'sheet_column': slot_data['sheet_column']
            }).fetchone()
            
            if existing:
                # Обновляем существующую запись
                update_query = text("""
                    UPDATE sheets_slots 
                    SET specialist = :specialist,
                        client_name = :value,
                        last_sync = NOW(),
                        version = version + 1
                    WHERE id = :id
                """)
                self.db.execute(update_query, {
                    'specialist': slot_data['specialist'],
                    'value': slot_data['value'],
                    'id': existing.id
                })
            else:
                # Создаем новую запись
                insert_query = text("""
                    INSERT INTO sheets_slots 
                    (specialist, sheet_row, sheet_column, sheet_name, client_name, last_sync)
                    VALUES (:specialist, :sheet_row, :sheet_column, :sheet_name, :value, NOW())
                """)
                self.db.execute(insert_query, slot_data)
            
            self.db.commit()
            logger.info(f"Updated sheets_slot: {slot_data}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating sheets_slot: {e}")
            self.db.rollback()
            return False
    
    def update_specific_column(self, sheet_name: str, row: int, column: int, value: str) -> bool:
        """
        Обновляет конкретную колонку в sheets_slots
        Колонки: 4=D(client_id), 5=E(client_name), 6=F(service)
        Если value пустое для client_id - это означает удаление записи
        """
        try:
            column_mapping = {
                4: 'client_id',    # D
                5: 'client_name',  # E  
                6: 'service'       # F
            }
            
            if column not in column_mapping:
                logger.info(f"Column {column} not tracked for updates")
                return True
            
            field = column_mapping[column]
            
            # Проверяем, это удаление записи?
            if field == 'client_id' and (not value or value == '-'):
                logger.info(f"[DELETE] Clearing booking at row {row}")
                
                # Очищаем все поля записи
                clear_query = text("""
                    UPDATE sheets_slots 
                    SET client_id = NULL, 
                        client_name = NULL, 
                        service = NULL,
                        last_sync = NOW(),
                        version = version + 1
                    WHERE sheet_name = :sheet_name 
                    AND sheet_row = :row
                """)
                
                self.db.execute(clear_query, {
                    'sheet_name': sheet_name,
                    'row': row
                })
                
                # Также удаляем из bookings если есть
                slot_data = self.db.execute(text("""
                    SELECT specialist, date, time 
                    FROM sheets_slots 
                    WHERE sheet_name = :sheet_name 
                    AND sheet_row = :row
                """), {'sheet_name': sheet_name, 'row': row}).fetchone()
                
                if slot_data:
                    from app.database import Booking
                    deleted_count = self.db.query(Booking).filter(
                        Booking.specialist_name == slot_data.specialist,
                        Booking.appointment_date == slot_data.date,
                        Booking.appointment_time == slot_data.time
                    ).delete()
                    
                    if deleted_count > 0:
                        logger.info(f"[DELETE] Removed {deleted_count} booking(s) from DB")
                
            else:
                # Обычное обновление поля
                update_query = text(f"""
                    UPDATE sheets_slots 
                    SET {field} = :value,
                        last_sync = NOW(),
                        version = version + 1
                    WHERE sheet_name = :sheet_name 
                    AND sheet_row = :row
                """)
                
                self.db.execute(update_query, {
                    'value': value if value else None,
                    'sheet_name': sheet_name,
                    'row': row
                })
            
            self.db.commit()
            logger.info(f"Updated {field} for row {row}: '{value}'")
            return True
            
        except Exception as e:
            logger.error(f"Error updating column: {e}")
            self.db.rollback()
            return False

async def run_sheets_background_sync(project_config):
    """
    Фоновая синхронизация Google Sheets → БД (каждые 5 минут)
    Резервный механизм на случай если webhook не сработал
    """
    import asyncio
    import gspread
    from google.oauth2.service_account import Credentials
    from datetime import datetime
    from sqlalchemy import text
    from app.database import SessionLocal
    
    logger.info("[SYNC] Starting Google Sheets → DB background sync task")
    
    while True:
        try:
            await asyncio.sleep(300)  # Ждем 5 минут
            
            logger.info("[SYNC] Running scheduled Sheets → DB synchronization")
            
            db = SessionLocal()
            try:
                # Подключаемся к Google Sheets
                SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
                creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
                client = gspread.authorize(creds)
                spreadsheet = client.open_by_key(project_config.google_sheet_id)
                
                updated_count = 0
                
                # Обрабатываем каждого специалиста
                for specialist_name in project_config.specialists:
                    try:
                        sheet = spreadsheet.worksheet(specialist_name)
                        all_values = sheet.get_all_values()
                        
                        # Пропускаем заголовки, начинаем с 3 строки
                        for row_idx, row in enumerate(all_values[2:], start=3):
                            if len(row) >= 6:
                                # Обновляем только если есть изменения в клиентских данных
                                client_id = '-CONTINUATION-' if row[3] == '-' else (row[3] if row[3] else None)
                                client_name = row[4] if row[4] else None
                                service = row[5] if row[5] else None
                                
                                query = text("""
                                    UPDATE sheets_slots 
                                    SET client_id = :client_id,
                                        client_name = :client_name,
                                        service = :service,
                                        last_sync = NOW()
                                    WHERE sheet_name = :sheet_name 
                                    AND sheet_row = :row
                                    AND (client_id IS DISTINCT FROM :client_id
                                         OR client_name IS DISTINCT FROM :client_name
                                         OR service IS DISTINCT FROM :service)
                                """)
                                
                                result = db.execute(query, {
                                    'client_id': client_id,
                                    'client_name': client_name,
                                    'service': service,
                                    'sheet_name': specialist_name,
                                    'row': row_idx
                                })
                                
                                if result.rowcount > 0:
                                    updated_count += 1
                        
                        db.commit()
                        
                    except Exception as e:
                        logger.error(f"[SYNC] Error syncing {specialist_name}: {e}")
                        db.rollback()
                
                if updated_count > 0:
                    logger.info(f"[SYNC] Updated {updated_count} slots from Google Sheets")
                else:
                    logger.debug("[SYNC] No changes detected in Google Sheets")
                    
            except Exception as e:
                logger.error(f"[SYNC] Error connecting to Google Sheets: {e}")
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"[SYNC] Background sync error: {e}")
            await asyncio.sleep(60)  # При ошибке ждем минуту

    def resolve_conflict(self, sheet_data, db_data):
        """
        Разрешает конфликты между Google Sheets и БД
        ПРИОРИТЕТ: Google Sheets (источник истины)
        """
        # Google Sheets ВСЕГДА имеет приоритет
        if sheet_data != db_data:
            logger.warning(f"[CONFLICT] Detected mismatch - Sheet: {sheet_data}, DB: {db_data}")
            logger.info(f"[CONFLICT] Applying Google Sheets data (has priority)")
            return sheet_data
        return db_data

    async def verify_consistency(self):
        """
        Проверяет консистентность данных между Sheets и БД
        При несоответствии - данные из Sheets перезаписывают БД
        """
        try:
            # Получаем случайную выборку для проверки
            sample_slots = self.db.execute(text("""
                SELECT sheet_name, sheet_row, date, time, client_id 
                FROM sheets_slots 
                WHERE client_id IS NOT NULL 
                ORDER BY RANDOM() 
                LIMIT 10
            """)).fetchall()
            
            conflicts_found = 0
            for slot in sample_slots:
                # Здесь должна быть проверка с реальными данными из Sheets
                # Для production нужно добавить вызов Google Sheets API
                pass
                
            if conflicts_found > 0:
                logger.warning(f"[CONSISTENCY] Found {conflicts_found} conflicts, Google Sheets data applied")
                
        except Exception as e:
            logger.error(f"[CONSISTENCY] Error checking consistency: {e}")

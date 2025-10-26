#!/usr/bin/env python3
"""
Скрипт для начальной загрузки всех данных из Google Sheets в локальную БД
"""
import os
import sys
import gspread
from datetime import datetime, date
from dotenv import load_dotenv
import json

sys.path.append('/root/fastapi_ai_service')

from telegram.database import SessionLocal
from telegram.config import ProjectConfig, settings
from sqlalchemy import text
from google.oauth2.service_account import Credentials
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def get_sheets_client():
    """Создает клиент для Google Sheets"""
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
    return gspread.authorize(creds)

def migrate_sheets_to_db():
    """Загружает все текущие записи из Google Sheets в БД"""
    
    # Загружаем конфигурацию из local_config.json
    with open('local_config.json', 'r') as f:
        config_data = json.load(f)
    
    # Создаем конфиг проекта
    default_config = ProjectConfig("default")
    if "default" in config_data:
        default_config.specialists = config_data["default"].get("specialists", [])
        default_config.services = config_data["default"].get("services", {})
    
    db = SessionLocal()
    
    try:
        logger.info("Starting migration from Google Sheets to DB...")
        
        # Подключаемся к Google Sheets
        client = get_sheets_client()
        spreadsheet = client.open_by_key(default_config.google_sheet_id)
        
        # Очищаем старые данные
        db.execute(text("TRUNCATE TABLE sheets_slots RESTART IDENTITY CASCADE"))
        db.commit()
        logger.info("Cleared old data from sheets_slots")
        
        # Получаем список всех специалистов
        specialists = default_config.specialists
        logger.info(f"Found {len(specialists)} specialists: {specialists}")
        
        total_slots = 0
        
        # Для каждого специалиста загружаем данные
        for specialist in specialists:
            logger.info(f"Processing specialist: {specialist}")
            
            try:
                worksheet = spreadsheet.worksheet(specialist)
                all_values = worksheet.get_all_values()
                
                # Пропускаем заголовок если есть
                start_row = 1 if all_values and all_values[0][0] == 'Дата' else 0
                
                for row_idx, row in enumerate(all_values[start_row:], start=start_row+1):
                    if len(row) >= 3:  # Минимум дата, полная дата, время
                        slot_date = row[0] if len(row) > 0 else ''
                        full_date = row[1] if len(row) > 1 else ''
                        slot_time = row[2] if len(row) > 2 else ''
                        client_id = '-CONTINUATION-' if row[3] == '-' else (row[3] if len(row) > 3 else '')
                        client_name = row[4] if len(row) > 4 else ''
                        service = row[5] if len(row) > 5 else ''
                        
                        # Парсим дату
                        parsed_date = None
                        if full_date:
                            try:
                                parsed_date = datetime.strptime(full_date, "%d.%m.%Y").date()
                            except:
                                pass
                        
                        # Парсим время
                        parsed_time = None
                        if slot_time:
                            try:
                                parsed_time = datetime.strptime(slot_time, "%H:%M").time()
                            except:
                                pass
                        
                        # Сохраняем в БД только если есть дата и время
                        if parsed_date and parsed_time:
                            insert_query = text("""
                                INSERT INTO sheets_slots 
                                (specialist, date, time, client_id, client_name, service, 
                                 sheet_row, sheet_column, sheet_name, last_sync)
                                VALUES (:specialist, :date, :time, :client_id, :client_name, :service,
                                        :sheet_row, :sheet_column, :sheet_name, NOW())
                            """)
                            
                            db.execute(insert_query, {
                                'specialist': specialist,
                                'date': parsed_date,
                                'time': parsed_time,
                                'client_id': client_id if client_id else None,
                                'client_name': client_name or None,
                                'service': service or None,
                                'sheet_row': row_idx,
                                'sheet_column': 'A-G',
                                'sheet_name': specialist
                            })
                            total_slots += 1
                
                db.commit()
                logger.info(f"  - Loaded {len(all_values)-start_row} rows for {specialist}")
                
            except Exception as e:
                logger.error(f"  - Error loading data for {specialist}: {e}")
                db.rollback()
        
        logger.info(f"Migration completed! Total slots loaded: {total_slots}")
        
        # Показываем статистику
        result = db.execute(text("SELECT COUNT(*) as total, COUNT(DISTINCT specialist) as specialists FROM sheets_slots")).fetchone()
        logger.info(f"Database now contains: {result.total} slots for {result.specialists} specialists")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    load_dotenv()
    migrate_sheets_to_db()

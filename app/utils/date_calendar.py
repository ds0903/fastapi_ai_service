from datetime import datetime, timedelta
from typing import Dict
import logging

logger = logging.getLogger(__name__)

# Русские названия дней недели
WEEKDAY_NAMES_RU = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье"
}

def generate_calendar_for_claude(start_date: datetime, days_ahead: int = 30) -> str:
    """
    Генерирует календарь на указанное количество дней вперед.
    Сегодняшний день помечается как "(Сегодня)".
    
    Args:
        start_date: Начальная дата (обычно текущая дата)
        days_ahead: Количество дней вперед (по умолчанию 30)
    
    Returns:
        Отформатированная строка календаря для передачи Claude
        
    Пример вывода:
        10.10.2025 - Пятница (Сегодня)
        11.10.2025 - Суббота
        12.10.2025 - Воскресенье
        ...
    """
    calendar_lines = []
    today_date_str = start_date.strftime("%d.%m.%Y")
    
    for i in range(days_ahead):
        current_date = start_date + timedelta(days=i)
        date_str = current_date.strftime("%d.%m.%Y")
        weekday_num = current_date.weekday()
        weekday_name = WEEKDAY_NAMES_RU[weekday_num]
        
        # Добавляем "(Сегодня)" к текущей дате
        if date_str == today_date_str:
            calendar_lines.append(f"{date_str} - {weekday_name} (Сегодня)")
        else:
            calendar_lines.append(f"{date_str} - {weekday_name}")
    
    calendar_text = "\n".join(calendar_lines)
    
    logger.info(f"Generated calendar: {days_ahead} days starting from {start_date.strftime('%d.%m.%Y')} (today)")
    
    return calendar_text

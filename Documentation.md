
## 🛠️ Установка и настройка

### Шаг 1: Сетап проекта (локально)

1. **Через GitHub Desktop (для новичков):**
   - Скачайте и установите [GitHub Desktop](https://desktop.github.com/)
   - Нажмите "Clone a repository from the Internet"
   - Вставьте ссылку на репозиторий
   - Выберите папку для сохранения

2. **Через командную строку:**
   ```bash
   git clone git@github.com:NesterNN/cosmetology-bot-backend.git
   cd cosmetology-bot-backend
   ```

### Шаг 2: Создание виртуального окружения. ВАЖНО: этот этап нужен только для запуска проекта, если не нужно запускать - можно пропустить


```bash
# Windows
python -m venv .venv
c:/path/to/folder/cosmetology-bot-backend/.venv/Scripts/Activate.ps1

# Mac/Linux
python -m venv .venv
source .venv/bin/activate
```

**Важно:** После активации в начале строки терминала должно появиться `(.venv)`.

### Шаг 3: Установка зависимостей

```bash
pip install -r requirements.txt
```

### Шаг 4: Настройка переменных окружения

1. Создайте файл `.env` в корне проекта
2. Скопируйте в него следующий шаблон:

```env
# База данных PostgreSQL
DATABASE_URL=postgresql://username:password@localhost:5432/database_name

# Redis для очереди сообщений
REDIS_URL=redis://localhost:6379

# API ключи Claude AI
CLAUDE_API_KEY_1=key1
CLAUDE_API_KEY_2=key2

# Google Sheets для расписания
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_SHEET_ID=id_таблицы

# Настройки приложения
DEBUG=True
HOST=0.0.0.0
PORT=8000
```

### Шаг 5: Настройка конфигураций проекта (специалисты и услуги)

1. Создать файл `local_config.json` и скопировать в него содержимое `local_config.example.json`
2. Заменить услуги и специалистов на необходимых в рамках проекта
3. В случае необходимости - менять именно файл `local_config.json` - НЕ ТРОГАТЬ .py ФАЙЛЫ.

### Шаг 6: Настройка внешних сервисов. ВАЖНО: этот этап можно пропустить, если не планируете запускать проект локально

#### 🗄️ PostgreSQL (база данных)
1. Скачайте и установите [PostgreSQL](https://www.postgresql.org/download/)
2. Создайте базу данных:
   ```sql
   CREATE DATABASE cosmetology_bot;
   CREATE USER bot_user WITH PASSWORD 'ваш_пароль';
   GRANT ALL PRIVILEGES ON DATABASE cosmetology_bot TO bot_user;
   ```

#### 🔧 Redis (очередь сообщений)
1. **Windows:** Скачайте [Redis for Windows](https://github.com/MicrosoftArchive/redis/releases)
2. **Mac:** `brew install redis`
3. **Linux:** `sudo apt install redis-server`

#### 📊 Google Sheets
1. Перейдите в [Google Cloud Console](https://console.cloud.google.com)
2. Создайте новый проект
3. Включите API:
   - Google Sheets API
   - Google Drive API
4. Создайте Service Account:
   - IAM & Admin → Service Accounts → Create
   - Скачайте JSON файл с ключами
   - Переименуйте в `credentials.json`
5. Создайте Google Таблицу и поделитесь ей с email из Service Account

---

## 🚀 Запуск системы

### Простой запуск

```bash
python start.py
```

Этот скрипт автоматически:
- Проверит все настройки
- Создаст таблицы в базе данных
- Протестирует подключения
- Запустит сервер

### Ручной запуск

```bash
# Запуск сервера
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 🔍 Проверка работы

После запуска откройте в браузере:
- **Главная страница:** http://localhost:8000
- **Документация API:** http://localhost:8000/docs
- **Проверка здоровья:** http://localhost:8000/health

---

## 📁 Структура файлов

### Главные файлы:
```
cosmetology-bot-backend/
├── main.py                 # Главный файл проекта
├── start.py               # Скрипт запуска с проверками (не используется при ручном запуске)
├── requirements.txt       # Список всех библиотек
├── prompts.yml           # Промты для Клода
├── .env                  # Переменные для проекта, пример файла - `.env-example`
└── README.md             # Техническая документация
```

### Папка `app/` (основная логика):
```
app/
├── config.py             # Настройки проекта
├── database.py           # Работа с базой данных
├── models.py             # Структуры запросов и данных
├── services/             # Основные сервисы:
│   ├── claude_service.py     # Работа с клодом
│   ├── booking_service.py    # Управление записями
│   ├── google_sheets.py      # Синхронизация с таблицами
│   └── message_queue.py      # Очередь сообщений
└── utils/
    └── prompt_loader.py  # Загрузка промтов
```

---

## ⚙️ Описание ключевых файлов

### 🎯 `main.py` - Сердце системы
**Что делает:** Принимает сообщения от SendPulse, обрабатывает их через Клод и отправляет ответы.

**Основные функции:**
- `sendpulse_webhook()` - принимает входящие сообщения с SendPulse
- `process_message_async()` - обрабатывает сообщение через ИИ
- `get_dialogue_history()` - получает историю диалога с клиентом

### 🧠 `app/services/claude_service.py` - Взаимодействие с Клодом
**Что делает:** Обрабатывает запросы юзеров

**Каждая функция имеет в себе короткое описание функционала**

### 📅 `app/services/booking_service.py` - Управление записями
**Что делает:** Создает, изменяет и отменяет записи клиентов.

**Функции:**
- Проверка свободных слотов
- Создание новых записей
- Перенос существующих записей
- Отмена записей

### 📊 `app/services/google_sheets.py` - Работа с гугл таблицей
**Что делает:** Синхронизирует данные с Google Таблицами.

**Формат таблицы:**
```
| Дата     | Полная дата | Время | ID клиента | Имя клиента | Услуга      |
|----------|-------------|-------|------------|-------------|-------------|
| 25.01    | 25.01.2025  | 14:00 | 123456789  | Анна        | Чистка лица |
```

### 🔄 `app/services/message_queue.py` - Очередь сообщений
**Что делает:** Управляет потоком сообщений, предотвращает спам юзеру

**Особенности:**
- Объединяет несколько сообщений в одно
- Предотвращает перегрузку ИИ
- Обеспечивает правильный порядок обработки

### ⚙️ `app/config.py` - Настройки проекта
**Что содержит:**
- Подключения к базам данных
- Настройки ИИ
- Рабочие часы салона
- Список услуг и специалистов

### 🗄️ `app/database.py` - База данных
**Таблицы:**
- `projects` - настройки проектов
- `bookings` - записи клиентов  
- `message_queue` - очередь сообщений
- `dialogues` - история диалогов
- `feedback` - отзывы клиентов

### 💬 `prompts.yml` - Настройки клода
**Содержит промты для клода. ВАЖНО: не изменять названия переменных, содержащие промты**

---

## 📊 Как читать логи

### 📍 Где находятся логи

Логи сохраняются в файл `app.log` в корне проекта и выводятся в консоль (journalctl -u cosmetology-bot -f)

### 🔍 Типы логов

#### ✅ INFO - Обычная работа
```
2025-01-20 14:30:15 - Message ABC123 get UUID: DEF456
2025-01-20 14:30:16 - Message ID: DEF456 - Processing incoming message through queue service
```

#### ⚠️ WARNING - Предупреждения
```
2025-01-20 14:30:17 - Message ID: DEF456 - Failed to parse date '32.13': Invalid date format
```

#### ❌ ERROR - Ошибки
```
2025-01-20 14:30:18 - Message ID: DEF456 - Claude API error: API rate limit exceeded
```

### 🔎 Как найти проблему

1. **Найдите сообщение с ошибкой**, каждому сообщению, когда оно приходит в проект, присваивается уникальный айди
2. **Проследите весь путь** сообщения по Message ID
3. **Обратите внимание на ERROR и WARNING**, если нет - на детали логов.

#### Пример анализа лога:
```
# Сообщение пришло
14:30:15 - Message "Хочу записаться" get UUID: ABC123

# Начали обработку
14:30:16 - Message ID: ABC123 - Processing incoming message

# Анализ Клода
14:30:17 - Message ID: ABC123 - Starting intent detection

# Ошибка в Клоде
14:30:18 - Message ID: ABC123 - Error in intent detection: API timeout

# Результат
14:30:19 - Message ID: ABC123 - Returning error response
```

### 🚨 Частые ошибки и решения

#### 1. "Claude API error: API rate limit exceeded"
**Проблема:** Превышен лимит запросов к ИИ  
**Решение:** Подождите или добавьте второй API ключ

#### 2. "Database connection failed"
**Проблема:** Нет подключения к PostgreSQL
**Решение:** Проверьте, запущен ли PostgreSQL, правильно ли указан username:password, создана ли база данных.

#### 3. "Redis connection failed"
**Проблема:** Нет подключения к Redis  
**Решение:** Запустите Redis сервер

#### 4. "Google Sheets access denied"
**Проблема:** Неправильные настройки Google API
**Решение:** Проверьте файл credentials.json, ID таблицы и добавлен ли сервисный аккаунт в таблицу как Редактор

---

## 🧪 Как тестировать систему (ЛОКАЛЬНО)

### 1. Проверка запуска

```bash
python start.py

# Должны увидеть:
✅ All required environment variables are set
✅ Database tables created successfully
✅ Database connection successful
✅ Redis connection successful
✅ Claude API key configured
🚀 Starting application on 0.0.0.0:8000
```

### ИЛИ (приоритетнее)

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Тестирование через веб-интерфейс

Откройте http://localhost:8000/docs и проверьте эндпоинты:

#### Проверка здоровья системы:
- **GET** `/health` - должен вернуть `{"status": "healthy"}`

#### Получение статистики:
- **GET** `/projects/default/stats` - покажет количество сообщений и записей

## 🧪 Как тестировать систему (НА СЕРВЕРЕ)

### 1. Через linux-service

**Проверить существование сервиса для проекта.**
`systemctl list-units --type=service`
**На момент написания, на сервере сервис имеет название `cosmetology-bot.service`**
**Если сервис не создан - создать его**
```bash
sudo nano /etc/systemd/system/cosmetology-bot.service

### Содержимое файла с сервисом:
[Unit]
Description=Cosmetology Bot Backend
After=network.target

[Service]
User=root
WorkingDirectory=/root/cosmetology-bot-backend
ExecStart=/root/cosmetology-bot-backend/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```bash
# Reload systemd to recognize new service
sudo systemctl daemon-reload

# Enable service (start at boot)
sudo systemctl enable cosmetology-bot

# Start the service
sudo systemctl start cosmetology-bot

# Check service status
sudo systemctl status cosmetology-bot
```

**Для перезапуска проекта (в случае внесения изменений)**
```bash
sudo systemctl restart cosmetology-bot

## OR

sudo systemctl stop cosmetology-bot
sudo systemctl start cosmetology-bot
```

## 2. Вручную

**Сначала нужно запустить виртуальное окружение**
```bash
cd cosmetology-bot-backend
source .venv/bin/activate
```

**Теперь запускаем проект (будет запущен пока мы его держим запущенным руками, для запуска в бекграунде нужно использовать linux-service)**
`uvicorn main:app --host 0.0.0.0 --port 8000 --reload`

**Для остановки проекта - `CTRL+C`**


---

## 🔧 Настройка для проекта

### 1. Настройка услуг и специалистов
TBD: переношу переменные в отдельные файлы для более простого изменения

### 2. Настройка Claude
**В файле `.env`** 
```bash
# Claude AI Configuration
CLAUDE_API_KEY_1=your_claude_api_key_1_here
CLAUDE_API_KEY_2=your_claude_api_key_2_here
CLAUDE_MODEL=claude-sonnet-4-20250514
```

### 3. Настройка и изменение промтов

**В файле `prompts.yml` изменять соответствующие промты. Менять только содержимое переменных, но не их имя.**

### 4. Настройка Google Таблицы

Структура таблицы для каждого специалиста:

| A (Дата) | B (Полная дата) | C (Время) | D (ID клиента) | E (Имя) | F (Услуга) |
|----------|-----------------|-----------|----------------|---------|------------|
| 25.01    | 25.01.2025      | 14:00     | 123456789      | Анна    | Маникюр    |

**Важно:** 
- У каждого специалиста должен быть отдельный лист
- Названия листов должны точно совпадать с именами в коде
- Поделитесь таблицей с email из Google Service Account
- Таблица должна быть заполнена (первые 3 столбца - Дата, полная дата, время)

---

## 🚨 Решение проблем

### Система не запускается

1. **Проверьте Python:**
   ```bash
   python --version  # Должно быть 3.8+
   ```

2. **Проверьте виртуальное окружение:**
   ```bash
   # В командной строке должно быть (.venv)
   ```

3. **Проверьте зависимости:**
   ```bash
   pip list  # Должны быть все библиотеки из requirements.txt
   ```

### ИИ не отвечает

1. **Проверьте API ключи Claude:**
   - Проверьте лимиты и баланс
   - Создайте новые ключи если нужно

2. **Проверьте логи:**
   ```bash
   grep "Claude API error" app.log
   ```

### Не работает Google Таблицы

1. **Проверьте Service Account:**
   - Файл `credentials.json` в корне проекта
   - Email из файла добавлен в доступ к таблице
   - ID таблицы указан верно

2. **Проверьте API:**
   - Google Sheets API включен
   - Google Drive API включен

### База данных не работает

1. **Проверьте PostgreSQL:**
   ```bash
   # Windows
   services.msc  # Найдите PostgreSQL
   
   # Mac
   brew services list | grep postgresql
   
   # Linux
   sudo systemctl status postgresql
   ```

2. **Проверьте подключение:**
   ```python
   from app.database import engine
   with engine.connect() as conn:
       result = conn.execute("SELECT 1")
       print("Подключение работает!")
   ```

### Telegram бот не отвечает

**Проверьте логи входящих сообщений:**
   ```bash
   grep "Webhook received" app.log
   ```

---

### Репорт багов

При появлении багов отправьте:
1. **Последние логи** из `app.log` (релевантные для сообщений, которые спровоцировали баг) **либо Message ID, с которым случился баг**
3. **Описание бага**
4. **Шаги для воспроизведения** (опционально)

---

## 🔄 Обновление системы

### Получение обновлений с GitHub

```bash
# Остановите проект (если запущен) (Ctrl+C)

# Получите обновления
git pull origin main

# Установите новые зависимости
pip install -r requirements.txt

# Обновите базу данных если нужно
python -c "from app.database import create_tables; create_tables()"

# Запустите систему
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

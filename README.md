# 🤖 Multi-Platform AI Bot Service

AI-бот який працює на **Telegram**, **WhatsApp**, **Viber** та **Instagram** використовуючи **одну спільну логіку** через Claude AI.

---

## ✨ Можливості

- ✅ **Telegram** бот (polling)
- ✅ **WhatsApp** бот (Meta Business API)
- ✅ **Viber** бот (Viber Bot API)
- ✅ **Instagram** messaging (Meta Business API)
- 🧠 Claude AI для обробки повідомлень
- 📅 Інтеграція з Google Sheets (бронювання)
- 💾 PostgreSQL база даних
- 📧 Email сповіщення
- 🔄 Черга повідомлень з retry логікою

---

## 📁 Структура проекту

```
fastapi_ai_service/
│
├── telegram/              # Telegram бот
│   ├── handlers/          # Обробники повідомлень
│   ├── middlewares/       # Middleware
│   ├── services/          # Сервіси (Claude, Sheets, тощо)
│   ├── utils/             # Утиліти
│   ├── bot_processor.py   # СПІЛЬНА ЛОГІКА для всіх платформ
│   ├── config.py          # Конфігурація
│   ├── database.py        # База даних
│   ├── models.py          # Моделі даних
│   └── bot.py             # Запуск Telegram бота
│
├── whatsapp/              # WhatsApp бот
│   └── handlers/
│       └── messages.py    # Webhook handler
│
├── viber/                 # Viber бот
│   └── handlers/
│       └── messages.py    # Webhook handler
│
├── instagram/             # Instagram бот
│   └── handlers/
│       └── messages.py    # Webhook handler
│
├── main.py                # FastAPI сервер (WhatsApp/Viber/Instagram)
├── local_config.json      # Конфігурація проекту
├── prompts.yml            # Промпти для Claude
├── .env                   # Змінні оточення
├── requirements.txt       # Python залежності
├── SETUP.md               # Інструкції з налаштування
└── setup_viber.py         # Скрипт для Viber webhook

```

---

## 🚀 Швидкий старт

### 1. Встанови залежності:
```bash
pip install -r requirements.txt
```

### 2. Налаштуй .env:
```env
# Telegram
TELEGRAM_BOT_TOKEN=your_token

# WhatsApp
WHATSAPP_ACCESS_TOKEN=your_token
WHATSAPP_PHONE_NUMBER_ID=your_id
WHATSAPP_VERIFY_TOKEN=your_secret

# Viber
VIBER_BOT_TOKEN=your_token

# Instagram
INSTAGRAM_ACCESS_TOKEN=your_token
INSTAGRAM_PAGE_ID=your_id
INSTAGRAM_VERIFY_TOKEN=your_secret

# Claude AI
CLAUDE_API_KEY_1=sk-ant-...
CLAUDE_API_KEY_2=sk-ant-...

# Database
DATABASE_URL=postgresql://user:pass@localhost/db
```

### 3. Створи базу даних:
```sql
CREATE DATABASE cosmetology_bot;
```

### 4. Запусти бота:

**Telegram:**
```bash
python telegram/bot.py
```

**WhatsApp/Viber/Instagram:**
```bash
python main.py
```

---

## 🔧 Як це працює

### Загальна архітектура:

```
Повідомлення → Platform Handler → MessageQueue → bot_processor.py → Claude AI → Відповідь
                     ↓                                    ↓
                (whatsapp/viber/instagram/telegram)  (спільна логіка)
```

### Спільна логіка (`bot_processor.py`):
Всі платформи використовують **одну функцію** `process_message_async()`:
1. Отримує текст від користувача
2. Додає в чергу повідомлень
3. Аналізує intent через Claude
4. Отримує доступні слоти з Google Sheets
5. Генерує відповідь через Claude
6. Обробляє бронювання
7. Зберігає діалог в БД
8. Повертає відповідь на платформу

### Platform Handlers:
Кожна платформа має свій handler який:
- Приймає повідомлення (webhook або polling)
- Конвертує в стандартний формат
- Викликає `bot_processor.py`
- Відправляє відповідь назад

---

## 📱 Налаштування платформ

Детальні інструкції: [SETUP.md](SETUP.md)

### WhatsApp:
1. Створи Business App на developers.facebook.com
2. Додай WhatsApp product
3. Отримай токени
4. Налаштуй webhook: `https://your-domain/whatsapp/webhook`

### Viber:
1. Створи бота на partners.viber.com
2. Отримай Bot Token
3. Запусти: `python setup_viber.py`

### Instagram:
1. Підключи Instagram до Facebook Page
2. Створи App з Instagram Messaging
3. Налаштуй webhook: `https://your-domain/instagram/webhook`

---

## 🌐 Deploy

### Для тестування (ngrok):
```bash
ngrok http 8000
```

### Production (VPS):
1. Налаштуй домен з SSL
2. Встанови systemd service:

```ini
[Unit]
Description=Multi-Platform Bot
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

3. Запусти:
```bash
sudo systemctl enable bot
sudo systemctl start bot
```

---

## 📊 Моніторинг

### Логи:
- `telegram/bot.log` - Telegram
- `messenger_bots.log` - WhatsApp/Viber/Instagram

### Health check:
```bash
curl http://localhost:8000/health
```

### Database:
```sql
-- Перевір повідомлення в черзі
SELECT * FROM message_queue WHERE status = 'pending';

-- Перевір діалоги
SELECT * FROM dialogues ORDER BY timestamp DESC LIMIT 10;

-- Перевір бронювання
SELECT * FROM bookings WHERE status = 'active';
```

---

## 🔒 Безпека

- ✅ Verify tokens для webhooks
- ✅ HTTPS обов'язковий
- ✅ Змінні оточення в `.env`
- ✅ Database connection pooling
- ✅ Rate limiting
- ✅ Retry логіка для повідомлень

---

## 🆘 Troubleshooting

### Бот не відповідає:
1. Перевір логи
2. Перевір що база даних підключена
3. Перевір що Claude API keys валідні
4. Перевір що webhooks verified

### Telegram працює, а інші ні:
- Webhooks потребують публічний HTTPS URL
- Використовуй ngrok для тестування
- Перевір що FastAPI сервер запущений: `python main.py`

### База даних помилки:
```bash
python fix_sequences.py  # Виправити sequence
```

---

## 📚 Документація

- **Telegram Bot API**: https://core.telegram.org/bots/api
- **WhatsApp Business API**: https://developers.facebook.com/docs/whatsapp
- **Viber Bot API**: https://developers.viber.com/docs/api/rest-bot-api/
- **Instagram Messaging**: https://developers.facebook.com/docs/messenger-platform/instagram
- **Claude AI**: https://docs.anthropic.com

---

## 🎯 Roadmap

- [ ] Web інтерфейс для адміністрування
- [ ] Аналітика та статистика
- [ ] A/B тестування промптів
- [ ] Мультимовність
- [ ] Voice messages підтримка
- [ ] Платежі через боти

---

## 📄 Ліцензія

Приватний проект

---

## 👨‍💻 Автор

Створено для BodySphera / Cosmetology Bot

---

**Версія**: 1.0.0  
**Останнє оновлення**: 2025

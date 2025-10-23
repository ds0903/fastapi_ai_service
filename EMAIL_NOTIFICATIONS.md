# Email повідомлення адміністратору та менеджеру

## Що вміє система

Коли клієнт у чаті просить **менеджера** або **адміністратора**, система:
1. 🤖 AI розпізнає запит
2. 📧 Автоматично відправляє email на вказані адреси
3. 🔗 Додає пряме посилання на чат клієнта в SendPulse

## Налаштування .env файлу

### 1. SMTP налаштування (Gmail)

```env
# SMTP сервер
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587

# Email з якого відправляються листи
EMAIL_HOST_USER=ваша_пошта@gmail.com
EMAIL_HOST_PASSWORD=ваш_пароль_додатку
```

**⚠️ Важливо для Gmail:**
- Використовуйте **пароль додатку**, не звичайний пароль
- Як створити: Google Account → Security → 2-Step Verification → App passwords

### 2. Email адреси отримувачів

```env
# Адміністратори (через кому якщо декілька)
ADMIN_EMAILS=admin1@example.com,admin2@example.com

# Менеджери/Консультанти (через кому якщо декілька)
CONSULTANT_EMAILS=manager1@example.com,manager2@example.com
```

### 3. SendPulse Bot ID

```env
# ID вашого бота в SendPulse (для посилання на чат)
SENDPULSE_BOT_ID=68a711000f8cbe2faf0879da
```

**Де взяти Bot ID:**
1. SendPulse → Chatbots → Виберіть бота
2. URL: `https://login.sendpulse.com/chatbots/flows?id=XXXXXXX`
3. Скопіюйте ID (24 символи)

## Як це працює

### 1. Клієнт пише запит
Приклади фраз які спрацьовують:
- "Хочу поговорити з менеджером"
- "Підключіть адміністратора"
- "Потрібна консультація"
- "Зв'яжіть з реальною людиною"

### 2. AI розпізнає тип запиту
- **Type 1** = Адміністратор → email на `ADMIN_EMAILS`
- **Type 2** = Менеджер/Консультант → email на `CONSULTANT_EMAILS`

### 3. Що буде в email листі

```
🔔 Клієнт просить адміністратора/консультанта

Дата та час: 23.10.2025 14:30:15
ID клієнта: +380671234567
Ім'я клієнта: Іван
Телефон: +380671234567

Останнє повідомлення:
"Хочу поговорити з менеджером"

Посилання на чат: [Відкрити чат в SendPulse]

Клієнт очікує на відповідь від реального адміністратора.
Будь ласка, зв'яжіться з клієнтом якомога швидше.
```

## Перевірка налаштувань

### ✅ Checklist

- [ ] SMTP налаштовано (Gmail + App Password)
- [ ] Вказано EMAIL_HOST_USER
- [ ] Вказано EMAIL_HOST_PASSWORD
- [ ] Додано ADMIN_EMAILS
- [ ] Додано CONSULTANT_EMAILS
- [ ] Вказано SENDPULSE_BOT_ID
- [ ] Перезапущено сервер після змін в .env

### 🧪 Тестування

1. Напишіть боту: "Хочу менеджера"
2. Перевірте email на `CONSULTANT_EMAILS`
3. Відкрийте посилання на чат

## Приклад повного .env

```env
# SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
EMAIL_HOST_USER=bot@salonanna.com
EMAIL_HOST_PASSWORD=abcd efgh ijkl mnop

# Отримувачі
ADMIN_EMAILS=admin@salonanna.com,owner@salonanna.com
CONSULTANT_EMAILS=manager@salonanna.com,reception@salonanna.com

# SendPulse
SENDPULSE_BOT_ID=68a711000f8cbe2faf0879da
```

## Troubleshooting

**Email не відправляються:**
- Перевірте Gmail App Password (не звичайний пароль)
- Перевірте що email адреси правильні
- Дивіться логи: `journalctl -u anna-paris-bot-8013 -f`

**Посилання на чат не працює:**
- Перевірте SENDPULSE_BOT_ID
- Переконайтесь що це WhatsApp бот

**AI не розпізнає запит:**
- Промпт вже налаштовано в `prompts.yml`
- Клієнт має чітко попросити менеджера/адміна

# 🚀 Швидке налаштування телефонії (2 кроки)

## ⚡ АВТОМАТИЧНЕ ВСТАНОВЛЕННЯ

### Windows:
```bash
cd telephony
QUICKSTART.bat
```

Скрипт автоматично:
- ✅ Встановить twilio
- ✅ Інтегрує в main.py
- ✅ Перевірить конфігурацію

## ⚙️ РУЧНЕ ВСТАНОВЛЕННЯ

### 1. Встановити залежності
```bash
pip install twilio==9.0.4
```

### 2. Інтегрувати в main.py
```bash
python telephony/integrate.py
```

### 3. Налаштувати Twilio

#### A. Отримати credentials
1. Реєстрація: https://www.twilio.com/try-twilio
2. Console: https://console.twilio.com
3. Скопіювати:
   - Account SID (AC...)
   - Auth Token

#### B. Купити номер
1. Phone Numbers → Buy a number
2. Обрати країну (Ukraine +380 / USA +1)
3. Voice capabilities ✓
4. Купити ($1-2/міс або trial credits)

#### C. Додати в .env
Відкрити `.env` в корені проекту:

```env
# Twilio Configuration
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+380xxxxxxxxx
```

#### D. Налаштувати Webhook
1. Console → Phone Numbers → Active Numbers
2. Клікнути на номер
3. Voice & Fax:
   - **A CALL COMES IN**: Webhook
   - **URL**: `https://your-domain.com/telephony/welcome`
   - **HTTP**: POST
   - **STATUS CALLBACK**: `https://your-domain.com/telephony/call-status`

**Для локального тестування:**
```bash
# Встановити ngrok: https://ngrok.com/download
ngrok http 8000

# Використати ngrok URL в Twilio
# Наприклад: https://abc123.ngrok.io/telephony/welcome
```

## ✅ Перевірка

### 1. Запустити сервер
```bash
python start.py
```

### 2. Перевірити статус
```
http://localhost:8000/telephony/health
```

Має показати:
```json
{
  "service": "telephony",
  "status": "configured",
  "message": "Telephony service is ready"
}
```

### 3. Тест дзвінка
Зателефонувати на ваш Twilio номер → AI має відповісти

## 📊 Моніторинг

### API endpoints:
- `GET /telephony/health` - статус сервісу
- `GET /telephony/stats` - активні дзвінки

### Twilio логи:
https://console.twilio.com/monitor/logs/calls

## 💰 Вартість

### Trial:
- $15 безкоштовних credits
- ~1000 хвилин дзвінків

### Production:
- Номер: $1-2/міс
- Дзвінок: $0.013/хв
- 100 дзвінків × 3 хв = **$5/міс**

## 🔧 Якщо щось не працює

### Помилка: "not configured"
→ Додайте TWILIO_* в .env

### Webhook не спрацьовує
→ Перевірте:
1. URL публічний (ngrok для локального)
2. Налаштування в Twilio Console
3. Логи: https://console.twilio.com/monitor

### AI не розуміє
→ Перевірте `voice_language` в `telephony/config.py`

## 📖 Повна документація
Див. `telephony/README.md`

## ❓ Підтримка
- Twilio Docs: https://www.twilio.com/docs
- Twilio Support: https://support.twilio.com

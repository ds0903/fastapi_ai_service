# 📞 Телефонія - Швидкий Запуск

## Встановлення (2 кроки):

### 1. Запустити:
```cmd
cd telephony
INSTALL.bat
```

### 2. Додати в .env (в корені проекту):
```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+380xxxxxxxxx
```

## Отримати credentials:

1. **Реєстрація**: https://www.twilio.com/try-twilio ($15 безкоштовно)
2. **Console**: https://console.twilio.com
   - Account SID + Auth Token
3. **Купити номер**: Phone Numbers → Buy ($1/міс)
4. **Налаштувати webhook** в номері:
   - Voice URL: `https://your-domain.com/telephony/welcome`
   - Status URL: `https://your-domain.com/telephony/call-status`

## Запуск:

```cmd
python start.py
```

Перевірка: http://localhost:8000/telephony/health

## Локальне тестування (ngrok):

```cmd
ngrok http 8000
```

Використати ngrok URL в Twilio webhook налаштуваннях.

## Готово! Телефонуйте на номер - AI відповість 🤖

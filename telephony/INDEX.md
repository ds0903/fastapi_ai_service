# 📞 Telephony Module

AI Voice Assistant через Twilio - телефонуйте на номер і спілкуйтесь з ботом голосом!

## 🚀 Швидкий старт (2 кліки)

### Windows:
```bash
cd telephony
QUICKSTART.bat
```

### Linux/Mac:
```bash
cd telephony
chmod +x QUICKSTART.sh
./QUICKSTART.sh
```

Або вручну:
```bash
pip install twilio==9.0.4
python telephony/integrate.py
```

## 📚 Документація

- **SETUP.md** - Покрокові інструкції налаштування
- **README.md** - Повна документація і troubleshooting
- **.env.example** - Приклад конфігурації

## ⚡ Що робить модуль:

1. ✅ Приймає дзвінки на Twilio номер
2. ✅ Розпізнає українську мову → текст
3. ✅ Обробляє через Claude AI (твій існуючий код!)
4. ✅ Відповідає голосом українською
5. ✅ Записує діалоги в БД
6. ✅ Може бронювати послуги голосом

## 💰 Вартість

- Trial: $15 безкоштовно (~1000 хв)
- Production: ~$5/міс (100 дзвінків по 3 хв)

## 🔗 Корисні посилання

- [Twilio Console](https://console.twilio.com)
- [Купити номер](https://console.twilio.com/phone-numbers)
- [Логи дзвінків](https://console.twilio.com/monitor/logs/calls)
- [Twilio Docs](https://www.twilio.com/docs/voice)

## 📊 Перевірка після встановлення

```bash
# Запустити сервер
python start.py

# Перевірити статус
curl http://localhost:8000/telephony/health

# Зателефонувати на Twilio номер → AI відповість!
```

---

**Питання?** Читай `SETUP.md` або `README.md`

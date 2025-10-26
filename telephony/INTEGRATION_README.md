# 📞 Інтеграція Binotel Телефонії

## ✅ Що зроблено

### 1. Переробка на Binotel
- ❌ Видалено Twilio
- ✅ Додано Binotel API
- ✅ Інтеграція з Google Cloud Speech-to-Text
- ✅ Інтеграція з Google Cloud Text-to-Speech

### 2. Схема роботи
```
Дзвінок → Binotel → Ваш сервер → Google Speech → Claude → Google TTS → Binotel → Клієнт
```

### 3. Файли

#### Оновлені файли:
- `telephony/config.py` - конфігурація Binotel
- `telephony/models.py` - моделі для Binotel вебхуків
- `telephony/telephony_service.py` - сервіс з Google Speech/TTS
- `telephony/voice_routes.py` - API роути для Binotel
- `requirements.txt` - додано Google Cloud бібліотеки
- `main.py` - інтеграція телефонії

## 🚀 Як запустити

### 1. Встановіть залежності
```bash
pip install -r requirements.txt
```

### 2. Налаштуйте .env
Створіть `.env` файл з наступними параметрами:

```env
# Binotel
BINOTEL_API_KEY=your_api_key
BINOTEL_API_SECRET=your_secret
BINOTEL_PHONE_NUMBER=+380XXXXXXXXX

# Google Cloud
GOOGLE_APPLICATION_CREDENTIALS=credentials.json
```

### 3. Налаштуйте Google Cloud

1. Створіть проект в Google Cloud Console
2. Увімкніть API:
   - Cloud Speech-to-Text API
   - Cloud Text-to-Speech API
3. Створіть Service Account
4. Завантажте ключ JSON як `credentials.json`
5. Покладіть файл в корінь проекту

### 4. Налаштуйте Binotel

1. Зайдіть в особистий кабінет Binotel
2. Налаштуйте вебхуки:
   - **Вхідний дзвінок**: `https://your-domain.com/telephony/binotel/incoming-call`
   - **Аудіо потік**: `https://your-domain.com/telephony/binotel/audio-stream`
   - **Статус дзвінка**: `https://your-domain.com/telephony/binotel/call-status`
3. Скопіюйте API ключ та секрет

### 5. Запустіть сервер
```bash
python main.py
```

## 📡 API Endpoints

### Binotel вебхуки:

**POST /telephony/binotel/incoming-call**
- Обробка вхідного дзвінка
- Повертає привітальне аудіо

**POST /telephony/binotel/audio-stream**
- Обробка аудіо від користувача
- Розпізнає мову → Claude → синтезує відповідь

**POST /telephony/binotel/call-status**
- Отримує оновлення статусу дзвінка

### Моніторинг:

**GET /telephony/stats**
- Статистика активних дзвінків

**GET /telephony/health**
- Перевірка стану сервісу

## 🔧 Технічні деталі

### Google Speech-to-Text
- Мова: Ukrainian (uk-UA)
- Модель: phone_call (оптимізована для телефонії)
- Encoding: LINEAR16
- Sample rate: 8000 Hz

### Google Text-to-Speech
- Голос: uk-UA-Wavenet-A (жіночий)
- Можна змінити в `telephony/config.py`:
  - `voice_name` - назва голосу
  - `voice_gender` - MALE або FEMALE

### Інтеграція з Claude
- Використовує існуючий ClaudeService
- Повна інтеграція з системою бронювання
- Зберігає історію розмов в БД

## 🎯 Що працює

✅ Розпізнавання української мови
✅ Синтез української мови
✅ Інтеграція з Claude AI
✅ Система бронювання через телефон
✅ Збереження історії розмов
✅ Активні дзвінки в пам'яті

## ⚙️ Налаштування голосу

В `telephony/config.py`:

```python
voice_language: str = "uk-UA"
voice_name: str = "uk-UA-Wavenet-A"  # Жіночий
# або
voice_name: str = "uk-UA-Wavenet-B"  # Чоловічий
```

Доступні голоси:
- uk-UA-Wavenet-A (жінка, нейтральний)
- uk-UA-Standard-A (жінка, базовий)

## 📊 Моніторинг

```bash
# Перевірка здоров'я
curl http://localhost:8000/telephony/health

# Статистика
curl http://localhost:8000/telephony/stats
```

## ❗ Важливо

1. **Binotel налаштування**: Переконайтесь що вебхуки налаштовані правильно
2. **Google Cloud**: Файл `credentials.json` повинен бути в корені проекту
3. **Мережа**: Ваш сервер повинен бути доступний з інтернету для Binotel вебхуків
4. **HTTPS**: Binotel вимагає HTTPS для вебхуків (використайте Nginx з SSL)

## 🐛 Troubleshooting

### Binotel не відправляє вебхуки
- Перевірте доступність сервера з інтернету
- Перевірте HTTPS сертифікат
- Перевірте логи Binotel в особистому кабінеті

### Google Speech не працює
- Перевірте `GOOGLE_APPLICATION_CREDENTIALS`
- Перевірте що API увімкнені в Google Cloud
- Перевірте квоти Google Cloud

### Немає звуку
- Перевірте формат аудіо (має бути LINEAR16, 8000Hz)
- Перевірте що Binotel правильно отримує аудіо

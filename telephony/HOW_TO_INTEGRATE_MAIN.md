# 🔧 Інтеграція телефонії в main.py

## ШАГ 1: Додати імпорти (після EmailService)

```python
from app.services.email_service import EmailService

# Telephony integration
try:
    from telephony.voice_routes import router as telephony_router, set_telephony_service
    from telephony.telephony_service import TelephonyService
    from telephony.config import binotel_settings
    TELEPHONY_ENABLED = True
    logger.info("Telephony modules imported successfully")
except ImportError as e:
    TELEPHONY_ENABLED = False
    logger.warning(f"Telephony modules not available: {e}")
```

## ШАГ 2: Ініціалізувати сервіс (в функції lifespan, після ClaudeService)

```python
# В функції lifespan(), після ініціалізації global_claude_service:

        # Initialize Telephony Service if enabled
        if TELEPHONY_ENABLED:
            try:
                telephony_service = TelephonyService(db, default_config, global_claude_service)
                set_telephony_service(telephony_service)
                logger.info("✅ Telephony service initialized successfully")
                logger.info(f"📞 Binotel configured: {bool(binotel_settings.binotel_api_key)}")
                logger.info(f"☁️ Google Cloud configured: {bool(binotel_settings.google_application_credentials)}")
            except Exception as e:
                logger.error(f"❌ Failed to initialize telephony service: {e}")
        else:
            logger.warning("⚠️ Telephony service not enabled - modules not imported")
```

## ШАГ 3: Підключити роути (після створення app)

```python
app = FastAPI(
    title="Telegram Bot Backend with Telephony",
    description="FastAPI backend for SendPulse Telegram bot with AI management and Binotel telephony",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include telephony routes
if TELEPHONY_ENABLED:
    app.include_router(telephony_router)
    logger.info("✅ Telephony routes registered at /telephony")
```

## ШАГ 4: Оновити ендпоінти (опціонально)

```python
@app.get("/")
async def root():
    return {
        "message": "Telegram Bot Backend is running",
        "telephony_enabled": TELEPHONY_ENABLED,
        "version": "2.0.0"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "telephony_enabled": TELEPHONY_ENABLED
    }
```

---

## 📝 ПОВНИЙ КОД ДЛЯ КОПІЮВАННЯ:

### 1. Імпорти (додати після EmailService):
```python
# Telephony integration
try:
    from telephony.voice_routes import router as telephony_router, set_telephony_service
    from telephony.telephony_service import TelephonyService
    from telephony.config import binotel_settings
    TELEPHONY_ENABLED = True
except ImportError as e:
    TELEPHONY_ENABLED = False
    logging.getLogger(__name__).warning(f"Telephony not available: {e}")
```

### 2. В lifespan() (після global_claude_service):
```python
        # Initialize Telephony Service
        if TELEPHONY_ENABLED:
            try:
                telephony_service = TelephonyService(db, default_config, global_claude_service)
                set_telephony_service(telephony_service)
                logger.info("✅ Telephony initialized")
            except Exception as e:
                logger.error(f"❌ Telephony init failed: {e}")
```

### 3. Після створення app:
```python
# Include telephony routes
if TELEPHONY_ENABLED:
    app.include_router(telephony_router)
```

---

## ✅ ВСЕ! Телефонія інтегрована.

Тепер просто:
1. Встановіть залежності: `pip install -r requirements.txt`
2. Налаштуйте .env
3. Запустіть: `python main.py`

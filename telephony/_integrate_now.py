import os
import sys

# Читаємо main.py
with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Додаємо імпорт після EmailService
import_add = '''from app.services.email_service import EmailService

# Telephony
try:
    from telephony import voice_router, TelephonyService
    from telephony.voice_routes import set_telephony_service
    TELEPHONY_AVAILABLE = True
except ImportError:
    TELEPHONY_AVAILABLE = False
'''

content = content.replace(
    'from app.services.email_service import EmailService',
    import_add
)

# Додаємо ініціалізацію в lifespan після ClaudeService
lifespan_add = '''        logger.info("Initialized global ClaudeService for load balancing between API keys")
        logger.info("📊 Load balance stats available at: GET /admin/load-balance-stats")
        
        # Initialize Telephony
        if TELEPHONY_AVAILABLE:
            try:
                telephony_service = TelephonyService(db, default_config, global_claude_service)
                set_telephony_service(telephony_service)
                logger.info("📞 Telephony service initialized")
            except Exception as e:
                logger.error(f"Telephony init failed: {e}")
'''

content = content.replace(
    '        logger.info("Initialized global ClaudeService for load balancing between API keys")\n        logger.info("📊 Load balance stats available at: GET /admin/load-balance-stats")',
    lifespan_add
)

# Додаємо router після middleware
router_add = '''app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Telephony routes
if TELEPHONY_AVAILABLE:
    app.include_router(voice_router)
    logger.info("📞 Telephony routes: /telephony/*")
'''

content = content.replace(
    '''app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)''',
    router_add
)

# Записуємо
with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Telephony integrated into main.py!")

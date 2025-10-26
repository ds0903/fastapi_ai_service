"""
Telephony Integration Script
Run this script to integrate telephony module into main.py
"""
import sys

def integrate_telephony():
    """Add telephony imports and router to main.py"""
    
    # Read main.py
    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("❌ Error: main.py not found!")
        print("Make sure you run this script from the project root directory")
        return False
    
    # Check if already integrated
    if 'from telephony import voice_router' in content:
        print("✅ Telephony already integrated in main.py")
        return True
    
    print("🔧 Integrating telephony into main.py...")
    
    # Find the import section and add telephony import
    import_marker = "from app.services.email_service import EmailService"
    
    telephony_import = """from app.services.email_service import EmailService

# Import telephony module
try:
    from telephony import voice_router, TelephonyService
    from telephony.voice_routes import set_telephony_service
    TELEPHONY_AVAILABLE = True
    logger.info("✅ Telephony module imported successfully")
except ImportError as e:
    TELEPHONY_AVAILABLE = False
    logger.warning(f"⚠️ Telephony module not available: {e}")
    logger.warning("To enable telephony, run: pip install twilio==9.0.4")
"""
    
    if import_marker in content:
        content = content.replace(import_marker, telephony_import)
        print("  ✓ Added telephony import")
    else:
        print("  ⚠️ Warning: Could not find import marker, adding at the end of imports")
        # Add after all imports (before first class/function definition)
        import_end = content.find('\n\nlogging.basicConfig')
        if import_end > 0:
            content = content[:import_end] + '\n' + telephony_import + content[import_end:]
    
    # Add telephony service initialization in lifespan
    lifespan_marker = '        logger.info("Initialized global ClaudeService for load balancing between API keys")'
    
    telephony_init = '''        logger.info("Initialized global ClaudeService for load balancing between API keys")
        
        # Initialize telephony service if available
        if TELEPHONY_AVAILABLE:
            try:
                telephony_service = TelephonyService(db, default_config, global_claude_service)
                set_telephony_service(telephony_service)
                logger.info("📞 Telephony service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize telephony service: {e}")
        else:
            logger.info("📞 Telephony service not available - install twilio to enable")
'''
    
    if lifespan_marker in content:
        content = content.replace(lifespan_marker, telephony_init)
        print("  ✓ Added telephony service initialization")
    else:
        print("  ⚠️ Warning: Could not find lifespan marker")
    
    # Add router inclusion after middleware setup
    middleware_marker = """app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)"""
    
    router_inclusion = """app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include telephony router
if TELEPHONY_AVAILABLE:
    app.include_router(voice_router)
    logger.info("📞 Telephony routes registered at /telephony/*")
"""
    
    if middleware_marker in content:
        content = content.replace(middleware_marker, router_inclusion)
        print("  ✓ Added telephony router inclusion")
    else:
        print("  ⚠️ Warning: Could not find middleware marker")
    
    # Write modified content back
    try:
        with open('main.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print("\n✅ Telephony successfully integrated into main.py!")
        print("\nNext steps:")
        print("1. Install twilio: pip install twilio==9.0.4")
        print("2. Configure .env with Twilio credentials")
        print("3. Restart your server: python start.py")
        print("4. Check telephony status: http://localhost:8000/telephony/health")
        return True
    except Exception as e:
        print(f"❌ Error writing main.py: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("📞 TELEPHONY INTEGRATION SCRIPT")
    print("=" * 60)
    print()
    
    success = integrate_telephony()
    
    print()
    print("=" * 60)
    sys.exit(0 if success else 1)

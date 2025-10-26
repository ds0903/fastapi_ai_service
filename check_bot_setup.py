"""
Check bot setup - verify all requirements are met
"""
import os
import sys

def check_setup():
    """Check if bot is ready to run"""
    issues = []
    warnings = []
    
    print("=" * 60)
    print("🔍 Checking bot setup...")
    print("=" * 60)
    print()
    
    # Check .env file
    if not os.path.exists('.env'):
        issues.append("❌ .env file not found! Create it from .env-example")
    else:
        print("✅ .env file exists")
        
        # Check critical env variables
        from dotenv import load_dotenv
        load_dotenv()
        
        if not os.getenv('TELEGRAM_BOT_TOKEN'):
            issues.append("❌ TELEGRAM_BOT_TOKEN not set in .env")
        else:
            token = os.getenv('TELEGRAM_BOT_TOKEN')
            if len(token) < 40:
                issues.append("❌ TELEGRAM_BOT_TOKEN seems invalid (too short)")
            else:
                print(f"✅ TELEGRAM_BOT_TOKEN set: {token[:10]}...")
        
        if not os.getenv('CLAUDE_API_KEY_1'):
            issues.append("❌ CLAUDE_API_KEY_1 not set in .env")
        else:
            print("✅ CLAUDE_API_KEY_1 set")
        
        if not os.getenv('CLAUDE_API_KEY_2'):
            warnings.append("⚠️  CLAUDE_API_KEY_2 not set (recommended for backup)")
        else:
            print("✅ CLAUDE_API_KEY_2 set")
        
        if not os.getenv('DATABASE_URL'):
            issues.append("❌ DATABASE_URL not set in .env")
        else:
            print("✅ DATABASE_URL set")
    
    # Check required packages
    try:
        import aiogram
        print(f"✅ aiogram installed (version {aiogram.__version__})")
    except ImportError:
        issues.append("❌ aiogram not installed! Run: pip install aiogram")
    
    try:
        import anthropic
        print("✅ anthropic installed")
    except ImportError:
        issues.append("❌ anthropic not installed! Run: pip install -r requirements.txt")
    
    try:
        import sqlalchemy
        print("✅ sqlalchemy installed")
    except ImportError:
        issues.append("❌ sqlalchemy not installed! Run: pip install -r requirements.txt")
    
    # Check database connection
    try:
        from telegram.database import engine
        with engine.connect() as conn:
            print("✅ Database connection successful")
    except Exception as e:
        issues.append(f"❌ Database connection failed: {e}")
    
    # Check local_config.json
    if not os.path.exists('local_config.json'):
        warnings.append("⚠️  local_config.json not found (will use defaults)")
    else:
        print("✅ local_config.json exists")
    
    # Check credentials.json (Google Sheets)
    if not os.path.exists('credentials.json'):
        warnings.append("⚠️  credentials.json not found (Google Sheets won't work)")
    else:
        print("✅ credentials.json exists")
    
    # Summary
    print()
    print("=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    
    if issues:
        print()
        print("❌ CRITICAL ISSUES (must fix):")
        for issue in issues:
            print(f"  {issue}")
    
    if warnings:
        print()
        print("⚠️  WARNINGS (optional):")
        for warning in warnings:
            print(f"  {warning}")
    
    print()
    
    if not issues:
        print("=" * 60)
        print("✅ ALL CHECKS PASSED!")
        print("=" * 60)
        print()
        print("You can now start the bot:")
        print("  python bot.py")
        print()
        return 0
    else:
        print("=" * 60)
        print(f"❌ Found {len(issues)} critical issues")
        print("=" * 60)
        print()
        print("Fix the issues above and run this script again.")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(check_setup())

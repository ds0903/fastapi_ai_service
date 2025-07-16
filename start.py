#!/usr/bin/env python3
"""
Startup script for Telegram Bot Backend
This script initializes the database and starts the application
"""

import os
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def check_environment():
    """Check if all required environment variables are set"""
    required_vars = [
        'DATABASE_URL',
        'REDIS_URL',
        'CLAUDE_API_KEY_1',
        'CLAUDE_API_KEY_2'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these variables in your .env file or environment")
        return False
    
    print("✅ All required environment variables are set")
    return True

def create_database_tables():
    """Create database tables if they don't exist"""
    try:
        from app.database import create_tables
        create_tables()
        print("✅ Database tables created successfully")
        return True
    except Exception as e:
        print(f"❌ Error creating database tables: {e}")
        return False

def test_connections():
    """Test connections to external services"""
    print("🔍 Testing connections...")
    
    # Test database connection
    try:
        from app.database import engine
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
    
    # Test Redis connection
    try:
        import redis
        from app.config import settings
        redis_client = redis.from_url(settings.redis_url)
        redis_client.ping()
        print("✅ Redis connection successful")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False
    
    # Test Claude API
    try:
        import anthropic
        from app.config import settings
        if settings.claude_api_key_1:
            client = anthropic.Client(api_key=settings.claude_api_key_1)
            print("✅ Claude API key configured")
        else:
            print("⚠️  Claude API key not configured")
    except Exception as e:
        print(f"❌ Claude API test failed: {e}")
        return False
    
    return True

def start_application():
    """Start the FastAPI application"""
    try:
        import uvicorn
        from app.config import settings
        
        print(f"🚀 Starting application on {settings.host}:{settings.port}")
        print(f"📚 API documentation available at: http://{settings.host}:{settings.port}/docs")
        print(f"🔧 Health check endpoint: http://{settings.host}:{settings.port}/health")
        print("\nPress Ctrl+C to stop the application")
        
        uvicorn.run(
            "main:app",
            host=settings.host,
            port=settings.port,
            reload=settings.debug,
            log_level=settings.log_level.lower()
        )
        
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        return False
    
    return True

def main():
    """Main startup function"""
    print("🤖 Telegram Bot Backend - Starting up...")
    print("=" * 50)
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Create database tables
    if not create_database_tables():
        sys.exit(1)
    
    # Test connections
    if not test_connections():
        print("\n⚠️  Some connections failed, but continuing anyway...")
    
    # Start application
    print("\n" + "=" * 50)
    start_application()

if __name__ == "__main__":
    main() 
"""
Test Telegram Bot Token
Quick script to verify your bot token works
"""
import asyncio
import sys
import os


async def test_token():
    """Test if bot token is valid"""
    from dotenv import load_dotenv
    load_dotenv()
    
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    print("=" * 60)
    print("🔑 Testing Telegram Bot Token")
    print("=" * 60)
    print()
    
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN not found in .env!")
        print()
        print("Add to .env file:")
        print("  TELEGRAM_BOT_TOKEN=your_token_here")
        return 1
    
    print(f"Token: {token[:10]}...{token[-10:]}")
    print()
    
    try:
        from aiogram import Bot
        
        bot = Bot(token=token)
        
        print("⏳ Connecting to Telegram...")
        me = await bot.get_me()
        
        print()
        print("=" * 60)
        print("✅ TOKEN IS VALID!")
        print("=" * 60)
        print()
        print(f"Bot info:")
        print(f"  ID: {me.id}")
        print(f"  Name: {me.first_name}")
        print(f"  Username: @{me.username}")
        print(f"  Can join groups: {me.can_join_groups}")
        print(f"  Can read messages: {me.can_read_all_group_messages}")
        print()
        print("Your bot is ready to use!")
        print(f"Find it in Telegram: https://t.me/{me.username}")
        print()
        
        await bot.session.close()
        return 0
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ TOKEN IS INVALID!")
        print("=" * 60)
        print()
        print(f"Error: {e}")
        print()
        print("Get a new token from @BotFather:")
        print("  1. Open Telegram")
        print("  2. Find @BotFather")
        print("  3. Send: /newbot")
        print("  4. Follow instructions")
        print("  5. Copy the token to .env")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(test_token()))

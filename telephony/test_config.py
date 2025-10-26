"""
Test script to check Binotel telephony configuration
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_config():
    """Check if all required configuration is present"""
    print("🔍 Checking Binotel Telephony Configuration...\n")
    
    issues = []
    warnings = []
    
    # Check Binotel settings
    print("📞 Binotel Configuration:")
    binotel_key = os.getenv("BINOTEL_API_KEY", "")
    binotel_secret = os.getenv("BINOTEL_API_SECRET", "")
    binotel_phone = os.getenv("BINOTEL_PHONE_NUMBER", "")
    
    if binotel_key:
        print(f"  ✅ BINOTEL_API_KEY: {binotel_key[:10]}...")
    else:
        print("  ❌ BINOTEL_API_KEY: NOT SET")
        issues.append("BINOTEL_API_KEY is not configured")
    
    if binotel_secret:
        print(f"  ✅ BINOTEL_API_SECRET: {binotel_secret[:10]}...")
    else:
        print("  ❌ BINOTEL_API_SECRET: NOT SET")
        issues.append("BINOTEL_API_SECRET is not configured")
    
    if binotel_phone:
        print(f"  ✅ BINOTEL_PHONE_NUMBER: {binotel_phone}")
    else:
        print("  ⚠️  BINOTEL_PHONE_NUMBER: NOT SET")
        warnings.append("BINOTEL_PHONE_NUMBER is not configured")
    
    # Check Google Cloud settings
    print("\n☁️  Google Cloud Configuration:")
    google_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
    print(f"  📄 GOOGLE_APPLICATION_CREDENTIALS: {google_creds}")
    
    if os.path.exists(google_creds):
        print(f"  ✅ Credentials file exists")
    else:
        print(f"  ❌ Credentials file NOT FOUND")
        issues.append(f"Google Cloud credentials file '{google_creds}' not found")
    
    # Check Python packages
    print("\n📦 Python Packages:")
    
    try:
        import google.cloud.speech
        print("  ✅ google-cloud-speech installed")
    except ImportError:
        print("  ❌ google-cloud-speech NOT installed")
        issues.append("Install: pip install google-cloud-speech")
    
    try:
        import google.cloud.texttospeech
        print("  ✅ google-cloud-texttospeech installed")
    except ImportError:
        print("  ❌ google-cloud-texttospeech NOT installed")
        issues.append("Install: pip install google-cloud-texttospeech")
    
    # Try to import telephony modules
    print("\n🔧 Telephony Modules:")
    try:
        from telephony.config import binotel_settings
        from telephony.telephony_service import TelephonyService
        from telephony.voice_routes import router
        print("  ✅ All telephony modules imported successfully")
    except ImportError as e:
        print(f"  ❌ Import error: {e}")
        issues.append(f"Telephony module import failed: {e}")
    
    # Summary
    print("\n" + "="*50)
    print("📊 Summary:")
    print("="*50)
    
    if not issues and not warnings:
        print("✅ ✅ ✅ ALL CHECKS PASSED! Telephony is ready!")
        print("\nNext steps:")
        print("1. Configure Binotel webhooks in their dashboard")
        print("2. Start the server: python main.py")
        print("3. Test with: curl http://localhost:8000/telephony/health")
        return True
    else:
        if issues:
            print(f"\n❌ {len(issues)} CRITICAL ISSUE(S) FOUND:")
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. {issue}")
        
        if warnings:
            print(f"\n⚠️  {len(warnings)} WARNING(S):")
            for i, warning in enumerate(warnings, 1):
                print(f"  {i}. {warning}")
        
        print("\n📚 See telephony/INTEGRATION_README.md for setup instructions")
        return False


def test_google_cloud():
    """Test Google Cloud API connection"""
    print("\n" + "="*50)
    print("🧪 Testing Google Cloud Connection...")
    print("="*50)
    
    try:
        from google.cloud import speech_v1 as speech
        from google.cloud import texttospeech
        
        # Try to create clients
        print("\n1️⃣ Testing Speech-to-Text API...")
        speech_client = speech.SpeechClient()
        print("  ✅ Speech-to-Text client created successfully")
        
        print("\n2️⃣ Testing Text-to-Speech API...")
        tts_client = texttospeech.TextToSpeechClient()
        print("  ✅ Text-to-Speech client created successfully")
        
        # Test TTS with Ukrainian
        print("\n3️⃣ Testing Ukrainian voice synthesis...")
        synthesis_input = texttospeech.SynthesisInput(text="Привіт! Це тест.")
        voice = texttospeech.VoiceSelectionParams(
            language_code="uk-UA",
            name="uk-UA-Wavenet-A"
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16
        )
        
        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        print(f"  ✅ Generated {len(response.audio_content)} bytes of audio")
        print("\n🎉 Google Cloud is working perfectly!")
        return True
        
    except Exception as e:
        print(f"\n❌ Google Cloud test failed: {e}")
        print("\nPossible issues:")
        print("  - Credentials file is invalid")
        print("  - APIs are not enabled in Google Cloud Console")
        print("  - Billing is not enabled")
        print("  - Network/firewall issues")
        return False


if __name__ == "__main__":
    print("="*50)
    print("🔧 BINOTEL TELEPHONY CONFIGURATION CHECKER")
    print("="*50)
    print()
    
    # Load .env if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Loaded .env file\n")
    except ImportError:
        print("⚠️  python-dotenv not installed (optional)\n")
    
    # Run checks
    config_ok = check_config()
    
    if config_ok:
        # Only test Google Cloud if config is OK
        test_google_cloud()
    
    print("\n" + "="*50)

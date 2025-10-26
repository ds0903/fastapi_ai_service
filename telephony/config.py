"""
Binotel configuration for telephony service
"""
import os
from pydantic_settings import BaseSettings
from typing import Optional


class BinotelSettings(BaseSettings):
    """Binotel API configuration"""
    
    # Binotel credentials
    binotel_api_key: str = os.getenv("BINOTEL_API_KEY", "")
    binotel_api_secret: str = os.getenv("BINOTEL_API_SECRET", "")
    binotel_phone_number: str = os.getenv("BINOTEL_PHONE_NUMBER", "")
    
    # Google Cloud credentials for Speech-to-Text and TTS
    google_application_credentials: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
    
    # Voice settings for Google TTS
    voice_language: str = "uk-UA"  # Ukrainian
    voice_name: str = "uk-UA-Wavenet-A"  # Ukrainian female voice
    voice_gender: str = "FEMALE"  # MALE or FEMALE
    
    # Speech recognition settings for Google STT
    speech_language: str = "uk-UA"
    speech_encoding: str = "LINEAR16"  # Audio encoding
    speech_sample_rate: int = 8000  # Sample rate for phone audio
    
    # Call settings
    max_call_duration: int = 600  # 10 minutes max
    speech_timeout: int = 5  # seconds to wait for speech
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = 'ignore'  # Ignore extra fields from .env


# Global settings instance
binotel_settings = BinotelSettings()

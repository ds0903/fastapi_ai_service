"""
Binotel Telephony Integration Package
Provides voice call handling with Google Cloud Speech and TTS
"""

__version__ = "1.0.0"
__author__ = "Your Team"

from .config import binotel_settings
from .telephony_service import TelephonyService
from .voice_routes import router

__all__ = ["binotel_settings", "TelephonyService", "router"]

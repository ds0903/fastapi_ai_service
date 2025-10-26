"""
FastAPI routes for Binotel telephony webhooks
"""
from fastapi import APIRouter, Request, Depends, Form, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from typing import Optional
import logging
import base64

from app.database import get_db
from .telephony_service import TelephonyService
from .config import binotel_settings
from .models import BinotelWebhookRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telephony", tags=["telephony"])

# Global telephony service instance (will be initialized in main.py)
_telephony_service: Optional[TelephonyService] = None


def get_telephony_service(db: Session = Depends(get_db)) -> TelephonyService:
    """Get telephony service instance"""
    global _telephony_service
    
    if _telephony_service is None:
        raise HTTPException(
            status_code=503,
            detail="Telephony service not initialized. Please configure Binotel settings."
        )
    
    return _telephony_service


def set_telephony_service(service: TelephonyService):
    """Set global telephony service instance"""
    global _telephony_service
    _telephony_service = service
    logger.info("Telephony service initialized in routes")


@router.post("/binotel/incoming-call")
async def handle_incoming_call(
    request: Request,
    telephony_service: TelephonyService = Depends(get_telephony_service)
):
    """
    Binotel webhook for incoming calls
    Called when someone calls your Binotel number
    """
    try:
        data = await request.json()
        logger.info(f"Binotel incoming call webhook: {data}")
        
        call_id = data.get("callID")
        from_number = data.get("externalNumber")
        to_number = data.get("internalNumber")
        
        if not all([call_id, from_number, to_number]):
            logger.error("Missing required fields in webhook")
            return JSONResponse(
                status_code=400,
                content={"error": "Missing required fields"}
            )
        
        # Handle incoming call
        result = await telephony_service.handle_incoming_call(call_id, from_number, to_number)
        
        if not result.get("success"):
            logger.error(f"Failed to handle incoming call: {result.get('error')}")
            return JSONResponse(
                status_code=500,
                content={"error": result.get("error")}
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "audio_data": result.get("audio_data"),  # Base64 encoded audio
                "message": result.get("message")
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling incoming call: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@router.post("/binotel/audio-stream")
async def process_audio_stream(
    request: Request,
    callID: str = Form(...),
    audio: UploadFile = File(...),
    telephony_service: TelephonyService = Depends(get_telephony_service)
):
    """
    Binotel webhook for audio stream processing
    Called when user speaks during the call
    """
    try:
        logger.info(f"Processing audio stream for call {callID}")
        
        # Read audio data
        audio_data = await audio.read()
        
        if not audio_data:
            logger.warning(f"Empty audio data for call {callID}")
            return JSONResponse(
                status_code=400,
                content={"error": "Empty audio data"}
            )
        
        # Process audio
        result = await telephony_service.process_audio_input(callID, audio_data)
        
        if not result.get("success"):
            logger.error(f"Failed to process audio: {result.get('error')}")
            return JSONResponse(
                status_code=500,
                content={"error": result.get("error")}
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "audio_data": result.get("audio_data"),  # Base64 encoded response audio
                "message": result.get("message"),
                "should_continue": result.get("should_continue", True)
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing audio stream: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@router.post("/binotel/call-status")
async def handle_call_status(
    request: Request,
    telephony_service: TelephonyService = Depends(get_telephony_service)
):
    """
    Binotel webhook for call status updates
    Called when call status changes
    """
    try:
        data = await request.json()
        logger.info(f"Binotel call status webhook: {data}")
        
        call_id = data.get("callID")
        status = data.get("status")
        
        if not all([call_id, status]):
            logger.error("Missing required fields in status webhook")
            return JSONResponse(
                status_code=400,
                content={"error": "Missing required fields"}
            )
        
        telephony_service.handle_call_status(call_id, status)
        
        return JSONResponse(
            status_code=200,
            content={"success": True}
        )
        
    except Exception as e:
        logger.error(f"Error handling call status: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@router.get("/stats")
async def get_telephony_stats(
    telephony_service: TelephonyService = Depends(get_telephony_service)
):
    """
    Get telephony statistics
    Shows active calls and configuration status
    """
    return {
        "status": "active" if binotel_settings.binotel_api_key else "not_configured",
        "active_calls": telephony_service.get_active_calls_count(),
        "binotel_number": binotel_settings.binotel_phone_number,
        "voice_language": binotel_settings.voice_language,
        "configured": bool(binotel_settings.binotel_api_key and binotel_settings.binotel_api_secret)
    }


@router.get("/health")
async def telephony_health_check():
    """
    Health check for telephony service
    """
    is_configured = bool(
        binotel_settings.binotel_api_key and 
        binotel_settings.binotel_api_secret and
        binotel_settings.binotel_phone_number
    )
    
    return {
        "service": "telephony",
        "status": "configured" if is_configured else "not_configured",
        "binotel_configured": is_configured,
        "google_cloud_configured": bool(binotel_settings.google_application_credentials),
        "message": "Telephony service is ready" if is_configured else "Please configure Binotel credentials in .env"
    }

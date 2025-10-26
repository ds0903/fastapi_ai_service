"""
Data models for Binotel telephony service
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class CallStatus(str, Enum):
    """Call status enum"""
    INITIATED = "initiated"
    IN_PROGRESS = "in-progress"
    RINGING = "ringing"
    ANSWERED = "answered"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_ANSWER = "no-answer"
    BUSY = "busy"
    CANCELLED = "cancelled"


class CallDirection(str, Enum):
    """Call direction enum"""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class BinotelWebhookRequest(BaseModel):
    """Incoming Binotel webhook request"""
    callID: Optional[str] = None  # Unique call ID
    externalNumber: Optional[str] = None  # Client phone number
    internalNumber: Optional[str] = None  # Your Binotel number
    callType: Optional[str] = None  # "in" or "out"
    status: Optional[str] = None  # Call status
    recordingLink: Optional[str] = None  # Link to call recording
    duration: Optional[int] = None  # Call duration in seconds
    disposition: Optional[str] = None  # Call result
    
    class Config:
        populate_by_name = True


class CallSession(BaseModel):
    """Active call session data"""
    call_id: str = Field(..., description="Binotel Call ID")
    from_number: str = Field(..., description="Caller phone number")
    to_number: str = Field(..., description="Called phone number")
    client_id: Optional[str] = Field(None, description="Client ID from database")
    status: CallStatus = Field(CallStatus.INITIATED, description="Current call status")
    direction: CallDirection = Field(CallDirection.INBOUND, description="Call direction")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    duration: Optional[int] = Field(None, description="Call duration in seconds")
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    project_id: str = Field("default", description="Project ID")
    audio_stream_url: Optional[str] = None  # WebSocket or RTP stream URL
    
    class Config:
        use_enum_values = True


class VoiceMessage(BaseModel):
    """Voice message from user"""
    text: str = Field(..., description="Transcribed text from speech")
    confidence: Optional[float] = Field(None, description="Speech recognition confidence")
    language: Optional[str] = Field("uk-UA", description="Detected language")


class AudioResponse(BaseModel):
    """Audio response to send back to Binotel"""
    audio_data: bytes = Field(..., description="Audio data in required format")
    format: str = Field("wav", description="Audio format (wav, mp3, etc)")
    sample_rate: int = Field(8000, description="Sample rate in Hz")


class CallRecord(BaseModel):
    """Call record for database"""
    call_id: str
    client_id: Optional[str]
    from_number: str
    to_number: str
    status: str
    direction: str
    duration: Optional[int]
    transcript: Optional[str]
    recording_url: Optional[str]
    created_at: datetime
    project_id: str = "default"

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Date, Time, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from typing import Generator

from .config import settings

Base = declarative_base()

# Configure database engine with proper connection pooling for concurrent webhooks
engine = create_engine(
    settings.database_url,
    pool_size=20,          # Number of connections to maintain in pool
    max_overflow=30,       # Additional connections beyond pool_size  
    pool_timeout=30,       # Seconds to wait for connection
    pool_recycle=3600,     # Recycle connections after 1 hour
    pool_pre_ping=True,    # Validate connections before use
    echo=False             # Set to True for SQL query logging
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    configuration = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    bookings = relationship("Booking", back_populates="project")
    messages = relationship("MessageQueue", back_populates="project")
    dialogues = relationship("Dialogue", back_populates="project")
    feedback_records = relationship("Feedback", back_populates="project")


class MessageQueue(Base):
    __tablename__ = "message_queue"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.project_id"), nullable=False)
    client_id = Column(String, nullable=False, index=True)
    original_message = Column(Text, nullable=False)
    aggregated_message = Column(Text, nullable=False)
    status = Column(String, default="pending", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    retry_count = Column(Integer, default=0)
    
    project = relationship("Project", back_populates="messages")


class Booking(Base):
    __tablename__ = "bookings"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String, ForeignKey("projects.project_id"), nullable=False)
    specialist_name = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    time = Column(Time, nullable=False)
    client_id = Column(String, nullable=False, index=True)
    client_name = Column(String, nullable=True)
    service_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    duration_slots = Column(Integer, default=1)
    status = Column(String, default="active", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    project = relationship("Project", back_populates="bookings")


class Dialogue(Base):
    __tablename__ = "dialogues"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String, ForeignKey("projects.project_id"), nullable=False)
    client_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)  # 'client' or 'claude'
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    is_archived = Column(Boolean, default=False)
    
    project = relationship("Project", back_populates="dialogues")


class ClientLastActivity(Base):
    __tablename__ = "client_last_activity"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String, ForeignKey("projects.project_id"), nullable=False)
    client_id = Column(String, nullable=False, index=True)
    last_message_at = Column(DateTime, nullable=False)
    zip_history = Column(Text, nullable=True)
    
    __table_args__ = (
        # Ensure unique combination of project_id and client_id
        {'schema': None},
    )


class Feedback(Base):
    __tablename__ = "feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String, ForeignKey("projects.project_id"), nullable=False)
    client_id = Column(String, nullable=False, index=True)
    client_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    feedback_text = Column(Text, nullable=False)
    feedback_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    project = relationship("Project", back_populates="feedback_records")


class ProcessingCounter(Base):
    __tablename__ = "processing_counter"
    
    id = Column(Integer, primary_key=True, index=True)
    counter_value = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)


def get_or_create_counter(db: Session) -> ProcessingCounter:
    """Get or create processing counter for Claude load balancing"""
    counter = db.query(ProcessingCounter).first()
    if not counter:
        counter = ProcessingCounter()
        db.add(counter)
        db.commit()
        db.refresh(counter)
    return counter


def increment_counter(db: Session) -> int:
    """Increment and return processing counter"""
    counter = get_or_create_counter(db)
    counter.counter_value += 1
    db.commit()
    return counter.counter_value 
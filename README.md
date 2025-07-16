# Telegram Bot Backend

FastAPI backend for SendPulse Telegram bot with AI management for booking services (beauty salons, nail technicians, etc.).

## Features

- **SendPulse Integration**: Receives and processes messages from SendPulse Telegram bot
- **AI Message Processing**: Uses Claude AI for intent detection, service identification, and response generation
- **Message Queue System**: Handles message flooding and aggregation
- **Google Sheets Integration**: Syncs bookings to Google Sheets for easy management
- **Booking Management**: Create, modify, and cancel bookings with availability checking
- **Dialogue History**: Tracks client conversations with compression after 24 hours
- **Multi-Project Support**: Scalable architecture for multiple independent projects
- **PostgreSQL Database**: Persistent storage for bookings, dialogues, and configurations

## Technical Stack

- **FastAPI**: Modern, fast web framework for building APIs
- **PostgreSQL**: Database for persistent storage
- **Redis**: Message queue and caching
- **Claude AI**: Natural language processing and intent detection
- **Google Sheets API**: Booking synchronization
- **SQLAlchemy**: ORM for database operations
- **Pydantic**: Data validation and serialization

## Installation

### Prerequisites

- Python 3.8+
- PostgreSQL
- Redis
- Google Cloud Service Account (for Sheets integration)
- Claude AI API keys

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd tg-bot-backend
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create environment file**
   ```bash
   cp .env.example .env
   ```

4. **Configure environment variables**
   Edit `.env` file with your configuration:
   
   ```env
   # Database
   DATABASE_URL=postgresql://user:password@localhost/bot_db
   REDIS_URL=redis://localhost:6379
   
   # Claude AI
   CLAUDE_API_KEY_1=your_claude_api_key_1
   CLAUDE_API_KEY_2=your_claude_api_key_2
   
   # Google Sheets
   GOOGLE_CREDENTIALS_FILE=path/to/google_credentials.json
   
   # SendPulse
   SENDPULSE_WEBHOOK_SECRET=your_webhook_secret
   ```

5. **Set up Google Sheets integration**
   - Create a Google Cloud project
   - Enable Google Sheets API and Google Drive API
   - Create a service account and download credentials JSON
   - Share your Google Sheets with the service account email

6. **Initialize database**
   ```bash
   python -c "from app.database import create_tables; create_tables()"
   ```

7. **Run the application**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

## API Endpoints

### Main Webhook
- `POST /webhook/sendpulse` - Receives messages from SendPulse

### Project Management
- `GET /projects/{project_id}/config` - Get project configuration
- `POST /projects/{project_id}/config` - Update project configuration
- `GET /projects/{project_id}/stats` - Get project statistics
- `GET /projects/{project_id}/queue` - Get message queue statistics

### Health Check
- `GET /health` - Health check endpoint
- `GET /` - Basic status endpoint

## Configuration

### Project Configuration

Each project has its own configuration with:

```python
{
    "project_id": "salon_abc",
    "specialists": ["Anna", "Maria", "Elena"],
    "services": {
        "Haircut": 1,        # 1 slot (30 minutes)
        "Coloring": 3,       # 3 slots (1.5 hours)
        "Manicure": 2,       # 2 slots (1 hour)
        "Massage": 2
    },
    "work_hours": {
        "start": "09:00",
        "end": "18:00"
    },
    "google_sheet_id": "your_google_sheet_id",
    "claude_prompts": {
        "intent_detection": "Custom prompt for intent detection",
        "service_identification": "Custom prompt for service identification",
        "main_response": "Custom prompt for main response",
        "dialogue_compression": "Custom prompt for dialogue compression"
    }
}
```

### Google Sheets Format

The system creates worksheets for each specialist with columns:
- **A**: Date (DD.MM)
- **B**: Full Date (DD.MM.YYYY)
- **C**: Time (HH:MM)
- **D**: Client ID
- **E**: Client Name
- **F**: Service Name

## Message Processing Flow

1. **Message Receipt**: SendPulse sends webhook with client message
2. **Queue Processing**: Message is added to queue with flood protection
3. **Intent Detection**: Claude analyzes message to determine client intent
4. **Service Identification**: If booking intent, identify requested service
5. **Availability Check**: Query Google Sheets for available time slots
6. **Response Generation**: Claude generates appropriate response
7. **Booking Actions**: Execute booking operations if requested
8. **Response Delivery**: Send response back to client via SendPulse

## Booking Operations

### Activate Booking
Creates a new booking with:
- Specialist selection
- Date and time
- Service type
- Client information
- Duration calculation

### Reject Booking
Cancels existing booking:
- Finds booking by specialist, date, time
- Marks as cancelled
- Updates Google Sheets

### Change Booking
Modifies existing booking:
- Finds current booking
- Validates new time slot
- Updates booking details
- Syncs to Google Sheets

## Dialogue Management

- **Real-time Storage**: All conversations stored in database
- **History Tracking**: Maintains conversation context for AI
- **Automatic Archiving**: Compresses dialogues after 24 hours inactivity
- **Context Preservation**: Compressed history available for future reference

## Error Handling

- **Retry Logic**: Automatic retry for failed operations
- **Fallback Responses**: Default responses when AI fails
- **Logging**: Comprehensive error logging
- **Queue Recovery**: Message queue recovery mechanisms

## Monitoring

### Statistics Available
- Total messages processed
- Active bookings count
- Client engagement metrics
- Queue processing statistics
- Dialogue archiving metrics

### Health Checks
- Database connectivity
- Redis availability
- Claude API status
- Google Sheets access

## Development

### Running Tests
```bash
python -m pytest tests/
```

### Database Migrations
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Adding New Services
1. Update project configuration
2. Add service to `services` dict with slot count
3. Update Claude prompts if needed
4. Test booking flow

## Deployment

### Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables for Production
- Set `DEBUG=False`
- Use secure database credentials
- Configure proper Redis instance
- Set up SSL certificates
- Configure logging level

## Security

- **Webhook Verification**: Validate SendPulse webhook signatures
- **API Rate Limiting**: Prevent abuse
- **Data Encryption**: Encrypt sensitive client data
- **Access Control**: Implement proper authentication
- **Input Validation**: Sanitize all inputs

## Scaling

- **Horizontal Scaling**: Multiple FastAPI instances
- **Database Scaling**: PostgreSQL read replicas
- **Message Queue**: Redis cluster for high availability
- **Caching**: Redis caching for frequently accessed data
- **CDN**: Content delivery for static assets

## Troubleshooting

### Common Issues

1. **Claude API Rate Limits**
   - Implemented load balancing between API keys
   - Automatic retry with exponential backoff

2. **Google Sheets Quota**
   - Batch operations where possible
   - Implement caching for read operations

3. **Database Connections**
   - Connection pooling configured
   - Automatic reconnection on failures

4. **Message Queue Issues**
   - Redis persistence enabled
   - Queue recovery mechanisms

### Logs Location
- Application logs: `/var/log/app/`
- Error logs: `/var/log/app/errors.log`
- Access logs: `/var/log/app/access.log`

## Support

For technical support or feature requests, please create an issue in the repository.

## License

This project is licensed under the MIT License. 
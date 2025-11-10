# AI Voice Interview System

An advanced AI-powered voice interview platform that conducts real-time, conversational interviews with candidates using cutting-edge speech technologies and AI-driven question generation.

## 🎯 Overview

The AI Voice Interview System revolutionizes the recruitment process by providing:

- **Real-time Voice Interviews**: Natural conversation flow with AI interviewer
- **Intelligent Question Generation**: AI-powered questions based on job descriptions and resumes
- **Multi-modal Communication**: Voice, text, and avatar-based interactions
- **Comprehensive Analytics**: Detailed interview transcripts and performance reports
- **HR Dashboard**: Real-time monitoring and session management
- **Automated Reporting**: PDF reports with AI-generated assessments

## ✨ Key Features

### 🤖 AI Interviewer
- Professional HR interviewer persona with extensive experience
- Context-aware question generation using OpenAI GPT models
- Natural conversation flow with follow-up questions
- Real-time speech transcription and analysis

### 🎤 Voice Technologies
- **Speech-to-Text**: OpenAI Whisper or Deepgram Nova-3
- **Text-to-Speech**: OpenAI TTS or ElevenLabs voices
- **Avatar Integration**: Anam AI avatar for visual presence
- **Real-time Audio Processing**: LiveKit-powered communication

### 📊 Analytics & Reporting
- Complete interview transcripts with timestamps
- AI-generated performance assessments
- PDF report generation with professional formatting
- Email delivery of results to candidates and HR

### 🖥️ Dashboard & Monitoring
- Real-time session monitoring
- Interview progress tracking
- System health indicators
- Session management and analytics

### 🔒 Enterprise Security
- TLS/SSL encryption for all communications
- API key authentication
- CORS protection
- Secure file upload handling

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Frontend  │    │   Flask API     │    │   LiveKit Agent │
│   (HTML/CSS/JS) │◄──►│   (REST API)    │◄──►│   (AI Interviewer)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   File Storage  │    │   Session Mgmt  │    │   AI Services   │
│   (PDF/DOCX)    │    │   (JSON files)  │    │   (OpenAI/etc)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Technology Stack

#### Backend
- **Python 3.8+**: Core application language
- **Flask 3.1.1**: Web framework with async support
- **LiveKit 1.0.13**: Real-time communication platform
- **LiveKit Agents 1.2.16**: AI agent framework

#### AI & ML Services
- **OpenAI GPT-4o-mini**: Question generation and conversation
- **OpenAI Whisper**: Speech-to-text transcription
- **Deepgram Nova-3**: Alternative STT with enhanced accuracy
- **ElevenLabs**: High-quality text-to-speech
- **Anam AI**: Professional avatar integration

#### Frontend
- **Bootstrap 5.3**: Responsive UI framework
- **Chart.js**: Dashboard visualizations
- **LiveKit Client SDK**: Real-time communication
- **Font Awesome**: Icon library

#### Infrastructure
- **AsyncIO**: Asynchronous programming
- **SSL/TLS**: Secure communications
- **CORS**: Cross-origin resource sharing
- **File Processing**: PDF/DOCX parsing with PyPDF2, python-docx

## 🚀 Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager
- Git
- LiveKit server (local or cloud instance)

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd voice-agent
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**

   Copy and configure the environment file:
   ```bash
   cp keys.env.example keys.env
   ```

   Edit `keys.env` with your API keys:
   ```env
   # LiveKit Configuration (Required)
   LIVEKIT_URL=wss://your-livekit-server.com
   LIVEKIT_API_KEY=your_livekit_api_key
   LIVEKIT_API_SECRET=your_livekit_api_secret

   # OpenAI Configuration (Recommended)
   OPENAI_API_KEY=your_openai_api_key

   # Alternative AI Services (Optional)
   DEEPGRAM_API_KEY=your_deepgram_api_key
   ELEVENLABS_API_KEY=your_elevenlabs_api_key
   ANAM_API_KEY=your_anam_api_key

   # Email Configuration (Optional)
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your_email@gmail.com
   SMTP_PASSWORD=your_app_password
   HR_EMAIL=hr@yourcompany.com

   # Application Settings
   FLASK_ENV=development
   SECRET_KEY=your_secret_key_here
   BACKEND_URL=http://localhost:5000
   ```

4. **Start the Flask application**
   ```bash
   python main.py
   ```

5. **Start the LiveKit agent** (in a separate terminal)
   ```bash
   python interview_agent.py dev
   ```

6. **Access the application**

   Open your browser and navigate to: `http://localhost:5000`

## ⚙️ Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `LIVEKIT_URL` | LiveKit server WebSocket URL | `wss://your-server.com` |
| `LIVEKIT_API_KEY` | LiveKit API key | `your_api_key` |
| `LIVEKIT_API_SECRET` | LiveKit API secret | `your_api_secret` |

### Optional Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for AI features | None |
| `DEEPGRAM_API_KEY` | Deepgram API key for STT | None |
| `ELEVENLABS_API_KEY` | ElevenLabs API key for TTS | None |
| `ANAM_API_KEY` | Anam AI API key for avatar | None |
| `FLASK_ENV` | Environment mode | `development` |
| `SECRET_KEY` | Flask secret key | Auto-generated |
| `BACKEND_URL` | Backend server URL | `http://localhost:5000` |
| `SMTP_*` | Email configuration | Gmail defaults |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:3000,http://127.0.0.1:3000` |

### LiveKit Server Setup

#### Option 1: LiveKit Cloud (Recommended)
1. Sign up at [LiveKit Cloud](https://cloud.livekit.io)
2. Get your API key and secret
3. Use the provided server URL

#### Option 2: Local LiveKit Server
```bash
# Install LiveKit CLI
go install github.com/livekit/livekit-cli@latest

# Start local server
livekit-server --dev
```

## 📖 Usage Guide

### For Candidates

1. **Access the Interview Portal**
   - Navigate to the main application URL
   - Fill in your personal information

2. **Upload Documents**
   - Upload your resume (PDF, DOCX, or TXT)
   - Upload the job description document

3. **Start the Interview**
   - Click "Start Interview Setup"
   - Wait for document processing and question generation

4. **Voice Interview**
   - Grant microphone permissions
   - Click "Connect to Interview"
   - Respond naturally to the AI interviewer
   - The system transcribes your speech in real-time

5. **Receive Results**
   - Interview completion notification
   - Download PDF report
   - Receive email with detailed assessment

### For HR Administrators

1. **Access Dashboard**
   - Navigate to `/dashboard`
   - Monitor active interviews in real-time

2. **Session Management**
   - View interview progress
   - Access transcripts and reports
   - Track system performance

3. **Analytics**
   - Review completion rates
   - Analyze interview quality metrics
   - Generate HR reports

## 🔌 API Documentation

### REST API Endpoints

#### Sessions Management
```
POST   /api/sessions          # Create new interview session
GET    /api/sessions          # List all sessions
GET    /api/sessions/<id>     # Get session details
PUT    /api/sessions/<id>     # Update session
DELETE /api/sessions/<id>     # Delete session
```

#### File Upload
```
POST   /api/sessions/<id>/upload  # Upload JD/resume files
```

#### Reports
```
GET    /api/sessions/<id>/report   # Generate PDF report
POST   /api/sessions/<id>/email    # Email report
```

#### Dashboard
```
GET    /api/dashboard/stats        # Dashboard statistics
GET    /api/dashboard/sessions     # Active sessions
```

### LiveKit Agent Functions

The AI interviewer supports these voice commands:

- `upload_job_description`: Upload and process job description
- `upload_resume`: Upload and process candidate resume
- `generate_interview_questions`: Generate tailored questions
- `ask_next_question`: Ask specific numbered question
- `get_transcript`: Retrieve conversation transcript
- `summarize_transcript`: Generate AI summary
- `end_interview`: Complete interview with final assessment

## 🛠️ Development

### Project Structure

```
voice-agent/
├── main.py                    # Flask application entry point
├── interview_agent.py         # LiveKit AI agent
├── requirements.txt           # Python dependencies
├── keys.env                   # Environment configuration
├── app/                       # Flask application package
│   ├── __init__.py           # Application factory
│   ├── core/                 # Core functionality
│   │   ├── config.py         # Configuration management
│   │   ├── logging.py        # Logging setup
│   │   ├── errors.py         # Error handling
│   │   └── ...
│   ├── api/                  # REST API endpoints
│   │   ├── sessions.py       # Session management
│   │   ├── dashboard.py      # Dashboard API
│   │   └── ...
│   └── services/             # Business logic
├── static/                   # Static assets
│   ├── css/
│   ├── js/
│   └── dashboard/            # Dashboard assets
├── templates/                # HTML templates
│   ├── index.html           # Main interview interface
│   └── dashboard.html       # Admin dashboard
├── interview_sessions/       # Session data storage
├── interview_reports/        # Generated reports
└── logs/                     # Application logs
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html
```

### Development Commands

```bash
# Start Flask development server
python main.py

# Start LiveKit agent in development mode
python interview_agent.py dev

# Start LiveKit agent in production mode
python interview_agent.py prod

# Check environment configuration
python -c "from app.core.config import Config; c = Config(); print('Config valid:', c.validate())"
```

### Code Quality

```bash
# Format code
black .

# Sort imports
isort .

# Type checking
mypy .

# Linting
flake8 .
```

## 🔧 Troubleshooting

### Common Issues

#### 1. LiveKit Connection Failed
```
Error: Failed to connect to LiveKit room
```
**Solution**: Check your `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` in `keys.env`

#### 2. AI Services Unavailable
```
Warning: No OpenAI API key found, using fallback LLM
```
**Solution**: Add `OPENAI_API_KEY` to your environment variables

#### 3. Microphone Not Working
```
Error: STT service unavailable
```
**Solution**: Ensure microphone permissions are granted and check STT API keys

#### 4. Avatar Not Appearing
```
Warning: ANAM_API_KEY not found - avatar will not be available
```
**Solution**: Add `ANAM_API_KEY` for avatar functionality

### Debug Mode

Enable debug logging by setting:
```env
FLASK_ENV=development
```

Check logs in the `logs/` directory for detailed error information.

## 📈 Performance Optimization

### Recommended System Requirements

- **CPU**: 4+ cores recommended
- **RAM**: 8GB minimum, 16GB recommended
- **Network**: Stable internet connection (10Mbps+)
- **Storage**: 10GB free space for logs and sessions

### Scaling Considerations

- Use LiveKit Cloud for production deployments
- Implement session cleanup for old interview data
- Configure rate limiting for API endpoints
- Use async processing for report generation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Add type hints for new functions
- Write comprehensive docstrings
- Add unit tests for new features
- Update documentation for API changes


**Made with ❤️ for revolutionizing recruitment processes**
# Voice-agent-HR-AVATAR

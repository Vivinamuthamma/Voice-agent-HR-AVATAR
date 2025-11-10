import os
import ssl
from typing import Optional

class Config:
    """Application configuration management."""

    def __init__(self):
        """Initialize configuration with validation and TLS setup."""
        self._load_config()
        self.setup_tls()
        self.validate()

    def _load_config(self):
        """Load configuration from environment variables."""
        # Flask settings
        self.SECRET_KEY = os.getenv('SECRET_KEY')
        if not self.SECRET_KEY:
            import secrets
            self.SECRET_KEY = secrets.token_hex(32)  # Generate secure key if not set
        self.FLASK_ENV = os.getenv('FLASK_ENV', 'development')
        self.DEBUG = self.FLASK_ENV == 'development'

        # LiveKit settings
        self.LIVEKIT_URL = os.getenv('LIVEKIT_URL', "wss://localhost:7880")
        self.LIVEKIT_API_KEY = os.getenv('LIVEKIT_API_KEY')
        self.LIVEKIT_API_SECRET = os.getenv('LIVEKIT_API_SECRET')

        # Email settings (optional)
        self.SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
        self.SMTP_USERNAME = os.getenv('SMTP_USERNAME')
        self.SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
        self.HR_EMAIL = os.getenv('HR_EMAIL')

        # OpenAI settings (optional)
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

        # Application settings
        self.BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:5000')
        self.MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        self.ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}

        # Authentication
        self.API_KEY = os.getenv('API_KEY')
        self.REQUIRE_API_KEY = os.getenv('REQUIRE_API_KEY', 'false').lower() == 'true'

        # Session settings
        self.SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT', '3600'))  # 1 hour
        self.MAX_SESSIONS_PER_USER = int(os.getenv('MAX_SESSIONS_PER_USER', '10'))

        # CORS settings
        self.CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000,http://localhost:5000').split(',')
        if self.FLASK_ENV == 'production':
            self.CORS_ORIGINS = os.getenv('CORS_ORIGINS_PROD', 'https://yourdomain.com').split(',')

        # TLS/SSL settings
        self.TLS_SSL_CONTEXT = None

    def setup_tls(self):
        """Setup TLS context for secure HTTP connections."""
        self.TLS_SSL_CONTEXT = ssl.create_default_context()
        self.TLS_SSL_CONTEXT.minimum_version = ssl.TLSVersion.TLSv1_2  # Minimum TLS 1.2
        self.TLS_SSL_CONTEXT.maximum_version = ssl.TLSVersion.TLSv1_3  # Maximum TLS 1.3
        self.TLS_SSL_CONTEXT.check_hostname = True
        self.TLS_SSL_CONTEXT.verify_mode = ssl.CERT_REQUIRED
        self.TLS_SSL_CONTEXT.load_default_certs()

    def validate(self) -> bool:
        """Validate required configuration with logging."""
        import logging
        logger = logging.getLogger(__name__)

        required = [
            ('LIVEKIT_URL', self.LIVEKIT_URL),
            ('LIVEKIT_API_KEY', self.LIVEKIT_API_KEY),
            ('LIVEKIT_API_SECRET', self.LIVEKIT_API_SECRET),
        ]

        missing = [name for name, value in required if not value]
        if missing:
            logger.error(f"Missing required configuration: {', '.join(missing)}")
            return False

        # Warn about optional but recommended configs (only in debug mode)
        if self.DEBUG:
            optional = [
                ('SMTP_USERNAME', self.SMTP_USERNAME),
                ('OPENAI_API_KEY', self.OPENAI_API_KEY),
            ]
            missing_optional = [name for name, value in optional if not value]
            if missing_optional:
                logger.warning(f"Missing optional configuration: {', '.join(missing_optional)}")

        return True

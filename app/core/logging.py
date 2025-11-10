import logging
import logging.handlers
import sys
import os
from pathlib import Path

def setup_logging(config=None, level=None):
    """Configure logging for the application with rotation and proper error handling."""
    # Check if logging is already configured to avoid duplicate handlers
    root_logger = logging.getLogger()
    if root_logger.handlers:
        # Logging already configured, don't add duplicate handlers
        return root_logger

    if config is None:
        from .config import Config
        config = Config()

    # Determine log level
    if level is None:
        level = getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper(), logging.INFO)

    logger = logging.getLogger()
    logger.setLevel(level)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # Rotating file handler
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / os.getenv('LOG_FILE', 'app.log')

    try:
        fh = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        fh.setLevel(getattr(logging, os.getenv('LOG_FILE_LEVEL', 'DEBUG').upper(), logging.DEBUG))
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except (OSError, PermissionError) as e:
        logger.warning(f"Could not set up file logging: {e}. Continuing with console only.")

    # Suppress noisy loggers
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('livekit').setLevel(logging.ERROR)

    return logger

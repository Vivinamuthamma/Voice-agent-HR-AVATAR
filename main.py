#!/usr/bin/env python3
import os
import sys
import io
import logging
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
 
# Configure logging before importing other modules
# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    try:
        # Try to set console to UTF-8
        import subprocess
        subprocess.run(['chcp', '65001'], shell=True, capture_output=True)
    except Exception as e:
        print(f"⚠️ Failed to set console code page to UTF-8: {e}")

from app.core.logging import setup_logging

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

def check_environment():
    """Check for required environment variables and files."""
    logger.info("🔍 Checking environment configuration...")

    keys_env_path = Path(__file__).parent / 'keys.env'
    if keys_env_path.exists():
        # Load from keys.env (development)
        try:
            from dotenv import load_dotenv
            load_dotenv(keys_env_path)
            logger.info("✅ Environment variables loaded from keys.env")
        except ImportError:
            logger.warning("⚠️ python-dotenv not installed. Install with: pip install python-dotenv")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to load environment variables: {e}")
            return False
    else:
     
        logger.info("✅ Using system environment variables (keys.env not found)")

    # Check critical environment variables
    critical_vars = {
        'LIVEKIT_API_KEY': 'LiveKit API key',
        'LIVEKIT_API_SECRET': 'LiveKit API secret',
        'LIVEKIT_URL': 'LiveKit server URL'
    }

    missing_vars = []
    placeholder_vars = []

    for var, description in critical_vars.items():
        value = os.getenv(var)
        if not value:
            missing_vars.append(f"{var} ({description})")
        elif value.startswith('your_') and value.endswith('_here'):
            placeholder_vars.append(f"{var} ({description})")

    if missing_vars:
        logger.error(f"❌ Missing critical environment variables: {', '.join(missing_vars)}")
        return False

    if placeholder_vars:
        logger.error(f"❌ Placeholder values detected for: {', '.join(placeholder_vars)}")
        logger.error("Please replace placeholder values with your actual API keys")
        return False

    # Check optional but recommended variables
    optional_vars = {
        'OPENAI_API_KEY': 'AI question generation'
    }

    missing_optional = []
    for var, description in optional_vars.items():
        value = os.getenv(var)
        if not value or (value.startswith('your_') and value.endswith('_here')):
            missing_optional.append(f"{var} ({description})")

    if missing_optional:
        logger.warning(f"⚠️ Optional services not configured: {', '.join(missing_optional)}")
        logger.warning("Some features may not work properly without these services")

    logger.info("✅ Environment configuration check completed")
    return True

def check_dependencies():
    """Check for required Python packages."""
    logger.info("📦 Checking Python dependencies...")
    
    required_packages = [
        ('flask', 'Flask web framework'),
        ('flask_cors', 'Flask CORS support'),
        ('livekit', 'LiveKit SDK'),
        ('aiohttp', 'Async HTTP client'),
        ('asyncio', 'Async support (built-in)'),
    ]
    

    missing_required = []
    
    for package, description in required_packages:
        try:
            __import__(package.replace('-', '_'))
            logger.debug(f"✅ {package} - {description}")
        except ImportError:
            missing_required.append(f"{package} ({description})")
 
    
    if missing_required:
        logger.error(f"❌ Missing required packages: {', '.join(missing_required)}")
        logger.error("Install with: pip install -r requirements.txt")
        return False


def main():
    """Main entry point with comprehensive error handling."""
    logger.info("🚀 Starting AI Voice Interview System...")
    
    try:
        # Environment checks
        if not check_environment():
            logger.error("❌ Environment check failed. Please fix the issues above and try again.")
            return 1
        
        # Import and run the Flask app
        logger.info("🌐 Starting Flask application...")

        try:
            from app import create_app
            app = create_app()
            
            # Check if we're in development or production mode
            flask_env = os.getenv('FLASK_ENV', 'development').lower()
            debug_mode = flask_env == 'development'
            
            if debug_mode:
                logger.info("🔧 Running in development mode")
                host = '127.0.0.1'
                port = 5000
            else:
                logger.info("🚀 Running in production mode")
                host = '0.0.0.0'
                port = int(os.getenv('PORT', 5000))
            
            logger.info(f"🌐 Flask app will be available at http://{host}:{port}")
            logger.info("📱 Open the URL in your browser to access the interview system")
            logger.info("🤖 Make sure to start the LiveKit agent separately using: python interview_agent.py dev")
            
            # Run the Flask app
            app.run(
                host=host,
                port=port,
                debug=debug_mode,
                threaded=True
            )
            
            return 0
            
        except ImportError as e:
            logger.error(f"❌ Failed to import Flask app: {e}")
            logger.error("Make sure all required files are present and dependencies are installed")
            return 1
            
        except Exception as e:
            logger.error(f"❌ Flask app error: {e}", exc_info=True)
            return 1
    
    except KeyboardInterrupt:
        logger.info("⏹️ Application stopped by user")
        return 0
    
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}", exc_info=True)
        return 1

if __name__ == '__main__':
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"💥 Critical error during startup: {e}", file=sys.stderr)
        sys.exit(1)

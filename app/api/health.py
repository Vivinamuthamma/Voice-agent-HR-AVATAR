from flask import Blueprint, jsonify
import datetime
from flask import g
from app.services.livekit_service import LiveKitService
from app.core.config import Config

health_bp = Blueprint('health', __name__)

@health_bp.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    livekit_manager = getattr(g, 'livekit_manager', None)
    return jsonify({
        "status": "healthy",
        "livekit_connected": livekit_manager is not None,
        "timestamp": datetime.datetime.now().isoformat()
    })

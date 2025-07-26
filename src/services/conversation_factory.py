"""
Factory for creating conversation service instances
"""

import os
import logging
from typing import Union
from .conversation_service import ConversationService
from .redis_conversation_service import RedisConversationService

logger = logging.getLogger(__name__)

def create_conversation_service() -> Union[ConversationService, RedisConversationService]:
    """
    Create appropriate conversation service based on environment
    
    Returns:
        ConversationService or RedisConversationService instance
    """
    redis_url = os.environ.get('REDIS_URL')
    use_redis = os.environ.get('USE_REDIS', 'false').lower() == 'true'
    
    if redis_url and use_redis:
        try:
            # Try to create Redis service
            service = RedisConversationService(redis_url)
            if service.health_check():
                logger.info("Using Redis-based conversation service")
                return service
            else:
                logger.warning("Redis health check failed, falling back to in-memory storage")
        except Exception as e:
            logger.error(f"Failed to initialize Redis service: {e}, falling back to in-memory storage")
    
    # Fallback to in-memory service
    logger.info("Using in-memory conversation service")
    return ConversationService()
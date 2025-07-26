"""
Redis-based conversation service for persistent storage
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

class RedisConversationService:
    """Redis-based conversation history management"""
    
    def __init__(self, redis_url: str = None, ttl_days: int = 7):
        """
        Initialize Redis conversation service
        
        Args:
            redis_url: Redis connection URL (defaults to localhost)
            ttl_days: Number of days to keep conversations (default 7)
        """
        self.redis_url = redis_url or os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        self.ttl_seconds = ttl_days * 24 * 60 * 60
        self.max_messages_per_user = int(os.environ.get('MAX_MESSAGES_PER_USER', '100'))
        self.redis_client = None
        self._connect()
    
    def _connect(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                connection_pool_kwargs={
                    'max_connections': 50,
                    'retry_on_timeout': True
                }
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Successfully connected to Redis")
        except RedisError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
    
    def _get_conversation_key(self, user_id: str) -> str:
        """Get Redis key for user conversation"""
        return f"conversation:{user_id}"
    
    def _get_metadata_key(self, user_id: str) -> str:
        """Get Redis key for conversation metadata"""
        return f"conversation_meta:{user_id}"
    
    def add_message(self, user_id: str, role: str, content: str, message_type: str = "text", metadata: dict = None):
        """Add a message to user's conversation history"""
        if not self.redis_client:
            logger.error("Redis client not connected")
            return
        
        try:
            conv_key = self._get_conversation_key(user_id)
            meta_key = self._get_metadata_key(user_id)
            
            # Create message
            message = {
                "role": role,
                "content": content,
                "message_type": message_type,
                "metadata": metadata or {},
                "timestamp": datetime.now().isoformat()
            }
            
            # Add message to conversation list
            self.redis_client.rpush(conv_key, json.dumps(message))
            
            # Trim to max messages
            self.redis_client.ltrim(conv_key, -self.max_messages_per_user, -1)
            
            # Update metadata
            self.redis_client.hset(meta_key, mapping={
                "last_activity": datetime.now().isoformat(),
                "message_count": self.redis_client.llen(conv_key)
            })
            
            # Set TTL
            self.redis_client.expire(conv_key, self.ttl_seconds)
            self.redis_client.expire(meta_key, self.ttl_seconds)
            
            logger.debug(f"Added {role} message for user {user_id}")
            
        except RedisError as e:
            logger.error(f"Redis error adding message: {e}")
    
    def get_conversation_history(self, user_id: str, limit: int = None) -> List[Dict]:
        """Get conversation history for a user"""
        if not self.redis_client:
            logger.error("Redis client not connected")
            return []
        
        try:
            conv_key = self._get_conversation_key(user_id)
            
            # Get messages
            if limit:
                messages = self.redis_client.lrange(conv_key, -limit, -1)
            else:
                messages = self.redis_client.lrange(conv_key, 0, -1)
            
            # Parse JSON messages
            parsed_messages = []
            for msg in messages:
                try:
                    parsed_messages.append(json.loads(msg))
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse message: {msg}")
            
            return parsed_messages
            
        except RedisError as e:
            logger.error(f"Redis error getting conversation: {e}")
            return []
    
    def get_messages_for_context(self, user_id: str, max_messages: int = 10) -> List[Dict]:
        """Get recent messages for AI context"""
        return self.get_conversation_history(user_id, limit=max_messages)
    
    def clear_conversation(self, user_id: str):
        """Clear a user's conversation history"""
        if not self.redis_client:
            logger.error("Redis client not connected")
            return
        
        try:
            conv_key = self._get_conversation_key(user_id)
            meta_key = self._get_metadata_key(user_id)
            
            self.redis_client.delete(conv_key, meta_key)
            logger.info(f"Cleared conversation for user {user_id}")
            
        except RedisError as e:
            logger.error(f"Redis error clearing conversation: {e}")
    
    def set_last_response_id(self, user_id: str, response_id: str):
        """Store the last response ID for conversation continuity"""
        if not self.redis_client:
            return
        
        try:
            meta_key = self._get_metadata_key(user_id)
            self.redis_client.hset(meta_key, "last_response_id", response_id)
            self.redis_client.expire(meta_key, self.ttl_seconds)
        except RedisError as e:
            logger.error(f"Redis error setting response ID: {e}")
    
    def get_last_response_id(self, user_id: str) -> Optional[str]:
        """Get the last response ID for a user"""
        if not self.redis_client:
            return None
        
        try:
            meta_key = self._get_metadata_key(user_id)
            return self.redis_client.hget(meta_key, "last_response_id")
        except RedisError as e:
            logger.error(f"Redis error getting response ID: {e}")
            return None
    
    @property
    def conversations(self) -> Dict:
        """Get all active conversations (for compatibility)"""
        if not self.redis_client:
            return {}
        
        try:
            # Get all conversation keys
            conv_keys = self.redis_client.keys("conversation:*")
            conversations = {}
            
            for key in conv_keys:
                user_id = key.split(":", 1)[1]
                meta_key = self._get_metadata_key(user_id)
                
                # Get metadata
                metadata = self.redis_client.hgetall(meta_key)
                message_count = int(metadata.get("message_count", 0))
                
                conversations[user_id] = {
                    "messages": [],  # Don't load all messages
                    "message_count": message_count,
                    "last_activity": metadata.get("last_activity", "Unknown")
                }
            
            return conversations
            
        except RedisError as e:
            logger.error(f"Redis error getting conversations: {e}")
            return {}
    
    def health_check(self) -> bool:
        """Check if Redis is healthy"""
        if not self.redis_client:
            return False
        
        try:
            return self.redis_client.ping()
        except RedisError:
            return False
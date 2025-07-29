import logging
import threading
import json
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from src.utils.redis_manager import get_redis_manager, RedisConnectionManager
from src.utils.memory_monitor import get_memory_monitor, MemoryStats

logger = logging.getLogger(__name__)

class ConversationService:
    """
    Unified conversation service with graceful Redis/in-memory fallback.
    
    Features:
    - Automatic fallback to in-memory storage when Redis is unavailable
    - Seamless Redis integration with circuit breaker pattern
    - Thread-safe operations with RLock for re-entrant calls
    - Consistent API regardless of storage backend
    - Conversation expiration and cleanup
    - Statistics and health monitoring
    """
    
    def __init__(self, redis_url: str = None, enable_redis: bool = True, 
                 conversation_ttl_hours: int = 24, enable_memory_monitoring: bool = True):
        """
        Initialize conversation service with Redis fallback capability.
        
        Args:
            redis_url: Redis connection URL (optional)
            enable_redis: Whether to attempt Redis connection
            conversation_ttl_hours: Hours after which conversations expire
            enable_memory_monitoring: Whether to enable memory-based cleanup
        """
        # In-memory storage for conversations (fallback + primary for non-Redis mode)
        # Format: {user_id: {"messages": [...], "created_at": datetime, "last_activity": datetime, "last_response_id": str}}
        self.conversations: Dict[str, Dict] = {}
        
        # Thread safety: RLock allows the same thread to acquire the lock multiple times
        # This is important for methods that call other methods that also need the lock
        self._lock = threading.RLock()
        
        # Configuration
        self.max_messages_per_user = 100  # Limit memory usage
        self.max_total_conversations = 1000  # Global limit for demo
        self.conversation_ttl_hours = conversation_ttl_hours
        self.enable_redis = enable_redis
        self.enable_memory_monitoring = enable_memory_monitoring
        
        # Redis integration
        self.redis_manager: Optional[RedisConnectionManager] = None
        self._redis_available = False
        self._last_redis_check = None
        self._redis_check_interval = 60  # Check Redis health every 60 seconds
        
        # Statistics
        self._stats = {
            'total_operations': 0,
            'redis_operations': 0,
            'fallback_operations': 0,
            'redis_failures': 0,
            'last_redis_check': None,
            'storage_mode': 'in_memory'  # 'redis', 'in_memory', 'hybrid'
        }
        
        # Initialize Redis if enabled
        if self.enable_redis:
            self._initialize_redis(redis_url)
        
        # Initialize memory monitoring integration
        self.memory_monitor = None
        if self.enable_memory_monitoring:
            self._initialize_memory_monitoring()
    
    def _initialize_redis(self, redis_url: str = None):
        """Initialize Redis connection manager."""
        try:
            self.redis_manager = get_redis_manager(redis_url=redis_url)
            health_status = self.redis_manager.health_check()
            self._redis_available = health_status.get('is_healthy', False)
            self._last_redis_check = datetime.now()
            
            if self._redis_available:
                self._stats['storage_mode'] = 'redis'
                logger.info("ConversationService initialized with Redis backend")
            else:
                self._stats['storage_mode'] = 'in_memory'
                logger.warning("Redis health check failed, using in-memory fallback")
                
        except Exception as e:
            logger.error(f"Failed to initialize Redis for ConversationService: {e}")
            self._redis_available = False
            self._stats['storage_mode'] = 'in_memory'
    
    def _initialize_memory_monitoring(self):
        """Initialize memory monitoring integration."""
        try:
            self.memory_monitor = get_memory_monitor()
            
            # Register cleanup callbacks with memory monitor
            self.memory_monitor.add_cleanup_callback(self._memory_cleanup_callback)
            
            logger.info("ConversationService integrated with memory monitoring")
            
        except Exception as e:
            logger.error(f"Failed to initialize memory monitoring: {e}")
            self.memory_monitor = None
    
    def _check_redis_health(self) -> bool:
        """Check Redis health periodically."""
        if not self.enable_redis or not self.redis_manager:
            return False
        
        now = datetime.now()
        if (self._last_redis_check and 
            (now - self._last_redis_check).total_seconds() < self._redis_check_interval):
            return self._redis_available
        
        try:
            health_status = self.redis_manager.health_check()
            self._redis_available = health_status.get('is_healthy', False)
            self._last_redis_check = now
            self._stats['last_redis_check'] = now.isoformat()
            
            if self._redis_available and self._stats['storage_mode'] == 'in_memory':
                self._stats['storage_mode'] = 'redis'
                logger.info("Redis connection restored - switching back to Redis storage")
            elif not self._redis_available and self._stats['storage_mode'] == 'redis':
                self._stats['storage_mode'] = 'in_memory'
                logger.warning("Redis connection lost - falling back to in-memory storage")
                
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            self._redis_available = False
            self._stats['redis_failures'] += 1
            
        return self._redis_available
    
    def _get_conversation_key(self, user_id: str) -> str:
        """Generate Redis key for conversation."""
        return f"conversation:{user_id}"
    
    def _serialize_conversation(self, conversation: Dict) -> str:
        """Serialize conversation data for Redis storage."""
        # Convert datetime objects to ISO format for JSON serialization
        serializable_conv = conversation.copy()
        for key in ['created_at', 'last_activity']:
            if key in serializable_conv and isinstance(serializable_conv[key], datetime):
                serializable_conv[key] = serializable_conv[key].isoformat()
        
        # Convert message timestamps
        for message in serializable_conv.get('messages', []):
            if 'timestamp' in message and isinstance(message['timestamp'], datetime):
                message['timestamp'] = message['timestamp'].isoformat()
        
        return json.dumps(serializable_conv)
    
    def _deserialize_conversation(self, data: str) -> Dict:
        """Deserialize conversation data from Redis."""
        conversation = json.loads(data)
        
        # Convert ISO format back to datetime objects
        for key in ['created_at', 'last_activity']:
            if key in conversation and conversation[key]:
                conversation[key] = datetime.fromisoformat(conversation[key])
        
        # Convert message timestamps
        for message in conversation.get('messages', []):
            if 'timestamp' in message and message['timestamp']:
                message['timestamp'] = datetime.fromisoformat(message['timestamp'])
        
        return conversation
    
    def _load_from_redis(self, user_id: str) -> Optional[Dict]:
        """Load conversation from Redis with fallback."""
        if not self._check_redis_health():
            return None
        
        def redis_operation(client):
            key = self._get_conversation_key(user_id)
            data = client.get(key)
            if data:
                return self._deserialize_conversation(data.decode('utf-8'))
            return None
        
        def fallback():
            # Return None to indicate fallback to in-memory
            return None
        
        result = self.redis_manager.execute_with_fallback(
            redis_operation, fallback, f"load_conversation_{user_id}"
        )
        
        if result is not None:
            self._stats['redis_operations'] += 1
        else:
            self._stats['fallback_operations'] += 1
        
        return result
    
    def _save_to_redis(self, user_id: str, conversation: Dict) -> bool:
        """Save conversation to Redis with fallback."""
        if not self._check_redis_health():
            return False
        
        def redis_operation(client):
            key = self._get_conversation_key(user_id)
            serialized_data = self._serialize_conversation(conversation)
            
            # Set with TTL
            ttl_seconds = self.conversation_ttl_hours * 3600
            return client.setex(key, ttl_seconds, serialized_data)
        
        def fallback():
            return False
        
        success = self.redis_manager.execute_with_fallback(
            redis_operation, fallback, f"save_conversation_{user_id}"
        )
        
        if success:
            self._stats['redis_operations'] += 1
            return True
        else:
            self._stats['fallback_operations'] += 1
            return False
    
    def _delete_from_redis(self, user_id: str) -> bool:
        """Delete conversation from Redis."""
        if not self._check_redis_health():
            return False
        
        def redis_operation(client):
            key = self._get_conversation_key(user_id)
            return client.delete(key) > 0
        
        def fallback():
            return False
        
        success = self.redis_manager.execute_with_fallback(
            redis_operation, fallback, f"delete_conversation_{user_id}"
        )
        
        if success:
            self._stats['redis_operations'] += 1
        else:
            self._stats['fallback_operations'] += 1
        
        return success
    
    def _get_conversation(self, user_id: str) -> Dict:
        """Get conversation with Redis fallback to in-memory."""
        self._stats['total_operations'] += 1
        
        # Try Redis first if available
        if self._redis_available:
            redis_conversation = self._load_from_redis(user_id)
            if redis_conversation is not None:
                # Update in-memory cache for hybrid access
                self.conversations[user_id] = redis_conversation
                return redis_conversation
        
        # Fall back to in-memory storage
        if user_id not in self.conversations:
            # Create new conversation
            conversation = {
                "messages": [],
                "created_at": datetime.now(),
                "last_activity": datetime.now(),
                "last_response_id": None
            }
            self.conversations[user_id] = conversation
            
            # Try to save to Redis if available
            if self._redis_available:
                self._save_to_redis(user_id, conversation)
                
            logger.info(f"Created new conversation for user {user_id}")
        
        return self.conversations[user_id]
    
    def _update_conversation(self, user_id: str, conversation: Dict):
        """Update conversation in both storage backends."""
        # Update in-memory storage
        self.conversations[user_id] = conversation
        
        # Try to save to Redis
        if self._redis_available:
            self._save_to_redis(user_id, conversation)
    
    def add_message(self, user_id: str, role: str, content: str, message_type: str = "text", metadata: dict = None):
        """Add a message to user's conversation history with optional metadata"""
        with self._lock:
            try:
                # Get conversation with Redis fallback
                conversation = self._get_conversation(user_id)
                
                # Add message with optional metadata
                message = {
                    "role": role,  # "user" or "assistant"
                    "content": content,
                    "message_type": message_type,  # "text", "image", "file", "mixed"
                    "metadata": metadata or {},
                    "timestamp": datetime.now()
                }
                
                conversation["messages"].append(message)
                conversation["last_activity"] = datetime.now()
                
                # Trim old messages if necessary
                if len(conversation["messages"]) > self.max_messages_per_user:
                    # Keep the most recent messages
                    conversation["messages"] = conversation["messages"][-self.max_messages_per_user:]
                    logger.debug(f"Trimmed conversation history for user {user_id}")
                
                # Update conversation in both storage backends
                self._update_conversation(user_id, conversation)
                
                # Global conversation limit management (only for in-memory)
                self._manage_global_limits()
                
                logger.debug(f"Added {message_type} {role} message for user {user_id} (total: {len(conversation['messages'])})")
                
            except Exception as e:
                logger.error(f"Error adding message for user {user_id}: {str(e)}")
                # Lock is automatically released by the context manager even on exception
    
    def get_last_response_id(self, user_id: str) -> Optional[str]:
        """Get the last response ID for Responses API conversation continuity"""
        with self._lock:
            try:
                conversation = self._get_conversation(user_id)
                if not conversation["messages"]:  # Empty conversation
                    return None
                return conversation.get("last_response_id")
                
            except Exception as e:
                logger.error(f"Error getting last response ID for user {user_id}: {str(e)}")
                return None
    
    def set_last_response_id(self, user_id: str, response_id: str):
        """Set the last response ID for Responses API conversation continuity"""
        with self._lock:
            try:
                # Get conversation with Redis fallback
                conversation = self._get_conversation(user_id)
                
                # Update the response ID and last activity
                conversation["last_response_id"] = response_id
                conversation["last_activity"] = datetime.now()
                
                # Update conversation in both storage backends
                self._update_conversation(user_id, conversation)
                
                logger.debug(f"Set last_response_id for user {user_id}: {response_id}")
                
            except Exception as e:
                logger.error(f"Error setting response ID for user {user_id}: {str(e)}")
                # Lock is automatically released by the context manager even on exception
    
    def get_conversation_history(self, user_id: str) -> List[Dict]:
        """Get conversation history for a user (legacy support - less needed with Responses API)"""
        with self._lock:
            try:
                conversation = self._get_conversation(user_id)
                
                # Return messages in format expected by OpenAI
                messages = []
                for msg in conversation["messages"]:
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
                
                return messages
                
            except Exception as e:
                logger.error(f"Error getting conversation history for user {user_id}: {str(e)}")
                return []
    
    def get_conversation_stats(self, user_id: str) -> Dict:
        """Get conversation statistics for a user"""
        with self._lock:
            try:
                # Try to get from Redis first, then fall back to in-memory
                conversation = None
                if self._redis_available:
                    conversation = self._load_from_redis(user_id)
                
                if conversation is None and user_id in self.conversations:
                    conversation = self.conversations[user_id]
                
                if conversation is None:
                    return {
                        "exists": False,
                        "message_count": 0,
                        "created_at": None,
                        "last_activity": None,
                        "has_response_id": False,
                        "last_response_id": None,
                        "storage_backend": "none"
                    }
                
                return {
                    "exists": True,
                    "message_count": len(conversation["messages"]),
                    "created_at": conversation["created_at"].isoformat(),
                    "last_activity": conversation["last_activity"].isoformat(),
                    "has_response_id": bool(conversation.get("last_response_id")),
                    "last_response_id": conversation.get("last_response_id"),
                    "storage_backend": "redis" if self._redis_available else "in_memory"
                }
                
            except Exception as e:
                logger.error(f"Error getting conversation stats for user {user_id}: {str(e)}")
                return {
                    "exists": False,
                    "message_count": 0,
                    "created_at": None,
                    "last_activity": None,
                    "has_response_id": False,
                    "last_response_id": None,
                    "storage_backend": "error",
                    "error": str(e)
                }
    
    def clear_conversation(self, user_id: str) -> bool:
        """Clear conversation history for a user"""
        with self._lock:
            try:
                cleared = False
                
                # Delete from Redis if available
                if self._redis_available:
                    redis_cleared = self._delete_from_redis(user_id)
                    if redis_cleared:
                        cleared = True
                
                # Delete from in-memory storage
                if user_id in self.conversations:
                    del self.conversations[user_id]
                    cleared = True
                
                if cleared:
                    logger.info(f"Cleared conversation for user {user_id}")
                
                return cleared
                
            except Exception as e:
                logger.error(f"Error clearing conversation for user {user_id}: {str(e)}")
                return False
    
    def get_all_conversations_stats(self) -> Dict:
        """Get statistics for all conversations"""
        with self._lock:
            try:
                # Get in-memory stats
                in_memory_stats = self._get_in_memory_stats()
                
                # Combine with overall service stats
                combined_stats = {
                    **in_memory_stats,
                    "redis_available": self._redis_available,
                    "storage_mode": self._stats['storage_mode'],
                    "service_stats": self._stats.copy()
                }
                
                return combined_stats
                
            except Exception as e:
                logger.error(f"Error getting all conversations stats: {str(e)}")
                return {
                    "total_users": 0,
                    "total_messages": 0,
                    "active_conversations": 0,
                    "conversations_with_response_ids": 0,
                    "redis_available": False,
                    "storage_mode": "error",
                    "error": str(e)
                }
    
    def _get_in_memory_stats(self) -> Dict:
        """Get statistics for in-memory conversations."""
        total_messages = sum(
            len(conv["messages"]) 
            for conv in self.conversations.values()
        )
        
        conversations_with_response_ids = sum(
            1 for conv in self.conversations.values()
            if conv.get("last_response_id")
        )
        
        return {
            "total_users": len(self.conversations),
            "total_messages": total_messages,
            "active_conversations": len([
                conv for conv in self.conversations.values()
                if len(conv["messages"]) > 0
            ]),
            "conversations_with_response_ids": conversations_with_response_ids
        }
    
    def _manage_global_limits(self):
        """Manage global conversation limits for in-memory storage (Redis handles its own TTL)"""
        # Note: This method is called from add_message which already holds the lock
        # Using RLock allows re-entrant locking from the same thread
        # Only apply to in-memory storage since Redis has TTL-based expiration
        if len(self.conversations) > self.max_total_conversations:
            # Remove oldest conversations (by last activity)
            conversations_by_activity = [
                (user_id, conv["last_activity"])
                for user_id, conv in self.conversations.items()
            ]
            
            # Sort by last activity (oldest first)
            conversations_by_activity.sort(key=lambda x: x[1])
            
            # Remove oldest 10% of conversations
            num_to_remove = max(1, len(conversations_by_activity) // 10)
            
            for i in range(num_to_remove):
                user_id_to_remove = conversations_by_activity[i][0]
                
                # Remove from both in-memory and Redis if available
                del self.conversations[user_id_to_remove]
                if self._redis_available:
                    self._delete_from_redis(user_id_to_remove)
                
                logger.info(f"Removed old conversation for user {user_id_to_remove} (global limit management)")
    
    def cleanup_old_conversations(self, max_age_hours: int = None):
        """Clean up conversations older than specified hours (for maintenance)"""
        with self._lock:
            try:
                if max_age_hours is None:
                    max_age_hours = self.conversation_ttl_hours
                
                current_time = datetime.now()
                users_to_remove = []
                
                # First pass: identify conversations to remove from in-memory storage
                for user_id, conv in self.conversations.items():
                    age_hours = (current_time - conv["last_activity"]).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        users_to_remove.append((user_id, age_hours))
                
                # Second pass: remove identified conversations atomically
                for user_id, age_hours in users_to_remove:
                    # Remove from in-memory
                    del self.conversations[user_id]
                    
                    # Remove from Redis if available
                    if self._redis_available:
                        self._delete_from_redis(user_id)
                    
                    logger.info(f"Cleaned up old conversation for user {user_id} (age: {age_hours:.1f} hours)")
                
                return len(users_to_remove)
                
            except Exception as e:
                logger.error(f"Error during conversation cleanup: {str(e)}")
                return 0
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status including Redis connectivity."""
        with self._lock:
            try:
                health_status = {
                    "service_healthy": True,
                    "storage_mode": self._stats['storage_mode'],
                    "redis_enabled": self.enable_redis,
                    "redis_available": self._redis_available,
                    "last_redis_check": self._last_redis_check.isoformat() if self._last_redis_check else None,
                    "statistics": self._stats.copy(),
                    "in_memory_conversations": len(self.conversations),
                    "max_conversations": self.max_total_conversations,
                    "max_messages_per_user": self.max_messages_per_user,
                    "conversation_ttl_hours": self.conversation_ttl_hours
                }
                
                # Add Redis health information if available
                if self.redis_manager:
                    redis_health = self.redis_manager.health_check()
                    health_status["redis_health"] = redis_health
                    
                    redis_stats = self.redis_manager.get_statistics()
                    health_status["redis_statistics"] = redis_stats
                
                return health_status
                
            except Exception as e:
                logger.error(f"Error getting health status: {str(e)}")
                return {
                    "service_healthy": False,
                    "error": str(e),
                    "storage_mode": "error"
                }
    
    def force_redis_reconnect(self) -> bool:
        """Force Redis reconnection (for admin/debugging purposes)."""
        with self._lock:
            try:
                if not self.enable_redis:
                    logger.warning("Redis is disabled, cannot reconnect")
                    return False
                
                if self.redis_manager:
                    self.redis_manager.reset_circuit()
                    health_status = self.redis_manager.health_check()
                    self._redis_available = health_status.get('is_healthy', False)
                    self._last_redis_check = datetime.now()
                    
                    if self._redis_available:
                        self._stats['storage_mode'] = 'redis'
                        logger.info("Forced Redis reconnection successful")
                        return True
                    else:
                        self._stats['storage_mode'] = 'in_memory'
                        logger.warning("Forced Redis reconnection failed")
                        return False
                else:
                    logger.error("Redis manager not initialized")
                    return False
                    
            except Exception as e:
                logger.error(f"Error during forced Redis reconnection: {str(e)}")
                return False
    
    def _memory_cleanup_callback(self, cleanup_level: str, memory_stats: MemoryStats):
        """
        Callback method for memory monitor to trigger conversation cleanup.
        
        Args:
            cleanup_level: Level of cleanup ('light', 'aggressive', 'emergency')
            memory_stats: Current memory statistics
        """
        try:
            if cleanup_level == "light":
                self._perform_light_memory_cleanup(memory_stats)
            elif cleanup_level == "aggressive":
                self._perform_aggressive_memory_cleanup(memory_stats)
            elif cleanup_level == "emergency":
                self._perform_emergency_memory_cleanup(memory_stats)
            
            logger.info(f"Completed {cleanup_level} memory cleanup for conversations")
            
        except Exception as e:
            logger.error(f"Error during {cleanup_level} memory cleanup: {e}")
    
    def _perform_light_memory_cleanup(self, memory_stats: MemoryStats):
        """Perform light memory cleanup by removing old and inactive conversations."""
        with self._lock:
            try:
                cleanup_count = 0
                cutoff_time = datetime.now() - timedelta(hours=self.conversation_ttl_hours // 2)
                users_to_remove = []
                
                # Identify old conversations for removal
                for user_id, conv in self.conversations.items():
                    if conv["last_activity"] < cutoff_time and len(conv["messages"]) < 5:
                        users_to_remove.append(user_id)
                
                # Remove identified conversations
                for user_id in users_to_remove:
                    del self.conversations[user_id]
                    if self._redis_available:
                        self._delete_from_redis(user_id)
                    cleanup_count += 1
                
                logger.info(f"Light cleanup: removed {cleanup_count} old conversations")
                
            except Exception as e:
                logger.error(f"Error during light memory cleanup: {e}")
    
    def _perform_aggressive_memory_cleanup(self, memory_stats: MemoryStats):
        """Perform aggressive memory cleanup by removing conversations and trimming messages."""
        with self._lock:
            try:
                cleanup_count = 0
                
                # First, perform light cleanup
                self._perform_light_memory_cleanup(memory_stats)
                
                # Trim messages in remaining conversations
                cutoff_time = datetime.now() - timedelta(hours=self.conversation_ttl_hours // 4)
                
                for user_id, conv in self.conversations.items():
                    original_count = len(conv["messages"])
                    
                    # More aggressive message trimming
                    if original_count > 20:
                        conv["messages"] = conv["messages"][-20:]  # Keep only last 20
                        
                        # Update in Redis if available
                        if self._redis_available:
                            self._save_to_redis(user_id, conv)
                        
                        cleanup_count += original_count - len(conv["messages"])
                
                # Remove conversations with no recent activity
                users_to_remove = []
                for user_id, conv in self.conversations.items():
                    if conv["last_activity"] < cutoff_time:
                        users_to_remove.append(user_id)
                
                for user_id in users_to_remove:
                    del self.conversations[user_id]
                    if self._redis_available:
                        self._delete_from_redis(user_id)
                    cleanup_count += 1
                
                logger.warning(f"Aggressive cleanup: trimmed {cleanup_count} messages/conversations")
                
            except Exception as e:
                logger.error(f"Error during aggressive memory cleanup: {e}")
    
    def _perform_emergency_memory_cleanup(self, memory_stats: MemoryStats):
        """Perform emergency memory cleanup by drastically reducing conversation data."""
        with self._lock:
            try:
                # First, perform aggressive cleanup
                self._perform_aggressive_memory_cleanup(memory_stats)
                
                # Emergency measures: keep only the most recent and active conversations
                if len(self.conversations) > 50:
                    # Sort conversations by last activity and message count
                    conversations_by_priority = [
                        (user_id, conv, conv["last_activity"], len(conv["messages"]))
                        for user_id, conv in self.conversations.items()
                    ]
                    
                    # Sort by activity (recent first), then by message count (more messages first)
                    conversations_by_priority.sort(key=lambda x: (x[2], x[3]), reverse=True)
                    
                    # Keep only top 50 conversations
                    conversations_to_keep = conversations_by_priority[:50]
                    conversations_to_remove = conversations_by_priority[50:]
                    
                    # Remove excess conversations
                    for user_id, conv, _, _ in conversations_to_remove:
                        if user_id in self.conversations:
                            del self.conversations[user_id]
                            if self._redis_available:
                                self._delete_from_redis(user_id)
                    
                    logger.critical(f"Emergency cleanup: removed {len(conversations_to_remove)} conversations, kept {len(conversations_to_keep)}")
                
                # Trim all remaining conversations to minimal messages
                for user_id, conv in self.conversations.items():
                    if len(conv["messages"]) > 5:
                        conv["messages"] = conv["messages"][-5:]  # Keep only last 5 messages
                        
                        # Update in Redis if available
                        if self._redis_available:
                            self._save_to_redis(user_id, conv)
                
                logger.critical("Emergency memory cleanup completed")
                
            except Exception as e:
                logger.critical(f"CRITICAL ERROR during emergency memory cleanup: {e}")
    
    def get_memory_usage_info(self) -> Dict[str, Any]:
        """Get detailed memory usage information for conversations."""
        with self._lock:
            try:
                # Calculate memory usage estimates
                total_conversations = len(self.conversations)
                total_messages = sum(len(conv["messages"]) for conv in self.conversations.values())
                
                # Estimate memory usage (rough calculation)
                avg_message_size = 200  # bytes (rough estimate)
                estimated_conversation_memory = total_messages * avg_message_size
                
                # Get active conversations (recent activity)
                recent_cutoff = datetime.now() - timedelta(hours=1)
                active_conversations = sum(
                    1 for conv in self.conversations.values()
                    if conv["last_activity"] > recent_cutoff
                )
                
                memory_info = {
                    'total_conversations': total_conversations,
                    'total_messages': total_messages,
                    'active_conversations': active_conversations,
                    'estimated_memory_bytes': estimated_conversation_memory,
                    'estimated_memory_mb': estimated_conversation_memory / (1024 * 1024),
                    'average_messages_per_conversation': total_messages / max(total_conversations, 1),
                    'memory_monitoring_enabled': self.enable_memory_monitoring,
                    'cleanup_stats': {
                        'max_messages_per_user': self.max_messages_per_user,
                        'max_total_conversations': self.max_total_conversations,
                        'conversation_ttl_hours': self.conversation_ttl_hours
                    }
                }
                
                # Add memory monitor stats if available
                if self.memory_monitor:
                    memory_info['memory_monitor_stats'] = self.memory_monitor.get_memory_usage_summary()
                
                return memory_info
                
            except Exception as e:
                logger.error(f"Error getting memory usage info: {e}")
                return {
                    'error': str(e),
                    'total_conversations': 0,
                    'total_messages': 0
                }

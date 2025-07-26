import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class ConversationService:
    """Manage conversation history per LINE user (in-memory for MVP demo)"""
    
    def __init__(self):
        # In-memory storage for conversations
        # Format: {user_id: {"messages": [...], "created_at": datetime, "last_activity": datetime, "last_response_id": str}}
        self.conversations: Dict[str, Dict] = {}
        
        # Thread safety: RLock allows the same thread to acquire the lock multiple times
        # This is important for methods that call other methods that also need the lock
        self._lock = threading.RLock()
        
        # Configuration
        self.max_messages_per_user = 100  # Limit memory usage
        self.max_total_conversations = 1000  # Global limit for demo
    
    def add_message(self, user_id: str, role: str, content: str, message_type: str = "text", metadata: dict = None):
        """Add a message to user's conversation history with optional metadata"""
        with self._lock:
            try:
                # Initialize conversation if it doesn't exist
                if user_id not in self.conversations:
                    self.conversations[user_id] = {
                        "messages": [],
                        "created_at": datetime.now(),
                        "last_activity": datetime.now(),
                        "last_response_id": None  # For Responses API conversation continuity
                    }
                    logger.info(f"Created new conversation for user {user_id}")
                
                # Add message with optional metadata
                message = {
                    "role": role,  # "user" or "assistant"
                    "content": content,
                    "message_type": message_type,  # "text", "image", "file", "mixed"
                    "metadata": metadata or {},
                    "timestamp": datetime.now()
                }
                
                self.conversations[user_id]["messages"].append(message)
                self.conversations[user_id]["last_activity"] = datetime.now()
                
                # Trim old messages if necessary
                if len(self.conversations[user_id]["messages"]) > self.max_messages_per_user:
                    # Keep the most recent messages
                    self.conversations[user_id]["messages"] = \
                        self.conversations[user_id]["messages"][-self.max_messages_per_user:]
                    logger.debug(f"Trimmed conversation history for user {user_id}")
                
                # Global conversation limit management
                self._manage_global_limits()
                
                logger.debug(f"Added {message_type} {role} message for user {user_id} (total: {len(self.conversations[user_id]['messages'])})")
                
            except Exception as e:
                logger.error(f"Error adding message for user {user_id}: {str(e)}")
                # Lock is automatically released by the context manager even on exception
    
    def get_last_response_id(self, user_id: str) -> Optional[str]:
        """Get the last response ID for Responses API conversation continuity"""
        with self._lock:
            if user_id not in self.conversations:
                return None
            
            return self.conversations[user_id].get("last_response_id")
    
    def set_last_response_id(self, user_id: str, response_id: str):
        """Set the last response ID for Responses API conversation continuity"""
        with self._lock:
            try:
                # Initialize conversation if it doesn't exist
                if user_id not in self.conversations:
                    self.conversations[user_id] = {
                        "messages": [],
                        "created_at": datetime.now(),
                        "last_activity": datetime.now(),
                        "last_response_id": None
                    }
                    logger.info(f"Created new conversation for user {user_id}")
                
                # Update the response ID and last activity
                self.conversations[user_id]["last_response_id"] = response_id
                self.conversations[user_id]["last_activity"] = datetime.now()
                
                logger.debug(f"Set last_response_id for user {user_id}: {response_id}")
                
            except Exception as e:
                logger.error(f"Error setting response ID for user {user_id}: {str(e)}")
                # Lock is automatically released by the context manager even on exception
    
    def get_conversation_history(self, user_id: str) -> List[Dict]:
        """Get conversation history for a user (legacy support - less needed with Responses API)"""
        with self._lock:
            if user_id not in self.conversations:
                return []
            
            # Return messages in format expected by OpenAI
            messages = []
            for msg in self.conversations[user_id]["messages"]:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            return messages
    
    def get_conversation_stats(self, user_id: str) -> Dict:
        """Get conversation statistics for a user"""
        with self._lock:
            if user_id not in self.conversations:
                return {
                    "exists": False,
                    "message_count": 0,
                    "created_at": None,
                    "last_activity": None,
                    "has_response_id": False,
                    "last_response_id": None
                }
            
            conv = self.conversations[user_id]
            return {
                "exists": True,
                "message_count": len(conv["messages"]),
                "created_at": conv["created_at"].isoformat(),
                "last_activity": conv["last_activity"].isoformat(),
                "has_response_id": bool(conv.get("last_response_id")),
                "last_response_id": conv.get("last_response_id")
            }
    
    def clear_conversation(self, user_id: str) -> bool:
        """Clear conversation history for a user"""
        with self._lock:
            if user_id in self.conversations:
                del self.conversations[user_id]
                logger.info(f"Cleared conversation for user {user_id}")
                return True
            return False
    
    def get_all_conversations_stats(self) -> Dict:
        """Get statistics for all conversations"""
        with self._lock:
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
        """Manage global conversation limits for demo purposes"""
        # Note: This method is called from add_message which already holds the lock
        # Using RLock allows re-entrant locking from the same thread
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
                del self.conversations[user_id_to_remove]
                logger.info(f"Removed old conversation for user {user_id_to_remove} (global limit management)")
    
    def cleanup_old_conversations(self, max_age_hours: int = 24):
        """Clean up conversations older than specified hours (for demo maintenance)"""
        with self._lock:
            current_time = datetime.now()
            users_to_remove = []
            
            # First pass: identify conversations to remove
            for user_id, conv in self.conversations.items():
                age_hours = (current_time - conv["last_activity"]).total_seconds() / 3600
                if age_hours > max_age_hours:
                    users_to_remove.append((user_id, age_hours))
            
            # Second pass: remove identified conversations atomically
            for user_id, age_hours in users_to_remove:
                del self.conversations[user_id]
                logger.info(f"Cleaned up old conversation for user {user_id} (age: {age_hours:.1f} hours)")
            
            return len(users_to_remove)

"""
Async webhook dispatcher with Celery integration.

This module provides a dispatcher that can route webhook processing
either synchronously (for immediate response) or asynchronously via Celery
for improved performance and scalability.
"""

import logging
import asyncio
import time
from typing import Dict, Any, Optional, Callable, Union
from datetime import datetime
from enum import Enum

from src.exceptions import (
    DataProcessingException, NetworkException, create_correlation_id
)
from src.utils.error_handler import StructuredLogger, error_handler

logger = StructuredLogger(__name__)


class ProcessingMode(Enum):
    """Processing modes for webhook handling."""
    SYNCHRONOUS = "sync"
    ASYNCHRONOUS = "async"
    HYBRID = "hybrid"  # Async for heavy tasks, sync for light tasks


class WebhookType(Enum):
    """Types of webhook events."""
    TEXT_MESSAGE = "text_message"
    IMAGE_MESSAGE = "image_message"
    POSTBACK = "postback"
    FOLLOW = "follow"
    UNFOLLOW = "unfollow"
    JOIN = "join"
    LEAVE = "leave"
    BEACON = "beacon"
    UNKNOWN = "unknown"


class AsyncWebhookDispatcher:
    """
    Dispatcher for routing webhook processing between sync and async modes.
    
    This dispatcher can intelligently route webhook events based on:
    - Event type and complexity
    - Current system load
    - User preferences
    - Processing time estimates
    """
    
    def __init__(self, 
                 default_mode: ProcessingMode = ProcessingMode.HYBRID,
                 enable_celery: bool = True,
                 sync_timeout: float = 5.0,
                 heavy_task_threshold: float = 3.0):
        """
        Initialize the webhook dispatcher.
        
        Args:
            default_mode: Default processing mode
            enable_celery: Whether Celery background processing is available
            sync_timeout: Timeout for synchronous processing
            heavy_task_threshold: Time threshold for considering a task "heavy"
        """
        self.default_mode = default_mode
        self.enable_celery = enable_celery
        self.sync_timeout = sync_timeout
        self.heavy_task_threshold = heavy_task_threshold
        
        # Performance tracking
        self.processing_stats = {
            'total_requests': 0,
            'sync_requests': 0,
            'async_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'avg_sync_time': 0.0,
            'avg_async_submit_time': 0.0
        }
        
        # Load balancing state
        self.current_load = 0
        self.max_concurrent_sync = 10
        self.current_sync_tasks = 0
        
        logger.info(f"Initialized AsyncWebhookDispatcher with mode={default_mode.value}, celery={enable_celery}")
    
    async def dispatch_webhook(self, 
                             webhook_type: WebhookType,
                             event_data: Dict[str, Any],
                             processing_mode: Optional[ProcessingMode] = None,
                             correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Dispatch a webhook event for processing.
        
        Args:
            webhook_type: Type of webhook event
            event_data: Event data from LINE webhook
            processing_mode: Override processing mode
            correlation_id: Request correlation ID
        
        Returns:
            Dict with dispatch results
        """
        start_time = time.time()
        
        if not correlation_id:
            correlation_id = create_correlation_id()
        
        with logger.context(correlation_id=correlation_id, webhook_type=webhook_type.value):
            logger.info("Dispatching webhook event")
            
            try:
                # Update stats
                self.processing_stats['total_requests'] += 1
                
                # Determine processing mode
                mode = processing_mode or self._determine_processing_mode(webhook_type, event_data)
                
                # Route to appropriate processor
                if mode == ProcessingMode.SYNCHRONOUS:
                    result = await self._process_synchronously(webhook_type, event_data, correlation_id)
                    self.processing_stats['sync_requests'] += 1
                    
                elif mode == ProcessingMode.ASYNCHRONOUS:
                    result = await self._process_asynchronously(webhook_type, event_data, correlation_id)
                    self.processing_stats['async_requests'] += 1
                    
                else:  # HYBRID
                    # Use intelligent routing based on current conditions
                    if self._should_process_async(webhook_type, event_data):
                        result = await self._process_asynchronously(webhook_type, event_data, correlation_id)
                        self.processing_stats['async_requests'] += 1
                    else:
                        result = await self._process_synchronously(webhook_type, event_data, correlation_id)
                        self.processing_stats['sync_requests'] += 1
                
                # Update success stats
                if result.get('success', False):
                    self.processing_stats['successful_requests'] += 1
                else:
                    self.processing_stats['failed_requests'] += 1
                
                # Update timing stats
                dispatch_time = time.time() - start_time
                if result.get('processing_mode') == 'sync':
                    self._update_sync_time_stats(dispatch_time)
                elif result.get('processing_mode') == 'async':
                    self._update_async_time_stats(dispatch_time)
                
                logger.info(
                    f"Webhook dispatched successfully",
                    extra_context={
                        'mode': result.get('processing_mode', 'unknown'),
                        'dispatch_time': dispatch_time
                    }
                )
                
                return result
                
            except Exception as e:
                self.processing_stats['failed_requests'] += 1
                logger.error(f"Webhook dispatch failed: {e}")
                
                return {
                    'success': False,
                    'error': str(e),
                    'processing_mode': 'failed',
                    'correlation_id': correlation_id,
                    'dispatch_time': time.time() - start_time
                }
    
    def _determine_processing_mode(self, 
                                 webhook_type: WebhookType, 
                                 event_data: Dict[str, Any]) -> ProcessingMode:
        """
        Determine the appropriate processing mode for a webhook event.
        
        Args:
            webhook_type: Type of webhook event
            event_data: Event data
        
        Returns:
            Recommended processing mode
        """
        # If Celery is not available, always use sync
        if not self.enable_celery:
            return ProcessingMode.SYNCHRONOUS
        
        # Use default mode if not hybrid
        if self.default_mode != ProcessingMode.HYBRID:
            return self.default_mode
        
        # Hybrid mode logic
        # Heavy tasks that should typically be async
        heavy_tasks = {
            WebhookType.IMAGE_MESSAGE,  # Image processing is CPU/IO intensive
        }
        
        # Light tasks that can be sync
        light_tasks = {
            WebhookType.POSTBACK,      # Simple postback handling
            WebhookType.FOLLOW,        # Welcome messages
            WebhookType.UNFOLLOW,      # Cleanup tasks
        }
        
        if webhook_type in heavy_tasks:
            return ProcessingMode.ASYNCHRONOUS
        elif webhook_type in light_tasks:
            return ProcessingMode.SYNCHRONOUS
        else:
            # For text messages, consider length and complexity
            if webhook_type == WebhookType.TEXT_MESSAGE:
                message_text = event_data.get('message', {}).get('text', '')
                
                # Long messages or complex queries -> async
                if len(message_text) > 200 or any(keyword in message_text.lower() 
                                                 for keyword in ['analyze', 'explain', 'detailed', 'summarize']):
                    return ProcessingMode.ASYNCHRONOUS
                else:
                    return ProcessingMode.SYNCHRONOUS
        
        # Default to sync for unknown cases
        return ProcessingMode.SYNCHRONOUS
    
    def _should_process_async(self, webhook_type: WebhookType, event_data: Dict[str, Any]) -> bool:
        """
        Determine if a task should be processed asynchronously based on current conditions.
        
        Args:
            webhook_type: Type of webhook event
            event_data: Event data
        
        Returns:
            True if should process async, False for sync
        """
        # Check current load
        if self.current_sync_tasks >= self.max_concurrent_sync:
            logger.debug("High sync load, routing to async")
            return True
        
        # Get base recommendation
        recommended_mode = self._determine_processing_mode(webhook_type, event_data)
        return recommended_mode == ProcessingMode.ASYNCHRONOUS
    
    async def _process_synchronously(self, 
                                   webhook_type: WebhookType,
                                   event_data: Dict[str, Any],
                                   correlation_id: str) -> Dict[str, Any]:
        """
        Process webhook event synchronously.
        
        Args:
            webhook_type: Type of webhook event
            event_data: Event data
            correlation_id: Request correlation ID
        
        Returns:
            Dict with processing results
        """
        self.current_sync_tasks += 1
        
        try:
            logger.debug("Processing webhook synchronously")
            
            # Import services here to avoid circular imports
            from src.services.line_service import LineService
            from src.services.openai_service import OpenAIService
            from src.services.conversation_factory import create_conversation_service
            from src.config.settings import Settings
            
            # Initialize services
            settings = Settings()
            conversation_service = create_conversation_service(settings)
            openai_service = OpenAIService(settings, conversation_service)
            line_service = LineService(settings, openai_service, conversation_service)
            
            # Create a timeout for sync processing
            async def process_with_timeout():
                if webhook_type == WebhookType.TEXT_MESSAGE:
                    return await self._handle_text_message_sync(
                        line_service, event_data, correlation_id
                    )
                elif webhook_type == WebhookType.IMAGE_MESSAGE:
                    return await self._handle_image_message_sync(
                        line_service, event_data, correlation_id
                    )
                elif webhook_type == WebhookType.POSTBACK:
                    return await self._handle_postback_sync(
                        line_service, event_data, correlation_id
                    )
                else:
                    return await self._handle_other_event_sync(
                        line_service, webhook_type, event_data, correlation_id
                    )
            
            # Process with timeout
            try:
                result = await asyncio.wait_for(process_with_timeout(), timeout=self.sync_timeout)
                result['processing_mode'] = 'sync'
                return result
                
            except asyncio.TimeoutError:
                logger.warning(f"Sync processing timeout for {webhook_type.value}, falling back to async")
                # Fall back to async processing
                return await self._process_asynchronously(webhook_type, event_data, correlation_id)
                
        finally:
            self.current_sync_tasks -= 1
    
    async def _process_asynchronously(self, 
                                    webhook_type: WebhookType,
                                    event_data: Dict[str, Any],
                                    correlation_id: str) -> Dict[str, Any]:
        """
        Process webhook event asynchronously using Celery.
        
        Args:
            webhook_type: Type of webhook event
            event_data: Event data
            correlation_id: Request correlation ID
        
        Returns:
            Dict with async processing results
        """
        logger.debug("Processing webhook asynchronously")
        
        try:
            # Import Celery tasks
            from src.tasks.webhook_processing import (
                process_text_message_async,
                process_image_message_async,
                process_postback_async
            )
            
            # Extract common fields
            user_id = event_data.get('source', {}).get('userId', 'unknown')
            reply_token = event_data.get('replyToken')
            
            # Route to appropriate async task
            if webhook_type == WebhookType.TEXT_MESSAGE:
                message_text = event_data.get('message', {}).get('text', '')
                task = process_text_message_async.delay(
                    user_id=user_id,
                    message_text=message_text,
                    reply_token=reply_token,
                    correlation_id=correlation_id,
                    webhook_context=event_data
                )
                
            elif webhook_type == WebhookType.IMAGE_MESSAGE:
                message_id = event_data.get('message', {}).get('id', '')
                task = process_image_message_async.delay(
                    user_id=user_id,
                    message_id=message_id,
                    reply_token=reply_token,
                    correlation_id=correlation_id,
                    webhook_context=event_data
                )
                
            elif webhook_type == WebhookType.POSTBACK:
                postback_data = event_data.get('postback', {}).get('data', '')
                task = process_postback_async.delay(
                    user_id=user_id,
                    postback_data=postback_data,
                    reply_token=reply_token,
                    correlation_id=correlation_id,
                    webhook_context=event_data
                )
                
            else:
                # For other event types, create a generic async task
                # This would need to be implemented based on specific needs
                logger.warning(f"No async handler for webhook type: {webhook_type.value}")
                return {
                    'success': False,
                    'error': f'No async handler for webhook type: {webhook_type.value}',
                    'processing_mode': 'async_failed',
                    'correlation_id': correlation_id
                }
            
            return {
                'success': True,
                'processing_mode': 'async',
                'task_id': task.id,
                'correlation_id': correlation_id,
                'message': 'Webhook processing submitted to background queue'
            }
            
        except Exception as e:
            logger.error(f"Failed to submit async task: {e}")
            
            return {
                'success': False,
                'error': f'Failed to submit async task: {str(e)}',
                'processing_mode': 'async_failed',
                'correlation_id': correlation_id
            }
    
    async def _handle_text_message_sync(self, 
                                      line_service: Any,
                                      event_data: Dict[str, Any],
                                      correlation_id: str) -> Dict[str, Any]:
        """Handle text message synchronously."""
        user_id = event_data.get('source', {}).get('userId', 'unknown')
        message_text = event_data.get('message', {}).get('text', '')
        reply_token = event_data.get('replyToken')
        
        # Get AI response
        ai_response = line_service.openai_service.get_response(
            user_id=user_id,
            user_message=message_text,
            use_streaming=False
        )
        
        if ai_response.get('success'):
            # Send reply
            response_message = ai_response.get('message', 'Sorry, I encountered an error.')
            line_service.line_bot_api.reply_message(
                reply_token,
                line_service._create_text_message(response_message)
            )
            
            return {
                'success': True,
                'user_id': user_id,
                'response_sent': True,
                'correlation_id': correlation_id
            }
        else:
            return {
                'success': False,
                'error': ai_response.get('error', 'AI processing failed'),
                'correlation_id': correlation_id
            }
    
    async def _handle_image_message_sync(self,
                                       line_service: Any,
                                       event_data: Dict[str, Any],
                                       correlation_id: str) -> Dict[str, Any]:
        """Handle image message synchronously."""
        # This is typically too heavy for sync processing
        # But can be implemented for small/simple images
        return {
            'success': False,
            'error': 'Image processing too heavy for sync mode',
            'correlation_id': correlation_id
        }
    
    async def _handle_postback_sync(self,
                                  line_service: Any,
                                  event_data: Dict[str, Any],
                                  correlation_id: str) -> Dict[str, Any]:
        """Handle postback event synchronously."""
        user_id = event_data.get('source', {}).get('userId', 'unknown')
        reply_token = event_data.get('replyToken')
        postback_data = event_data.get('postback', {}).get('data', '')
        
        # Simple postback response
        response_message = f"Thanks for the interaction! Data: {postback_data}"
        line_service.line_bot_api.reply_message(
            reply_token,
            line_service._create_text_message(response_message)
        )
        
        return {
            'success': True,
            'user_id': user_id,
            'postback_data': postback_data,
            'response_sent': True,
            'correlation_id': correlation_id
        }
    
    async def _handle_other_event_sync(self,
                                     line_service: Any,
                                     webhook_type: WebhookType,
                                     event_data: Dict[str, Any],
                                     correlation_id: str) -> Dict[str, Any]:
        """Handle other event types synchronously."""
        user_id = event_data.get('source', {}).get('userId', 'unknown')
        
        # Log the event but don't send a response for most event types
        logger.info(f"Handled {webhook_type.value} event for user {user_id}")
        
        return {
            'success': True,
            'event_type': webhook_type.value,
            'user_id': user_id,
            'action': 'logged',
            'correlation_id': correlation_id
        }
    
    def _update_sync_time_stats(self, processing_time: float):
        """Update synchronous processing time statistics."""
        current_avg = self.processing_stats['avg_sync_time']
        sync_count = self.processing_stats['sync_requests']
        
        if sync_count > 0:
            self.processing_stats['avg_sync_time'] = (
                (current_avg * (sync_count - 1) + processing_time) / sync_count
            )
    
    def _update_async_time_stats(self, submit_time: float):
        """Update asynchronous submit time statistics."""
        current_avg = self.processing_stats['avg_async_submit_time']
        async_count = self.processing_stats['async_requests']
        
        if async_count > 0:
            self.processing_stats['avg_async_submit_time'] = (
                (current_avg * (async_count - 1) + submit_time) / async_count
            )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get dispatcher performance statistics."""
        return {
            'processing_stats': self.processing_stats.copy(),
            'current_state': {
                'current_sync_tasks': self.current_sync_tasks,
                'max_concurrent_sync': self.max_concurrent_sync,
                'current_load': self.current_load
            },
            'configuration': {
                'default_mode': self.default_mode.value,
                'enable_celery': self.enable_celery,
                'sync_timeout': self.sync_timeout,
                'heavy_task_threshold': self.heavy_task_threshold
            },
            'timestamp': datetime.utcnow().isoformat()
        }


# Global dispatcher instance
_dispatcher_instance: Optional[AsyncWebhookDispatcher] = None


def get_webhook_dispatcher(
    default_mode: ProcessingMode = ProcessingMode.HYBRID,
    enable_celery: bool = True
) -> AsyncWebhookDispatcher:
    """Get or create the global webhook dispatcher."""
    global _dispatcher_instance
    
    if _dispatcher_instance is None:
        _dispatcher_instance = AsyncWebhookDispatcher(
            default_mode=default_mode,
            enable_celery=enable_celery
        )
    
    return _dispatcher_instance


def classify_webhook_event(event_data: Dict[str, Any]) -> WebhookType:
    """
    Classify a webhook event based on its data structure.
    
    Args:
        event_data: Webhook event data
    
    Returns:
        Classified webhook type
    """
    event_type = event_data.get('type', '')
    
    if event_type == 'message':
        message_type = event_data.get('message', {}).get('type', '')
        if message_type == 'text':
            return WebhookType.TEXT_MESSAGE
        elif message_type == 'image':
            return WebhookType.IMAGE_MESSAGE
    elif event_type == 'postback':
        return WebhookType.POSTBACK
    elif event_type == 'follow':
        return WebhookType.FOLLOW
    elif event_type == 'unfollow':
        return WebhookType.UNFOLLOW
    elif event_type == 'join':
        return WebhookType.JOIN
    elif event_type == 'leave':
        return WebhookType.LEAVE
    elif event_type == 'beacon':
        return WebhookType.BEACON
    
    return WebhookType.UNKNOWN
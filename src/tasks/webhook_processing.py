"""
Background webhook processing with Celery integration.

This module provides async webhook processing capabilities using Celery
for improved performance and reliability of LINE Bot webhook handling.
"""

import logging
import time
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from celery import Task
from celery.exceptions import Retry, WorkerLostError

from src.utils.celery_app import celery_app
from src.exceptions import (
    LineAPIException, OpenAIAPIException, NetworkException,
    DataProcessingException, create_correlation_id, BaseBotException
)
from src.utils.error_handler import StructuredLogger, error_handler
from src.utils.connection_pool import connection_pool_manager

logger = StructuredLogger(__name__)


class WebhookProcessingTask(Task):
    """Custom Celery task class for webhook processing with enhanced error handling."""
    
    autoretry_for = (NetworkException, OpenAIAPIException)
    retry_kwargs = {'max_retries': 3, 'countdown': 2}
    retry_backoff = True
    retry_backoff_max = 60
    retry_jitter = True
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails."""
        correlation_id = kwargs.get('correlation_id', 'unknown')
        
        with logger.context(correlation_id=correlation_id, task_id=task_id):
            logger.error(
                f"Webhook processing task failed: {exc}",
                extra_context={
                    'args': args,
                    'kwargs': kwargs,
                    'exception_info': str(einfo)
                }
            )
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called when task is retried."""
        correlation_id = kwargs.get('correlation_id', 'unknown')
        
        with logger.context(correlation_id=correlation_id, task_id=task_id):
            logger.warning(
                f"Webhook processing task retrying: {exc}",
                extra_context={
                    'retry_count': self.request.retries,
                    'max_retries': self.max_retries
                }
            )
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds."""
        correlation_id = kwargs.get('correlation_id', 'unknown')
        processing_time = retval.get('processing_time', 0) if isinstance(retval, dict) else 0
        
        with logger.context(correlation_id=correlation_id, task_id=task_id):
            logger.info(
                f"Webhook processing task completed successfully",
                extra_context={
                    'processing_time': processing_time,
                    'result_size': len(str(retval)) if retval else 0
                }
            )


@celery_app.task(base=WebhookProcessingTask, bind=True, name='webhook.process_text_message')
def process_text_message_async(self, user_id: str, message_text: str, 
                              reply_token: str, correlation_id: str = None,
                              webhook_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Process text message asynchronously in background.
    
    Args:
        user_id: LINE user ID
        message_text: User's text message
        reply_token: LINE reply token
        correlation_id: Request correlation ID
        webhook_context: Additional webhook context
    
    Returns:
        Dict with processing results
    """
    start_time = time.time()
    
    if not correlation_id:
        correlation_id = create_correlation_id()
    
    with logger.context(
        correlation_id=correlation_id,
        task_id=self.request.id,
        user_id=user_id[:8] + '...' if user_id else None
    ):
        logger.info("Processing text message in background")
        
        try:
            # Import services here to avoid circular imports
            from src.services.line_service import LineService
            from src.services.openai_service import OpenAIService
            from src.services.conversation_factory import create_conversation_service
            from src.config.settings import Settings
            
            # Initialize services (these should be cached/singleton in production)
            settings = Settings()
            conversation_service = create_conversation_service(settings)
            openai_service = OpenAIService(settings, conversation_service)
            line_service = LineService(settings, openai_service, conversation_service)
            
            # Get AI response
            logger.debug("Getting AI response for text message")
            ai_response = openai_service.get_response(
                user_id=user_id,
                user_message=message_text,
                use_streaming=False  # Disable streaming for background processing
            )
            
            if not ai_response.get('success'):
                raise DataProcessingException(
                    message=f"AI processing failed: {ai_response.get('error', 'Unknown error')}",
                    operation="get_ai_response",
                    correlation_id=correlation_id
                )
            
            # Send response via LINE API
            logger.debug("Sending response via LINE API")
            response_message = ai_response.get('message', 'Sorry, I encountered an error processing your message.')
            
            # Use connection pooling for LINE API call
            def send_reply():
                return line_service.line_bot_api.reply_message(
                    reply_token,
                    line_service._create_text_message(response_message)
                )
            
            delivery_result = connection_pool_manager.execute_with_retry(
                'line_bot_api',
                send_reply,
                max_attempts=2
            )
            
            processing_time = time.time() - start_time
            
            result = {
                'success': True,
                'user_id': user_id,
                'message_length': len(message_text),
                'response_length': len(response_message),
                'processing_time': processing_time,
                'ai_response': ai_response,
                'delivery_successful': True,
                'correlation_id': correlation_id,
                'task_id': self.request.id
            }
            
            logger.info(
                f"Text message processed successfully",
                extra_context={
                    'processing_time': processing_time,
                    'response_length': len(response_message)
                }
            )
            
            return result
            
        except BaseBotException as e:
            # Handle known bot exceptions
            logger.error(f"Bot exception in background processing: {e}")
            raise self.retry(countdown=2, max_retries=2)
            
        except Exception as e:
            # Handle unexpected exceptions
            logger.error(f"Unexpected error in background processing: {e}")
            
            # Attempt to send error message to user
            try:
                from src.services.line_service import LineService
                from src.config.settings import Settings
                
                settings = Settings()
                line_service = LineService(settings, None, None)
                
                error_message = "I'm sorry, I'm experiencing technical difficulties. Please try again later."
                line_service.line_bot_api.reply_message(
                    reply_token,
                    line_service._create_text_message(error_message)
                )
                
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")
            
            # Re-raise for Celery retry mechanism
            raise


@celery_app.task(base=WebhookProcessingTask, bind=True, name='webhook.process_image_message')
def process_image_message_async(self, user_id: str, message_id: str, 
                               reply_token: str, correlation_id: str = None,
                               webhook_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Process image message asynchronously in background.
    
    Args:
        user_id: LINE user ID
        message_id: LINE message ID for image
        reply_token: LINE reply token
        correlation_id: Request correlation ID
        webhook_context: Additional webhook context
    
    Returns:
        Dict with processing results
    """
    start_time = time.time()
    
    if not correlation_id:
        correlation_id = create_correlation_id()
    
    with logger.context(
        correlation_id=correlation_id,
        task_id=self.request.id,
        user_id=user_id[:8] + '...' if user_id else None
    ):
        logger.info("Processing image message in background")
        
        try:
            # Import services here to avoid circular imports
            from src.services.line_service import LineService
            from src.services.openai_service import OpenAIService
            from src.services.conversation_factory import create_conversation_service
            from src.config.settings import Settings
            from src.utils.image_utils import ImageProcessor
            
            # Initialize services
            settings = Settings()
            conversation_service = create_conversation_service(settings)
            openai_service = OpenAIService(settings, conversation_service)
            line_service = LineService(settings, openai_service, conversation_service)
            
            # Download and process image
            logger.debug("Downloading and processing image")
            with ImageProcessor() as image_processor:
                image_result = image_processor.download_image_from_line(
                    line_service.line_bot_api,
                    message_id,
                    timeout_seconds=30  # Longer timeout for background processing
                )
                
                if not image_result.get('success'):
                    raise DataProcessingException(
                        message=f"Image processing failed: {image_result.get('error', 'Unknown error')}",
                        operation="download_image",
                        correlation_id=correlation_id
                    )
                
                # Get AI response for image
                logger.debug("Getting AI response for image")
                ai_response = openai_service.get_response(
                    user_id=user_id,
                    user_message="What do you see in this image?",
                    image_data=image_result.get('image_data'),
                    use_streaming=False  # Disable streaming for background processing
                )
                
                if not ai_response.get('success'):
                    raise DataProcessingException(
                        message=f"AI processing failed: {ai_response.get('error', 'Unknown error')}",
                        operation="get_ai_response",
                        correlation_id=correlation_id
                    )
                
                # Send response via LINE API
                logger.debug("Sending response via LINE API")
                response_message = ai_response.get('message', 'I can see your image, but I encountered an error analyzing it.')
                
                # Use connection pooling for LINE API call
                def send_reply():
                    return line_service.line_bot_api.reply_message(
                        reply_token,
                        line_service._create_text_message(response_message)
                    )
                
                delivery_result = connection_pool_manager.execute_with_retry(
                    'line_bot_api',
                    send_reply,
                    max_attempts=2
                )
                
                processing_time = time.time() - start_time
                
                result = {
                    'success': True,
                    'user_id': user_id,
                    'message_id': message_id,
                    'image_size': image_result.get('size', 0),
                    'image_format': image_result.get('format', 'unknown'),
                    'response_length': len(response_message),
                    'processing_time': processing_time,
                    'ai_response': ai_response,
                    'delivery_successful': True,
                    'correlation_id': correlation_id,
                    'task_id': self.request.id
                }
                
                logger.info(
                    f"Image message processed successfully",
                    extra_context={
                        'processing_time': processing_time,
                        'image_size': image_result.get('size', 0),
                        'response_length': len(response_message)
                    }
                )
                
                return result
                
        except BaseBotException as e:
            # Handle known bot exceptions
            logger.error(f"Bot exception in background image processing: {e}")
            raise self.retry(countdown=3, max_retries=2)  # Longer countdown for image processing
            
        except Exception as e:
            # Handle unexpected exceptions
            logger.error(f"Unexpected error in background image processing: {e}")
            
            # Attempt to send error message to user
            try:
                from src.services.line_service import LineService
                from src.config.settings import Settings
                
                settings = Settings()
                line_service = LineService(settings, None, None)
                
                error_message = "I'm sorry, I had trouble processing your image. Please try again later."
                line_service.line_bot_api.reply_message(
                    reply_token,
                    line_service._create_text_message(error_message)
                )
                
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")
            
            # Re-raise for Celery retry mechanism
            raise


@celery_app.task(base=WebhookProcessingTask, bind=True, name='webhook.process_postback')
def process_postback_async(self, user_id: str, postback_data: str,
                          reply_token: str, correlation_id: str = None,
                          webhook_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Process postback event asynchronously in background.
    
    Args:
        user_id: LINE user ID
        postback_data: Postback data from user interaction
        reply_token: LINE reply token
        correlation_id: Request correlation ID
        webhook_context: Additional webhook context
    
    Returns:
        Dict with processing results
    """
    start_time = time.time()
    
    if not correlation_id:
        correlation_id = create_correlation_id()
    
    with logger.context(
        correlation_id=correlation_id,
        task_id=self.request.id,
        user_id=user_id[:8] + '...' if user_id else None
    ):
        logger.info("Processing postback event in background")
        
        try:
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
            
            # Parse postback data
            try:
                postback_params = json.loads(postback_data)
            except json.JSONDecodeError:
                postback_params = {'action': 'unknown', 'data': postback_data}
            
            action = postback_params.get('action', 'unknown')
            
            logger.debug(f"Processing postback action: {action}")
            
            # Handle different postback actions
            if action == 'view_content':
                response_message = "Thank you for your interest! Here's more content for you."
            elif action == 'share_action':
                response_message = "Thanks for sharing! Your friends will love this content."
            elif action == 'save_action':
                response_message = "Content saved! You can find it in your saved items."
            elif action == 'like_action':
                response_message = "Thanks for the like! 👍 Glad you enjoyed the content."
            else:
                response_message = f"Thanks for the interaction! Action: {action}"
            
            # Send response via LINE API
            logger.debug("Sending postback response via LINE API")
            
            # Use connection pooling for LINE API call
            def send_reply():
                return line_service.line_bot_api.reply_message(
                    reply_token,
                    line_service._create_text_message(response_message)
                )
            
            delivery_result = connection_pool_manager.execute_with_retry(
                'line_bot_api',
                send_reply,
                max_attempts=2
            )
            
            processing_time = time.time() - start_time
            
            result = {
                'success': True,
                'user_id': user_id,
                'action': action,
                'postback_data': postback_data,
                'response_message': response_message,
                'processing_time': processing_time,
                'delivery_successful': True,
                'correlation_id': correlation_id,
                'task_id': self.request.id
            }
            
            logger.info(
                f"Postback event processed successfully",
                extra_context={
                    'processing_time': processing_time,
                    'action': action
                }
            )
            
            return result
            
        except Exception as e:
            # Handle unexpected exceptions
            logger.error(f"Unexpected error in background postback processing: {e}")
            
            # Attempt to send error message to user
            try:
                from src.services.line_service import LineService
                from src.config.settings import Settings
                
                settings = Settings()
                line_service = LineService(settings, None, None)
                
                error_message = "Thanks for the interaction! I'm processing your request."
                line_service.line_bot_api.reply_message(
                    reply_token,
                    line_service._create_text_message(error_message)
                )
                
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")
            
            # Re-raise for Celery retry mechanism
            raise


@celery_app.task(name='webhook.batch_process_rich_messages')
def batch_process_rich_messages(user_ids: List[str], message_template: str,
                               template_category: str = 'general',
                               correlation_id: str = None) -> Dict[str, Any]:
    """
    Process Rich Message delivery to multiple users in batch.
    
    Args:
        user_ids: List of LINE user IDs
        message_template: Rich Message template
        template_category: Template category
        correlation_id: Request correlation ID
    
    Returns:
        Dict with batch processing results
    """
    start_time = time.time()
    
    if not correlation_id:
        correlation_id = create_correlation_id()
    
    with logger.context(correlation_id=correlation_id):
        logger.info(f"Processing batch Rich Message delivery for {len(user_ids)} users")
        
        try:
            # Import async pipeline
            from src.utils.async_rich_message_pipeline import get_async_pipeline
            
            # Get the async pipeline (should be initialized by the main app)
            pipeline = get_async_pipeline()
            
            if not pipeline or not pipeline.is_running:
                # Fallback to synchronous processing if async pipeline not available
                logger.warning("Async pipeline not available, falling back to synchronous processing")
                
                # Import services for fallback
                from src.services.rich_message_service import RichMessageService
                from src.services.line_service import LineService
                from src.config.settings import Settings
                
                settings = Settings()
                line_service = LineService(settings, None, None)
                rich_message_service = RichMessageService(line_service.line_bot_api)
                
                # Process synchronously
                delivered_count = 0
                failed_count = 0
                results = []
                
                for user_id in user_ids:
                    try:
                        # Generate and send Rich Message (simplified for demo)
                        # In real implementation, this would use the full Rich Message generation
                        message = f"Rich Message: {message_template}"
                        line_service.line_bot_api.push_message(
                            user_id,
                            line_service._create_text_message(message)
                        )
                        delivered_count += 1
                        results.append({'user_id': user_id, 'status': 'delivered'})
                        
                    except Exception as e:
                        failed_count += 1
                        results.append({'user_id': user_id, 'status': 'failed', 'error': str(e)})
                        logger.error(f"Failed to deliver to user {user_id}: {e}")
                
                processing_time = time.time() - start_time
                
                return {
                    'success': True,
                    'method': 'synchronous_fallback',
                    'delivered_count': delivered_count,
                    'failed_count': failed_count,
                    'total_users': len(user_ids),
                    'processing_time': processing_time,
                    'results': results,
                    'correlation_id': correlation_id
                }
            
            else:
                # Use async pipeline for processing
                import asyncio
                
                async def submit_batch_task():
                    task_id = await pipeline.submit_batch_delivery_task(
                        user_ids=user_ids,
                        content_template=message_template,
                        template_category=template_category
                    )
                    return task_id
                
                # Submit to async pipeline
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    task_id = loop.run_until_complete(submit_batch_task())
                finally:
                    loop.close()
                
                processing_time = time.time() - start_time
                
                return {
                    'success': True,
                    'method': 'async_pipeline',
                    'async_task_id': task_id,
                    'total_users': len(user_ids),
                    'processing_time': processing_time,
                    'correlation_id': correlation_id,
                    'message': 'Batch processing submitted to async pipeline'
                }
                
        except Exception as e:
            logger.error(f"Batch Rich Message processing failed: {e}")
            
            processing_time = time.time() - start_time
            
            return {
                'success': False,
                'error': str(e),
                'total_users': len(user_ids),
                'processing_time': processing_time,
                'correlation_id': correlation_id
            }


@celery_app.task(name='webhook.health_check')
def webhook_processing_health_check() -> Dict[str, Any]:
    """
    Health check for webhook processing system.
    
    Returns:
        Dict with health status
    """
    try:
        # Check connection pool health
        pool_metrics = connection_pool_manager.get_metrics()
        pool_healthy = len([h for h in pool_metrics.get('health', {}).values() 
                          if h.get('state') == 'healthy']) > 0
        
        # Check async pipeline health (if available)
        pipeline_healthy = False
        try:
            from src.utils.async_rich_message_pipeline import get_async_pipeline
            pipeline = get_async_pipeline()
            pipeline_healthy = pipeline and pipeline.is_running
        except Exception:
            pipeline_healthy = False
        
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'components': {
                'celery_worker': True,  # If this task runs, Celery is working
                'connection_pools': pool_healthy,
                'async_pipeline': pipeline_healthy
            },
            'pool_metrics': {
                'total_pools': pool_metrics.get('total_pools', 0),
                'healthy_connections': len([h for h in pool_metrics.get('health', {}).values() 
                                          if h.get('state') == 'healthy'])
            }
        }
        
    except Exception as e:
        return {
            'status': 'unhealthy',
            'timestamp': datetime.utcnow().isoformat(),
            'error': str(e)
        }


# Task monitoring and metrics
@celery_app.task(name='webhook.collect_metrics')
def collect_webhook_metrics() -> Dict[str, Any]:
    """
    Collect metrics for webhook processing performance.
    
    Returns:
        Dict with collected metrics
    """
    try:
        # Get Celery task metrics
        inspect = celery_app.control.inspect()
        
        # Get active tasks
        active_tasks = inspect.active()
        active_count = sum(len(tasks) for tasks in active_tasks.values()) if active_tasks else 0
        
        # Get scheduled tasks
        scheduled_tasks = inspect.scheduled()
        scheduled_count = sum(len(tasks) for tasks in scheduled_tasks.values()) if scheduled_tasks else 0
        
        # Get reserved tasks
        reserved_tasks = inspect.reserved()
        reserved_count = sum(len(tasks) for tasks in reserved_tasks.values()) if reserved_tasks else 0
        
        # Get connection pool metrics
        pool_metrics = connection_pool_manager.get_metrics()
        
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'celery_metrics': {
                'active_tasks': active_count,
                'scheduled_tasks': scheduled_count,
                'reserved_tasks': reserved_count,
                'total_queued': scheduled_count + reserved_count
            },
            'connection_pool_metrics': pool_metrics,
            'status': 'healthy'
        }
        
    except Exception as e:
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'error',
            'error': str(e)
        }
"""
Unit tests for webhook processing with Celery integration.
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from src.tasks.webhook_processing import (
    process_text_message_async,
    process_image_message_async,
    process_postback_async,
    batch_process_rich_messages,
    webhook_processing_health_check,
    collect_webhook_metrics
)
from src.utils.async_webhook_dispatcher import (
    AsyncWebhookDispatcher, WebhookType, ProcessingMode,
    get_webhook_dispatcher, classify_webhook_event
)


class TestWebhookProcessingTasks:
    """Test Celery webhook processing tasks."""
    
    @pytest.fixture
    def mock_task_context(self):
        """Create mock Celery task context."""
        mock_task = Mock()
        mock_task.request.id = "test_task_id"
        mock_task.request.retries = 0
        mock_task.max_retries = 3
        return mock_task
    
    @patch('src.tasks.webhook_processing.OpenAIService')
    @patch('src.tasks.webhook_processing.LineService')
    @patch('src.tasks.webhook_processing.create_conversation_service')
    @patch('src.tasks.webhook_processing.Settings')
    def test_process_text_message_async_success(self, mock_settings, mock_conv_service, 
                                              mock_line_service, mock_openai_service):
        """Test successful text message processing."""
        # Setup mocks
        mock_settings.return_value = Mock()
        mock_conv_service.return_value = Mock()
        
        mock_openai = Mock()
        mock_openai.get_response.return_value = {
            'success': True,
            'message': 'Test AI response'
        }
        mock_openai_service.return_value = mock_openai
        
        mock_line = Mock()
        mock_line.line_bot_api.reply_message.return_value = None
        mock_line._create_text_message.return_value = Mock()
        mock_line_service.return_value = mock_line
        
        # Create a mock task instance
        task_instance = Mock()
        task_instance.request.id = "test_task_id"
        
        # Call the function directly (not as Celery task)
        with patch('src.tasks.webhook_processing.connection_pool_manager') as mock_pool:
            mock_pool.execute_with_retry.return_value = None
            
            result = process_text_message_async.__wrapped__(
                task_instance,
                user_id="test_user",
                message_text="Hello",
                reply_token="reply_token",
                correlation_id="test_correlation"
            )
        
        # Verify result
        assert result['success'] is True
        assert result['user_id'] == "test_user"
        assert result['message_length'] == 5
        assert 'processing_time' in result
        
        # Verify mocks were called
        mock_openai.get_response.assert_called_once()
        mock_line.line_bot_api.reply_message.assert_called_once()
    
    @patch('src.tasks.webhook_processing.OpenAIService')
    @patch('src.tasks.webhook_processing.LineService')
    @patch('src.tasks.webhook_processing.create_conversation_service')
    @patch('src.tasks.webhook_processing.Settings')
    def test_process_text_message_async_ai_failure(self, mock_settings, mock_conv_service, 
                                                 mock_line_service, mock_openai_service):
        """Test text message processing with AI failure."""
        # Setup mocks
        mock_settings.return_value = Mock()
        mock_conv_service.return_value = Mock()
        
        mock_openai = Mock()
        mock_openai.get_response.return_value = {
            'success': False,
            'error': 'AI service unavailable'
        }
        mock_openai_service.return_value = mock_openai
        
        # Create a mock task instance with retry method
        task_instance = Mock()
        task_instance.request.id = "test_task_id"
        task_instance.retry = Mock(side_effect=Exception("Retry called"))
        
        # Test that retry is called on AI failure
        with pytest.raises(Exception, match="Retry called"):
            process_text_message_async.__wrapped__(
                task_instance,
                user_id="test_user",
                message_text="Hello",
                reply_token="reply_token",
                correlation_id="test_correlation"
            )
    
    @patch('src.tasks.webhook_processing.ImageProcessor')
    @patch('src.tasks.webhook_processing.OpenAIService')
    @patch('src.tasks.webhook_processing.LineService')
    @patch('src.tasks.webhook_processing.create_conversation_service')
    @patch('src.tasks.webhook_processing.Settings')
    def test_process_image_message_async_success(self, mock_settings, mock_conv_service,
                                               mock_line_service, mock_openai_service, 
                                               mock_image_processor):
        """Test successful image message processing."""
        # Setup mocks
        mock_settings.return_value = Mock()
        mock_conv_service.return_value = Mock()
        
        mock_openai = Mock()
        mock_openai.get_response.return_value = {
            'success': True,
            'message': 'I can see an image'
        }
        mock_openai_service.return_value = mock_openai
        
        mock_line = Mock()
        mock_line.line_bot_api.reply_message.return_value = None
        mock_line._create_text_message.return_value = Mock()
        mock_line_service.return_value = mock_line
        
        # Mock image processor
        mock_processor_instance = Mock()
        mock_processor_instance.download_image_from_line.return_value = {
            'success': True,
            'image_data': b'fake_image_data',
            'size': 1024,
            'format': 'JPEG'
        }
        mock_image_processor.return_value.__enter__.return_value = mock_processor_instance
        
        # Create a mock task instance
        task_instance = Mock()
        task_instance.request.id = "test_task_id"
        
        # Call the function directly
        with patch('src.tasks.webhook_processing.connection_pool_manager') as mock_pool:
            mock_pool.execute_with_retry.return_value = None
            
            result = process_image_message_async.__wrapped__(
                task_instance,
                user_id="test_user",
                message_id="msg_123",
                reply_token="reply_token",
                correlation_id="test_correlation"
            )
        
        # Verify result
        assert result['success'] is True
        assert result['user_id'] == "test_user"
        assert result['message_id'] == "msg_123"
        assert result['image_size'] == 1024
        assert result['image_format'] == 'JPEG'
        
        # Verify mocks were called
        mock_processor_instance.download_image_from_line.assert_called_once()
        mock_openai.get_response.assert_called_once()
        mock_line.line_bot_api.reply_message.assert_called_once()
    
    def test_process_postback_async_success(self):
        """Test successful postback processing."""
        # Create a mock task instance
        task_instance = Mock()
        task_instance.request.id = "test_task_id"
        
        postback_data = json.dumps({'action': 'like_action', 'item_id': '123'})
        
        with patch('src.tasks.webhook_processing.LineService') as mock_line_service, \
             patch('src.tasks.webhook_processing.Settings') as mock_settings, \
             patch('src.tasks.webhook_processing.connection_pool_manager') as mock_pool:
            
            # Setup mocks
            mock_settings.return_value = Mock()
            mock_line = Mock()
            mock_line.line_bot_api.reply_message.return_value = None
            mock_line._create_text_message.return_value = Mock()
            mock_line_service.return_value = mock_line
            mock_pool.execute_with_retry.return_value = None
            
            result = process_postback_async.__wrapped__(
                task_instance,
                user_id="test_user",
                postback_data=postback_data,
                reply_token="reply_token",
                correlation_id="test_correlation"
            )
        
        # Verify result
        assert result['success'] is True
        assert result['user_id'] == "test_user"
        assert result['action'] == 'like_action'
        assert 'Thanks for the like!' in result['response_message']
    
    @patch('src.tasks.webhook_processing.get_async_pipeline')
    def test_batch_process_rich_messages_with_pipeline(self, mock_get_pipeline):
        """Test batch Rich Message processing with async pipeline."""
        # Setup mock pipeline
        mock_pipeline = Mock()
        mock_pipeline.is_running = True
        mock_pipeline.submit_batch_delivery_task = AsyncMock(return_value="batch_task_123")
        mock_get_pipeline.return_value = mock_pipeline
        
        user_ids = ["user1", "user2", "user3"]
        
        # Need to handle the async call within the sync function
        import asyncio
        
        def run_async_part():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    mock_pipeline.submit_batch_delivery_task(
                        user_ids=user_ids,
                        content_template="Test message",
                        template_category="general"
                    )
                )
            finally:
                loop.close()
        
        with patch('asyncio.new_event_loop') as mock_new_loop, \
             patch('asyncio.set_event_loop') as mock_set_loop:
            
            mock_loop = Mock()
            mock_loop.run_until_complete.return_value = "batch_task_123"
            mock_new_loop.return_value = mock_loop
            
            result = batch_process_rich_messages(
                user_ids=user_ids,
                message_template="Test message",
                template_category="general",
                correlation_id="test_correlation"
            )
        
        # Verify result
        assert result['success'] is True
        assert result['method'] == 'async_pipeline'
        assert result['async_task_id'] == "batch_task_123"
        assert result['total_users'] == 3
    
    @patch('src.tasks.webhook_processing.get_async_pipeline')
    @patch('src.tasks.webhook_processing.LineService')
    @patch('src.tasks.webhook_processing.Settings')
    def test_batch_process_rich_messages_fallback(self, mock_settings, mock_line_service, 
                                                 mock_get_pipeline):
        """Test batch Rich Message processing fallback to sync."""
        # Setup mocks for fallback scenario
        mock_get_pipeline.return_value = None  # No pipeline available
        
        mock_settings.return_value = Mock()
        mock_line = Mock()
        mock_line.line_bot_api.push_message.return_value = None
        mock_line._create_text_message.return_value = Mock()
        mock_line_service.return_value = mock_line
        
        user_ids = ["user1", "user2"]
        
        result = batch_process_rich_messages(
            user_ids=user_ids,
            message_template="Test message",
            correlation_id="test_correlation"
        )
        
        # Verify fallback result
        assert result['success'] is True
        assert result['method'] == 'synchronous_fallback'
        assert result['delivered_count'] == 2
        assert result['failed_count'] == 0
        assert result['total_users'] == 2
    
    @patch('src.tasks.webhook_processing.connection_pool_manager')
    def test_webhook_processing_health_check(self, mock_pool_manager):
        """Test webhook processing health check."""
        # Setup mock pool metrics
        mock_pool_manager.get_metrics.return_value = {
            'total_pools': 3,
            'health': {
                'pool1': {'state': 'healthy'},
                'pool2': {'state': 'healthy'},
                'pool3': {'state': 'degraded'}
            }
        }
        
        with patch('src.tasks.webhook_processing.get_async_pipeline') as mock_get_pipeline:
            mock_pipeline = Mock()
            mock_pipeline.is_running = True
            mock_get_pipeline.return_value = mock_pipeline
            
            result = webhook_processing_health_check()
        
        # Verify health check result
        assert result['status'] == 'healthy'
        assert 'timestamp' in result
        assert result['components']['celery_worker'] is True
        assert result['components']['connection_pools'] is True
        assert result['components']['async_pipeline'] is True
        assert result['pool_metrics']['total_pools'] == 3
        assert result['pool_metrics']['healthy_connections'] == 2
    
    @patch('src.tasks.webhook_processing.celery_app')
    @patch('src.tasks.webhook_processing.connection_pool_manager')
    def test_collect_webhook_metrics(self, mock_pool_manager, mock_celery_app):
        """Test webhook metrics collection."""
        # Setup mock Celery inspect
        mock_inspect = Mock()
        mock_inspect.active.return_value = {'worker1': [{'id': 'task1'}]}
        mock_inspect.scheduled.return_value = {'worker1': []}
        mock_inspect.reserved.return_value = {'worker1': [{'id': 'task2'}]}
        
        mock_celery_app.control.inspect.return_value = mock_inspect
        
        # Setup mock pool metrics
        mock_pool_manager.get_metrics.return_value = {
            'total_pools': 2,
            'health': {'pool1': {'state': 'healthy'}}
        }
        
        result = collect_webhook_metrics()
        
        # Verify metrics result
        assert result['status'] == 'healthy'
        assert 'timestamp' in result
        assert result['celery_metrics']['active_tasks'] == 1
        assert result['celery_metrics']['scheduled_tasks'] == 0
        assert result['celery_metrics']['reserved_tasks'] == 1
        assert result['celery_metrics']['total_queued'] == 1


class TestAsyncWebhookDispatcher:
    """Test async webhook dispatcher."""
    
    @pytest.fixture
    def dispatcher(self):
        """Create a dispatcher for testing."""
        return AsyncWebhookDispatcher(
            default_mode=ProcessingMode.HYBRID,
            enable_celery=True
        )
    
    def test_dispatcher_initialization(self, dispatcher):
        """Test dispatcher initialization."""
        assert dispatcher.default_mode == ProcessingMode.HYBRID
        assert dispatcher.enable_celery is True
        assert dispatcher.sync_timeout == 5.0
        assert dispatcher.current_sync_tasks == 0
        assert dispatcher.processing_stats['total_requests'] == 0
    
    def test_determine_processing_mode(self, dispatcher):
        """Test processing mode determination logic."""
        # Test image message -> async
        image_event = {'type': 'message', 'message': {'type': 'image'}}
        mode = dispatcher._determine_processing_mode(WebhookType.IMAGE_MESSAGE, image_event)
        assert mode == ProcessingMode.ASYNCHRONOUS
        
        # Test postback -> sync
        postback_event = {'type': 'postback'}
        mode = dispatcher._determine_processing_mode(WebhookType.POSTBACK, postback_event)
        assert mode == ProcessingMode.SYNCHRONOUS
        
        # Test short text message -> sync
        text_event = {'message': {'text': 'Hello'}}
        mode = dispatcher._determine_processing_mode(WebhookType.TEXT_MESSAGE, text_event)
        assert mode == ProcessingMode.SYNCHRONOUS
        
        # Test long text message -> async
        long_text_event = {'message': {'text': 'Please analyze this in detail: ' + 'x' * 200}}
        mode = dispatcher._determine_processing_mode(WebhookType.TEXT_MESSAGE, long_text_event)
        assert mode == ProcessingMode.ASYNCHRONOUS
    
    def test_should_process_async_load_balancing(self, dispatcher):
        """Test async processing decision based on load."""
        # Set high sync load
        dispatcher.current_sync_tasks = dispatcher.max_concurrent_sync
        
        # Even a simple postback should go async due to high load
        result = dispatcher._should_process_async(WebhookType.POSTBACK, {})
        assert result is True
    
    async def test_dispatch_webhook_sync_mode(self, dispatcher):
        """Test webhook dispatch in synchronous mode."""
        event_data = {
            'type': 'postback',
            'source': {'userId': 'test_user'},
            'replyToken': 'reply_123',
            'postback': {'data': 'test_data'}
        }
        
        with patch.object(dispatcher, '_process_synchronously') as mock_sync:
            mock_sync.return_value = {
                'success': True,
                'processing_mode': 'sync',
                'user_id': 'test_user'
            }
            
            result = await dispatcher.dispatch_webhook(
                WebhookType.POSTBACK,
                event_data,
                ProcessingMode.SYNCHRONOUS
            )
        
        assert result['success'] is True
        assert result['processing_mode'] == 'sync'
        mock_sync.assert_called_once()
    
    async def test_dispatch_webhook_async_mode(self, dispatcher):
        """Test webhook dispatch in asynchronous mode."""
        event_data = {
            'type': 'message',
            'message': {'type': 'image', 'id': 'img_123'},
            'source': {'userId': 'test_user'},
            'replyToken': 'reply_123'
        }
        
        with patch.object(dispatcher, '_process_asynchronously') as mock_async:
            mock_async.return_value = {
                'success': True,
                'processing_mode': 'async',
                'task_id': 'celery_task_123'
            }
            
            result = await dispatcher.dispatch_webhook(
                WebhookType.IMAGE_MESSAGE,
                event_data,
                ProcessingMode.ASYNCHRONOUS
            )
        
        assert result['success'] is True
        assert result['processing_mode'] == 'async'
        mock_async.assert_called_once()
    
    async def test_dispatch_webhook_hybrid_mode(self, dispatcher):
        """Test webhook dispatch in hybrid mode."""
        # Test that hybrid mode chooses appropriately
        text_event = {
            'type': 'message',
            'message': {'type': 'text', 'text': 'Hello'},
            'source': {'userId': 'test_user'},
            'replyToken': 'reply_123'
        }
        
        with patch.object(dispatcher, '_process_synchronously') as mock_sync:
            mock_sync.return_value = {
                'success': True,
                'processing_mode': 'sync'
            }
            
            result = await dispatcher.dispatch_webhook(
                WebhookType.TEXT_MESSAGE,
                text_event,
                ProcessingMode.HYBRID
            )
        
        # Short text should go sync in hybrid mode
        assert result['processing_mode'] == 'sync'
        mock_sync.assert_called_once()
    
    def test_get_statistics(self, dispatcher):
        """Test statistics retrieval."""
        # Update some stats
        dispatcher.processing_stats['total_requests'] = 10
        dispatcher.processing_stats['sync_requests'] = 6
        dispatcher.processing_stats['async_requests'] = 4
        dispatcher.current_sync_tasks = 2
        
        stats = dispatcher.get_statistics()
        
        assert stats['processing_stats']['total_requests'] == 10
        assert stats['processing_stats']['sync_requests'] == 6
        assert stats['processing_stats']['async_requests'] == 4
        assert stats['current_state']['current_sync_tasks'] == 2
        assert stats['configuration']['default_mode'] == 'hybrid'
        assert 'timestamp' in stats


class TestWebhookUtilities:
    """Test webhook utility functions."""
    
    def test_classify_webhook_event_text_message(self):
        """Test classification of text message events."""
        event_data = {
            'type': 'message',
            'message': {'type': 'text', 'text': 'Hello'}
        }
        
        webhook_type = classify_webhook_event(event_data)
        assert webhook_type == WebhookType.TEXT_MESSAGE
    
    def test_classify_webhook_event_image_message(self):
        """Test classification of image message events."""
        event_data = {
            'type': 'message',
            'message': {'type': 'image', 'id': 'img_123'}
        }
        
        webhook_type = classify_webhook_event(event_data)
        assert webhook_type == WebhookType.IMAGE_MESSAGE
    
    def test_classify_webhook_event_postback(self):
        """Test classification of postback events."""
        event_data = {
            'type': 'postback',
            'postback': {'data': 'action=like'}
        }
        
        webhook_type = classify_webhook_event(event_data)
        assert webhook_type == WebhookType.POSTBACK
    
    def test_classify_webhook_event_follow(self):
        """Test classification of follow events."""
        event_data = {'type': 'follow'}
        
        webhook_type = classify_webhook_event(event_data)
        assert webhook_type == WebhookType.FOLLOW
    
    def test_classify_webhook_event_unknown(self):
        """Test classification of unknown events."""
        event_data = {'type': 'unknown_event'}
        
        webhook_type = classify_webhook_event(event_data)
        assert webhook_type == WebhookType.UNKNOWN
    
    def test_get_webhook_dispatcher_singleton(self):
        """Test global webhook dispatcher singleton."""
        dispatcher1 = get_webhook_dispatcher()
        dispatcher2 = get_webhook_dispatcher()
        
        assert dispatcher1 is dispatcher2
        assert isinstance(dispatcher1, AsyncWebhookDispatcher)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
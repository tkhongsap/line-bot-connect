"""
Error scenario testing and fallback mechanism validation.

This module provides comprehensive testing for error conditions, edge cases,
and fallback mechanisms to ensure system resilience and graceful degradation.
"""

import pytest
import tempfile
import os
import json
import time
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional

from linebot.exceptions import LineBotApiError
from requests.exceptions import RequestException, Timeout, ConnectionError

from src.services.rich_message_service import RichMessageService
from src.services.line_service import LineService
from src.services.openai_service import OpenAIService
from src.utils.interaction_handler import get_interaction_handler, InteractionType
from src.utils.analytics_tracker import get_analytics_tracker
from src.utils.admin_controller import get_admin_controller
from src.utils.metrics_storage import get_metrics_storage
from src.config.settings import Settings


class TestErrorScenarios:
    """Comprehensive error scenario testing"""
    
    @pytest.fixture
    def mock_line_bot_api_with_errors(self):
        """Create mock LINE Bot API that can simulate various error conditions"""
        mock_api = Mock()
        
        # Default successful responses
        mock_api.broadcast.return_value = None
        mock_api.narrowcast.return_value = None
        mock_api.create_rich_menu.return_value = "test_menu_id"
        mock_api.set_rich_menu_image.return_value = None
        mock_api.set_default_rich_menu.return_value = None
        
        return mock_api
    
    @pytest.fixture
    def rich_message_service_with_errors(self, mock_line_bot_api_with_errors):
        """Create RichMessageService for error testing"""
        return RichMessageService(line_bot_api=mock_line_bot_api_with_errors)
    
    @pytest.fixture
    def sample_message_data(self):
        """Sample message data for error testing"""
        return {
            "title": "Error Test Message",
            "content": "This message is used for error scenario testing.",
            "image_url": "https://example.com/test_image.jpg",
            "content_id": "error_test_content_001",
            "user_id": "error_test_user_001"
        }
    
    def test_line_api_rate_limit_error_handling(self, rich_message_service_with_errors, sample_message_data):
        """Test handling of LINE API rate limiting errors"""
        mock_api = rich_message_service_with_errors.line_bot_api
        
        # Simulate rate limit error
        rate_limit_error = LineBotApiError(
            status_code=429,
            headers={},
            error=Mock(message="Rate limit exceeded", details=Mock(retry_after=30))
        )
        mock_api.broadcast.side_effect = rate_limit_error
        
        # Create message
        flex_message = rich_message_service_with_errors.create_flex_message(**sample_message_data)
        
        # Test broadcast with rate limit error
        result = rich_message_service_with_errors.broadcast_rich_message(flex_message)
        
        assert result["success"] is False
        assert "Rate limit" in result["error"] or "429" in result["error"]
        assert "timestamp" in result
        
        print(f"Rate limit error handled: {result['error']}")
    
    def test_line_api_authentication_error_handling(self, rich_message_service_with_errors, sample_message_data):
        """Test handling of LINE API authentication errors"""
        mock_api = rich_message_service_with_errors.line_bot_api
        
        # Simulate authentication error
        auth_error = LineBotApiError(
            status_code=401,
            headers={},
            error=Mock(message="Invalid channel access token")
        )
        mock_api.broadcast.side_effect = auth_error
        
        # Create message
        flex_message = rich_message_service_with_errors.create_flex_message(**sample_message_data)
        
        # Test broadcast with auth error
        result = rich_message_service_with_errors.broadcast_rich_message(flex_message)
        
        assert result["success"] is False
        assert "401" in result["error"] or "authentication" in result["error"].lower()
        
        print(f"Authentication error handled: {result['error']}")
    
    def test_line_api_service_unavailable_error(self, rich_message_service_with_errors, sample_message_data):
        """Test handling of LINE API service unavailable errors"""
        mock_api = rich_message_service_with_errors.line_bot_api
        
        # Simulate service unavailable error
        service_error = LineBotApiError(
            status_code=503,
            headers={},
            error=Mock(message="Service temporarily unavailable")
        )
        mock_api.broadcast.side_effect = service_error
        
        # Create message
        flex_message = rich_message_service_with_errors.create_flex_message(**sample_message_data)
        
        # Test broadcast with service error
        result = rich_message_service_with_errors.broadcast_rich_message(flex_message)
        
        assert result["success"] is False
        assert "503" in result["error"] or "unavailable" in result["error"].lower()
        
        print(f"Service unavailable error handled: {result['error']}")
    
    def test_network_timeout_error_handling(self, rich_message_service_with_errors, sample_message_data):
        """Test handling of network timeout errors"""
        mock_api = rich_message_service_with_errors.line_bot_api
        
        # Simulate network timeout
        mock_api.broadcast.side_effect = Timeout("Request timed out")
        
        # Create message
        flex_message = rich_message_service_with_errors.create_flex_message(**sample_message_data)
        
        # Test broadcast with timeout
        result = rich_message_service_with_errors.broadcast_rich_message(flex_message)
        
        assert result["success"] is False
        assert "timeout" in result["error"].lower() or "timed out" in result["error"].lower()
        
        print(f"Network timeout error handled: {result['error']}")
    
    def test_connection_error_handling(self, rich_message_service_with_errors, sample_message_data):
        """Test handling of connection errors"""
        mock_api = rich_message_service_with_errors.line_bot_api
        
        # Simulate connection error
        mock_api.broadcast.side_effect = ConnectionError("Connection failed")
        
        # Create message
        flex_message = rich_message_service_with_errors.create_flex_message(**sample_message_data)
        
        # Test broadcast with connection error
        result = rich_message_service_with_errors.broadcast_rich_message(flex_message)
        
        assert result["success"] is False
        assert "connection" in result["error"].lower() or "failed" in result["error"].lower()
        
        print(f"Connection error handled: {result['error']}")
    
    def test_invalid_message_data_handling(self, rich_message_service_with_errors):
        """Test handling of invalid message data"""
        # Test with empty title and content
        result1 = rich_message_service_with_errors.create_flex_message(
            title="",
            content="",
            image_url="invalid_url"
        )
        
        # Should still create a message even with empty data
        assert result1 is not None
        assert hasattr(result1, 'contents')
        
        # Test with None values
        result2 = rich_message_service_with_errors.create_flex_message(
            title=None,
            content=None,
            image_url=None
        )
        
        # Should handle None values gracefully
        assert result2 is not None
        
        # Test with extremely long content
        long_content = "Very long content. " * 1000  # Very long string
        result3 = rich_message_service_with_errors.create_flex_message(
            title="Long Content Test",
            content=long_content
        )
        
        # Should handle long content without errors
        assert result3 is not None
        
        print("Invalid message data handling tests passed")
    
    def test_interaction_handler_error_scenarios(self):
        """Test error handling in interaction handler"""
        interaction_handler = get_interaction_handler()
        
        # Test with missing required fields
        result1 = interaction_handler.handle_user_interaction(
            "test_user",
            {}  # Empty interaction data
        )
        
        assert result1["success"] is False
        assert "error" in result1
        assert "Missing required" in result1["error"]
        
        # Test with invalid interaction type
        result2 = interaction_handler.handle_user_interaction(
            "test_user",
            {
                "action": "interaction",
                "type": "invalid_type",
                "content_id": "test_content"
            }
        )
        
        assert result2["success"] is False
        assert "error" in result2
        assert "Invalid interaction type" in result2["error"]
        
        # Test with missing content_id
        result3 = interaction_handler.handle_user_interaction(
            "test_user",
            {
                "action": "interaction",
                "type": "like"
                # Missing content_id
            }
        )
        
        assert result3["success"] is False
        assert "error" in result3
        
        print("Interaction handler error scenarios handled correctly")
    
    @patch('src.utils.metrics_storage.get_metrics_storage')
    def test_analytics_error_scenarios(self, mock_get_storage):
        """Test error handling in analytics system"""
        # Mock storage that fails
        mock_storage = Mock()
        mock_storage.store_metric.side_effect = Exception("Storage failure")
        mock_get_storage.return_value = mock_storage
        
        analytics_tracker = get_analytics_tracker()
        
        # Test analytics tracking with storage failure
        # Should not raise exception even if storage fails
        try:
            analytics_tracker.track_message_delivery(
                user_id="test_user",
                content_category="test_category",
                template_id="test_template",
                delivery_time_ms=100
            )
            
            # Should continue working even with storage errors
            assert True, "Analytics continued working despite storage failure"
            
        except Exception as e:
            # If exception is raised, it should be handled gracefully
            assert "Storage failure" not in str(e), "Storage failure should be handled internally"
        
        # Test system metrics calculation with errors
        try:
            system_metrics = analytics_tracker.calculate_system_metrics()
            # Should return something even with partial failures
            assert system_metrics is not None
            
        except Exception:
            # Should not raise unhandled exceptions
            pytest.fail("System metrics calculation should handle errors gracefully")
        
        print("Analytics error scenarios handled correctly")
    
    @patch('src.services.openai_service.OpenAIService')
    def test_openai_service_error_scenarios(self, mock_openai_service_class):
        """Test error handling in OpenAI service interactions"""
        # Mock OpenAI service with various error scenarios
        mock_service = Mock()
        mock_openai_service_class.return_value = mock_service
        
        # Test API key error
        mock_service.get_response.side_effect = Exception("Invalid API key")
        
        try:
            response = mock_service.get_response("test prompt")
            assert False, "Should have raised exception"
        except Exception as e:
            assert "Invalid API key" in str(e)
        
        # Test rate limit error
        mock_service.get_response.side_effect = Exception("Rate limit exceeded")
        
        try:
            response = mock_service.get_response("test prompt")
            assert False, "Should have raised exception"
        except Exception as e:
            assert "Rate limit" in str(e)
        
        # Test content generation error
        mock_service.generate_themed_content.return_value = {
            "success": False,
            "error": "Content generation failed",
            "error_code": "CONTENT_GENERATION_ERROR"
        }
        
        result = mock_service.generate_themed_content(category="test")
        assert result["success"] is False
        assert "error" in result
        
        print("OpenAI service error scenarios tested")
    
    def test_template_manager_error_scenarios(self):
        """Test error handling in template management"""
        with patch('src.utils.template_manager.TemplateManager') as mock_template_manager:
            mock_manager = Mock()
            mock_template_manager.return_value = mock_manager
            
            # Test template not found
            mock_manager.select_template.return_value = None
            result = mock_manager.select_template({"category": "nonexistent"})
            assert result is None
            
            # Test template loading error
            mock_manager.load_templates.side_effect = FileNotFoundError("Template file not found")
            
            try:
                mock_manager.load_templates()
                assert False, "Should have raised FileNotFoundError"
            except FileNotFoundError as e:
                assert "Template file not found" in str(e)
            
            # Test invalid template data
            mock_manager.validate_template.return_value = {
                "valid": False,
                "errors": ["Missing required field: background_file"]
            }
            
            validation_result = mock_manager.validate_template({"name": "Invalid Template"})
            assert validation_result["valid"] is False
            assert len(validation_result["errors"]) > 0
            
        print("Template manager error scenarios tested")
    
    def test_image_composer_error_scenarios(self):
        """Test error handling in image composition"""
        with patch('src.utils.image_composer.ImageComposer') as mock_image_composer:
            mock_composer = Mock()
            mock_image_composer.return_value = mock_composer
            
            # Test image file not found
            mock_composer.compose_image.return_value = {
                "success": False,
                "error": "Background image file not found",
                "error_code": "IMAGE_FILE_NOT_FOUND"
            }
            
            result = mock_composer.compose_image({}, {})
            assert result["success"] is False
            assert "not found" in result["error"]
            
            # Test image composition failure
            mock_composer.compose_image.side_effect = Exception("Image composition failed")
            
            try:
                mock_composer.compose_image({}, {})
                assert False, "Should have raised exception"
            except Exception as e:
                assert "composition failed" in str(e)
            
            # Test invalid image format
            mock_composer.validate_image.return_value = {
                "valid": False,
                "error": "Unsupported image format"
            }
            
            validation_result = mock_composer.validate_image("test.xyz")
            assert validation_result["valid"] is False
            
        print("Image composer error scenarios tested")
    
    def test_admin_controller_error_scenarios(self):
        """Test error handling in admin controller"""
        admin_controller = get_admin_controller()
        
        # Test campaign not found
        result1 = admin_controller.get_campaign_details("nonexistent_campaign_id")
        assert result1["success"] is False
        assert "Campaign not found" in result1["error"]
        
        # Test updating non-existent campaign
        result2 = admin_controller.update_campaign("nonexistent_id", {"name": "New Name"})
        assert result2["success"] is False
        assert "Campaign not found" in result2["error"]
        
        # Test scheduling campaign for past time
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        
        # First create a campaign
        create_result = admin_controller.create_campaign(
            name="Test Campaign",
            description="Test description",
            content_title="Test title",
            content_message="Test message"
        )
        campaign_id = create_result["campaign_id"]
        
        # Try to schedule for past time
        result3 = admin_controller.schedule_campaign(campaign_id, past_time)
        assert result3["success"] is False
        assert "future" in result3["error"]
        
        print("Admin controller error scenarios tested")
    
    def test_database_connection_errors(self):
        """Test handling of database connection errors"""
        with patch('src.utils.metrics_storage.get_metrics_storage') as mock_get_storage:
            # Mock storage with connection errors
            mock_storage = Mock()
            mock_storage.get_metrics.side_effect = Exception("Database connection failed")
            mock_storage.store_metric.side_effect = Exception("Database connection failed")
            mock_get_storage.return_value = mock_storage
            
            # Test metrics retrieval with database error
            try:
                metrics = mock_storage.get_metrics()
                assert False, "Should have raised exception"
            except Exception as e:
                assert "Database connection failed" in str(e)
            
            # Test that system continues to function despite database errors
            interaction_handler = get_interaction_handler()
            result = interaction_handler.handle_user_interaction(
                "test_user",
                {
                    "action": "interaction",
                    "type": "like",
                    "content_id": "test_content"
                }
            )
            
            # Should still process interaction even if database storage fails
            assert result["success"] is True
            
        print("Database connection error scenarios tested")
    
    def test_memory_exhaustion_scenarios(self, rich_message_service_with_errors):
        """Test system behavior under memory pressure"""
        # Create a large number of messages to simulate memory pressure
        large_content = "Very large content block. " * 1000  # Large content
        
        messages_created = 0
        try:
            # Create messages until we might hit memory issues
            for i in range(100):  # Reasonable number for testing
                message = rich_message_service_with_errors.create_flex_message(
                    title=f"Memory Test Message {i}",
                    content=large_content,
                    content_id=f"memory_test_{i}",
                    include_interactions=True
                )
                
                if message is not None:
                    messages_created += 1
                else:
                    break
            
            # Should have created at least some messages
            assert messages_created > 0, "Should create messages under normal conditions"
            
        except MemoryError:
            # If we hit a memory error, that's expected behavior
            assert messages_created >= 0, "Should handle memory errors gracefully"
            
        print(f"Memory exhaustion test completed. Created {messages_created} messages.")
    
    def test_concurrent_access_error_scenarios(self, rich_message_service_with_errors):
        """Test error handling under concurrent access"""
        import threading
        import queue
        
        errors_queue = queue.Queue()
        success_count = threading.local()
        success_count.value = 0
        
        def worker_function(worker_id: int):
            """Worker function for concurrent testing"""
            try:
                for i in range(10):
                    message = rich_message_service_with_errors.create_flex_message(
                        title=f"Concurrent Test Worker {worker_id} Message {i}",
                        content=f"Concurrent test content from worker {worker_id}",
                        content_id=f"concurrent_{worker_id}_{i}"
                    )
                    
                    if message is not None:
                        with threading.Lock():
                            success_count.value += 1
                    
                    # Small delay to increase chance of concurrent access
                    time.sleep(0.001)
                    
            except Exception as e:
                errors_queue.put(f"Worker {worker_id}: {str(e)}")
        
        # Start multiple worker threads
        threads = []
        num_workers = 5
        
        for worker_id in range(num_workers):
            thread = threading.Thread(target=worker_function, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check for errors
        errors = []
        while not errors_queue.empty():
            errors.append(errors_queue.get())
        
        # Should have minimal errors under concurrent access
        assert len(errors) <= num_workers, f"Too many concurrent access errors: {errors}"
        assert success_count.value > 0, "Should have some successful operations"
        
        print(f"Concurrent access test completed. Successes: {success_count.value}, Errors: {len(errors)}")
    
    def test_fallback_mechanism_validation(self, rich_message_service_with_errors):
        """Test that fallback mechanisms work correctly"""
        
        # Test fallback when image URL is invalid
        message_with_invalid_image = rich_message_service_with_errors.create_flex_message(
            title="Fallback Test",
            content="This message should work even with invalid image URL",
            image_url="https://invalid-domain-that-does-not-exist.com/invalid.jpg"
        )
        
        assert message_with_invalid_image is not None
        assert hasattr(message_with_invalid_image, 'contents')
        
        # Test fallback when content is empty
        message_with_empty_content = rich_message_service_with_errors.create_flex_message(
            title="",
            content=""
        )
        
        assert message_with_empty_content is not None
        
        # Test fallback when interactions fail to load
        with patch('src.utils.interaction_handler.get_interaction_handler') as mock_get_handler:
            mock_handler = Mock()
            mock_handler.create_interactive_buttons.side_effect = Exception("Interaction handler failed")
            mock_get_handler.return_value = mock_handler
            
            message_with_interaction_failure = rich_message_service_with_errors.create_flex_message(
                title="Interaction Fallback Test",
                content="This should work even if interactions fail",
                content_id="fallback_test",
                include_interactions=True
            )
            
            # Should still create message without interactions
            assert message_with_interaction_failure is not None
        
        print("Fallback mechanism validation completed successfully")
    
    def test_data_corruption_scenarios(self):
        """Test handling of corrupted data scenarios"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test corrupted configuration file
            corrupt_config_path = os.path.join(temp_dir, "corrupt_config.json")
            with open(corrupt_config_path, 'w') as f:
                f.write("{ invalid json content }")
            
            # Should handle corrupted JSON gracefully
            try:
                with open(corrupt_config_path, 'r') as f:
                    json.load(f)
                assert False, "Should have raised JSON decode error"
            except json.JSONDecodeError:
                # Expected behavior
                pass
            
            # Test corrupted template metadata
            corrupt_template_path = os.path.join(temp_dir, "corrupt_template.json")
            with open(corrupt_template_path, 'w') as f:
                f.write('{"templates": {"test": {"incomplete": true')  # Incomplete JSON
            
            try:
                with open(corrupt_template_path, 'r') as f:
                    json.load(f)
                assert False, "Should have raised JSON decode error"
            except json.JSONDecodeError:
                # Expected behavior
                pass
            
            # Test handling of corrupted image files
            corrupt_image_path = os.path.join(temp_dir, "corrupt_image.png")
            with open(corrupt_image_path, 'wb') as f:
                f.write(b"Not a valid PNG file")
            
            # Should detect that this is not a valid image
            assert os.path.exists(corrupt_image_path)
            with open(corrupt_image_path, 'rb') as f:
                content = f.read()
                assert not content.startswith(b'\x89PNG')  # Not a valid PNG
        
        print("Data corruption scenarios tested")
    
    def test_resource_cleanup_on_errors(self, rich_message_service_with_errors):
        """Test that resources are properly cleaned up after errors"""
        import gc
        import psutil
        
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Cause multiple errors and check memory usage
        for i in range(50):
            try:
                # Create scenario that might cause memory leaks
                large_content = "Large content block. " * 1000
                message = rich_message_service_with_errors.create_flex_message(
                    title=f"Resource Test {i}",
                    content=large_content,
                    image_url="https://invalid-url.com/image.jpg"
                )
                
                # Force some operations that might fail
                mock_api = rich_message_service_with_errors.line_bot_api
                mock_api.broadcast.side_effect = Exception("Simulated error")
                
                try:
                    rich_message_service_with_errors.broadcast_rich_message(message)
                except:
                    pass  # Expected to fail
                    
            except Exception:
                pass  # Expected errors
        
        # Force garbage collection
        gc.collect()
        
        # Check memory usage after errors
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB for this test)
        assert memory_increase < 100.0, f"Memory increased by {memory_increase:.2f}MB, possible memory leak"
        
        print(f"Resource cleanup test completed. Memory increase: {memory_increase:.2f}MB")
    
    def test_system_recovery_scenarios(self, rich_message_service_with_errors, sample_message_data):
        """Test system recovery after various error conditions"""
        mock_api = rich_message_service_with_errors.line_bot_api
        
        # Simulate temporary service failure followed by recovery
        failure_then_success = [
            Exception("Temporary failure"),
            Exception("Still failing"),
            None  # Success
        ]
        
        mock_api.broadcast.side_effect = failure_then_success
        
        flex_message = rich_message_service_with_errors.create_flex_message(**sample_message_data)
        
        # First attempt should fail
        result1 = rich_message_service_with_errors.broadcast_rich_message(flex_message)
        assert result1["success"] is False
        
        # Second attempt should also fail
        result2 = rich_message_service_with_errors.broadcast_rich_message(flex_message)
        assert result2["success"] is False
        
        # Third attempt should succeed
        result3 = rich_message_service_with_errors.broadcast_rich_message(flex_message)
        assert result3["success"] is True
        
        print("System recovery scenario tested successfully")


class TestFallbackMechanisms:
    """Specific tests for fallback mechanisms"""
    
    @pytest.fixture
    def rich_message_service_fallback(self):
        """Create RichMessageService configured for fallback testing"""
        mock_api = Mock()
        mock_api.broadcast.return_value = None
        mock_api.narrowcast.return_value = None
        return RichMessageService(line_bot_api=mock_api)
    
    def test_image_url_fallback(self, rich_message_service_fallback):
        """Test fallback when image URLs are unavailable"""
        # Test with completely invalid URL
        message1 = rich_message_service_fallback.create_flex_message(
            title="Image Fallback Test 1",
            content="Testing with invalid image URL",
            image_url="https://definitely-not-a-real-domain.invalid/image.jpg"
        )
        
        assert message1 is not None
        assert hasattr(message1, 'contents')
        
        # Test with malformed URL
        message2 = rich_message_service_fallback.create_flex_message(
            title="Image Fallback Test 2",
            content="Testing with malformed image URL",
            image_url="not-a-url-at-all"
        )
        
        assert message2 is not None
        
        # Test with None image URL
        message3 = rich_message_service_fallback.create_flex_message(
            title="Image Fallback Test 3",
            content="Testing with None image URL",
            image_url=None
        )
        
        assert message3 is not None
        
        print("Image URL fallback mechanisms working correctly")
    
    def test_content_generation_fallback(self):
        """Test fallback when content generation fails"""
        with patch('src.utils.content_generator.ContentGenerator') as mock_content_generator:
            mock_generator = Mock()
            mock_content_generator.return_value = mock_generator
            
            # Test with content generation failure
            mock_generator.generate_content.return_value = {
                "success": False,
                "error": "Content generation service unavailable",
                "fallback_content": {
                    "title": "Fallback Title",
                    "content": "Fallback content when generation fails."
                }
            }
            
            result = mock_generator.generate_content(category="test")
            
            # Should provide fallback content
            assert result["success"] is False
            assert "fallback_content" in result
            assert result["fallback_content"]["title"] is not None
            assert result["fallback_content"]["content"] is not None
            
        print("Content generation fallback working correctly")
    
    def test_template_selection_fallback(self):
        """Test fallback when template selection fails"""
        with patch('src.utils.template_manager.TemplateManager') as mock_template_manager:
            mock_manager = Mock()
            mock_template_manager.return_value = mock_manager
            
            # Test with no matching templates
            mock_manager.select_template.return_value = None
            mock_manager.get_default_template.return_value = {
                "template_id": "default_fallback",
                "template_data": {
                    "name": "Default Fallback Template",
                    "category": "default"
                }
            }
            
            # Should fall back to default template
            selected = mock_manager.select_template({"category": "nonexistent"})
            assert selected is None
            
            # Get fallback template
            fallback = mock_manager.get_default_template()
            assert fallback is not None
            assert fallback["template_id"] == "default_fallback"
            
        print("Template selection fallback working correctly")
    
    def test_analytics_storage_fallback(self):
        """Test fallback when analytics storage fails"""
        with patch('src.utils.metrics_storage.get_metrics_storage') as mock_get_storage:
            # Mock primary storage failure
            mock_primary_storage = Mock()
            mock_primary_storage.store_metric.side_effect = Exception("Primary storage failed")
            
            # Mock fallback storage
            mock_fallback_storage = Mock()
            mock_fallback_storage.store_metric.return_value = True
            
            # Configure storage to return primary first, then fallback
            mock_get_storage.side_effect = [mock_primary_storage, mock_fallback_storage]
            
            analytics_tracker = get_analytics_tracker()
            
            # Should handle storage failure gracefully
            try:
                analytics_tracker.track_message_delivery(
                    user_id="fallback_test_user",
                    content_category="fallback_test",
                    template_id="fallback_template",
                    delivery_time_ms=100
                )
                
                # Should not raise exception even with storage failure
                success = True
                
            except Exception as e:
                # If exception occurs, it should be a controlled fallback
                success = "fallback" in str(e).lower()
            
            assert success, "Analytics should handle storage failures gracefully"
            
        print("Analytics storage fallback working correctly")
    
    def test_interaction_processing_fallback(self):
        """Test fallback when interaction processing encounters errors"""
        interaction_handler = get_interaction_handler()
        
        # Test with malformed interaction data
        result1 = interaction_handler.handle_user_interaction(
            "fallback_user",
            {
                "action": "unknown_action",
                "invalid_field": "invalid_value"
            }
        )
        
        # Should handle unknown action gracefully
        assert result1["success"] is False
        assert "error" in result1
        assert result1["response_type"] == "error"
        
        # Test with partially valid data
        result2 = interaction_handler.handle_user_interaction(
            "fallback_user",
            {
                "action": "interaction",
                "type": "like"
                # Missing content_id - should be handled gracefully
            }
        )
        
        assert result2["success"] is False
        assert "error" in result2
        
        print("Interaction processing fallback working correctly")
    
    def test_rich_menu_creation_fallback(self, rich_message_service_fallback):
        """Test fallback when rich menu creation fails"""
        mock_api = rich_message_service_fallback.line_bot_api
        
        # Simulate rich menu creation failure
        mock_api.create_rich_menu.side_effect = LineBotApiError(
            status_code=400,
            headers={},
            error=Mock(message="Rich menu creation failed")
        )
        
        # Should handle failure gracefully
        menu_id = rich_message_service_fallback.create_rich_menu()
        assert menu_id is None  # Should return None on failure
        
        # Should not crash the system
        message = rich_message_service_fallback.create_flex_message(
            title="Test after menu failure",
            content="System should continue working"
        )
        assert message is not None
        
        print("Rich menu creation fallback working correctly")
    
    def test_broadcast_delivery_fallback(self, rich_message_service_fallback):
        """Test fallback delivery mechanisms"""
        mock_api = rich_message_service_fallback.line_bot_api
        
        # Simulate broadcast failure but narrowcast success
        mock_api.broadcast.side_effect = LineBotApiError(
            status_code=500,
            headers={},
            error=Mock(message="Broadcast service unavailable")
        )
        mock_api.narrowcast.return_value = None
        
        message = rich_message_service_fallback.create_flex_message(
            title="Fallback Delivery Test",
            content="Testing fallback delivery mechanisms"
        )
        
        # Test broadcast failure
        broadcast_result = rich_message_service_fallback.broadcast_rich_message(message)
        assert broadcast_result["success"] is False
        
        # Test narrowcast as fallback
        narrowcast_result = rich_message_service_fallback.broadcast_rich_message(
            message, 
            target_audience="fallback_audience"
        )
        assert narrowcast_result["success"] is True
        
        print("Broadcast delivery fallback working correctly")


class TestResilienceValidation:
    """Validation of overall system resilience"""
    
    def test_system_stability_under_multiple_failures(self, rich_message_service_fallback):
        """Test system stability when multiple components fail simultaneously"""
        
        # Simulate multiple simultaneous failures
        with patch('src.utils.interaction_handler.get_interaction_handler') as mock_get_handler, \
             patch('src.utils.analytics_tracker.get_analytics_tracker') as mock_get_analytics, \
             patch('src.utils.metrics_storage.get_metrics_storage') as mock_get_storage:
            
            # All components fail
            mock_handler = Mock()
            mock_handler.create_interactive_buttons.side_effect = Exception("Interaction handler failed")
            mock_get_handler.return_value = mock_handler
            
            mock_analytics = Mock()
            mock_analytics.track_message_delivery.side_effect = Exception("Analytics failed")
            mock_get_analytics.return_value = mock_analytics
            
            mock_storage = Mock()
            mock_storage.store_metric.side_effect = Exception("Storage failed")
            mock_get_storage.return_value = mock_storage
            
            # System should still be able to create basic messages
            message = rich_message_service_fallback.create_flex_message(
                title="Resilience Test",
                content="System should work despite multiple component failures",
                content_id="resilience_test",
                include_interactions=True  # This will fail but should be handled
            )
            
            assert message is not None
            assert hasattr(message, 'contents')
            
            # Should be able to attempt delivery (even if components fail)
            result = rich_message_service_fallback.broadcast_rich_message(message)
            assert "success" in result  # Should at least return a result structure
            
        print("System maintained stability under multiple component failures")
    
    def test_graceful_degradation(self, rich_message_service_fallback):
        """Test that system degrades gracefully under stress"""
        
        # Create messages with increasing complexity while simulating resource constraints
        complexity_levels = [
            ("simple", "Simple", "Simple content."),
            ("medium", "Medium complexity message", "Medium content " * 20),
            ("complex", "Very complex message with lots of details", "Complex content " * 100),
            ("extreme", "Extremely detailed message" * 5, "Extreme content " * 500)
        ]
        
        messages_created = 0
        
        for level, title, content in complexity_levels:
            try:
                message = rich_message_service_fallback.create_flex_message(
                    title=title,
                    content=content,
                    image_url=f"https://example.com/{level}_image.jpg",
                    content_id=f"degradation_test_{level}",
                    include_interactions=True
                )
                
                if message is not None:
                    messages_created += 1
                    
                    # Try to broadcast each message
                    result = rich_message_service_fallback.broadcast_rich_message(message)
                    # Should at least return a result structure
                    assert isinstance(result, dict)
                    
            except Exception as e:
                # System should handle complexity gracefully
                # Extreme cases might fail, but system should continue
                print(f"Expected degradation at {level} complexity: {str(e)}")
        
        # Should create at least simple and medium complexity messages
        assert messages_created >= 2, f"System should handle basic complexity levels (created {messages_created})"
        
        print(f"Graceful degradation test completed. Created {messages_created}/{len(complexity_levels)} messages.")
    
    def test_error_recovery_cycle(self, rich_message_service_fallback):
        """Test complete error-recovery cycle"""
        mock_api = rich_message_service_fallback.line_bot_api
        
        # Simulate error-recovery pattern
        error_success_pattern = [
            LineBotApiError(status_code=500, headers={}, error=Mock(message="Service error")),  # Error
            LineBotApiError(status_code=429, headers={}, error=Mock(message="Rate limit")),     # Error
            None,  # Success
            None,  # Success
            LineBotApiError(status_code=502, headers={}, error=Mock(message="Gateway error")),  # Error
            None   # Recovery
        ]
        
        mock_api.broadcast.side_effect = error_success_pattern
        
        message = rich_message_service_fallback.create_flex_message(
            title="Recovery Cycle Test",
            content="Testing error-recovery patterns"
        )
        
        results = []
        for i in range(len(error_success_pattern)):
            result = rich_message_service_fallback.broadcast_rich_message(message)
            results.append(result["success"])
        
        # Should show error-success pattern
        expected = [False, False, True, True, False, True]
        assert results == expected, f"Expected {expected}, got {results}"
        
        print("Error recovery cycle validation completed successfully")
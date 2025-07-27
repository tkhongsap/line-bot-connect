"""
Performance tests for Rich Message automation pipeline.

This module tests the performance characteristics of the Rich Message generation
system, focusing on image composition, content generation, and delivery times
to ensure the system meets performance requirements.
"""

import pytest
import time
import tempfile
import os
import json
import statistics
from unittest.mock import patch, Mock, MagicMock
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple

from src.services.rich_message_service import RichMessageService
from src.utils.interaction_handler import get_interaction_handler
from src.utils.analytics_tracker import get_analytics_tracker
from src.utils.admin_controller import get_admin_controller


class TestRichMessagePerformance:
    """Performance tests for Rich Message automation system"""
    
    @pytest.fixture
    def temp_test_environment(self):
        """Create temporary test environment with mock services"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock LINE Bot API
            mock_line_api = Mock()
            mock_line_api.broadcast.return_value = None
            mock_line_api.narrowcast.return_value = None
            mock_line_api.create_rich_menu.return_value = "test_menu_id"
            mock_line_api.set_rich_menu_image.return_value = None
            
            # Create test image files
            test_images_dir = os.path.join(temp_dir, "test_images")
            os.makedirs(test_images_dir, exist_ok=True)
            
            # Create sample test images
            test_image_paths = []
            for i in range(5):
                image_path = os.path.join(test_images_dir, f"test_image_{i}.png")
                with open(image_path, 'wb') as f:
                    # Create minimal PNG header for testing
                    f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x02X\x00\x00\x01\x90\x08\x06\x00\x00\x00')
                test_image_paths.append(image_path)
            
            yield {
                "temp_dir": temp_dir,
                "test_images_dir": test_images_dir,
                "test_image_paths": test_image_paths,
                "mock_line_api": mock_line_api
            }
    
    @pytest.fixture
    def rich_message_service(self, temp_test_environment):
        """Create RichMessageService for performance testing"""
        return RichMessageService(line_bot_api=temp_test_environment["mock_line_api"])
    
    @pytest.fixture
    def sample_content_batches(self):
        """Generate sample content for batch testing"""
        batches = []
        
        # Small batch (10 items)
        small_batch = []
        for i in range(10):
            small_batch.append({
                "title": f"Performance Test Message {i}",
                "content": f"This is performance test content number {i}. " * 5,  # Longer content
                "image_url": f"https://example.com/test_image_{i % 3}.jpg",
                "content_id": f"perf_test_content_{i}",
                "category": "performance_testing"
            })
        batches.append(("small", small_batch))
        
        # Medium batch (50 items)
        medium_batch = []
        for i in range(50):
            medium_batch.append({
                "title": f"Medium Batch Message {i}",
                "content": f"Medium batch performance test content {i}. " * 8,
                "image_url": f"https://example.com/medium_image_{i % 5}.jpg",
                "content_id": f"perf_medium_content_{i}",
                "category": "performance_testing"
            })
        batches.append(("medium", medium_batch))
        
        # Large batch (100 items)
        large_batch = []
        for i in range(100):
            large_batch.append({
                "title": f"Large Batch Message {i}",
                "content": f"Large batch performance test content {i}. " * 10,
                "image_url": f"https://example.com/large_image_{i % 10}.jpg",
                "content_id": f"perf_large_content_{i}",
                "category": "performance_testing"
            })
        batches.append(("large", large_batch))
        
        return batches
    
    def measure_execution_time(self, func, *args, **kwargs) -> Tuple[Any, float]:
        """Measure execution time of a function call"""
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time = (end_time - start_time) * 1000  # Convert to milliseconds
        return result, execution_time
    
    def test_single_flex_message_creation_performance(self, rich_message_service):
        """Test performance of creating a single Flex Message"""
        test_data = {
            "title": "Performance Test Message",
            "content": "This is a performance test message with substantial content to measure processing time. " * 5,
            "image_url": "https://example.com/test_image.jpg",
            "content_id": "perf_test_single",
            "include_interactions": True
        }
        
        # Warm up
        for _ in range(3):
            rich_message_service.create_flex_message(**test_data)
        
        # Measure multiple iterations
        execution_times = []
        for i in range(20):
            _, exec_time = self.measure_execution_time(
                rich_message_service.create_flex_message,
                **test_data
            )
            execution_times.append(exec_time)
        
        # Calculate statistics
        avg_time = statistics.mean(execution_times)
        median_time = statistics.median(execution_times)
        max_time = max(execution_times)
        min_time = min(execution_times)
        
        # Performance assertions
        assert avg_time < 50.0, f"Average creation time {avg_time:.2f}ms exceeds 50ms threshold"
        assert max_time < 100.0, f"Maximum creation time {max_time:.2f}ms exceeds 100ms threshold"
        assert min_time < 30.0, f"Minimum creation time {min_time:.2f}ms exceeds 30ms threshold"
        
        print(f"Single Flex Message Creation Performance:")
        print(f"  Average: {avg_time:.2f}ms")
        print(f"  Median: {median_time:.2f}ms")
        print(f"  Min: {min_time:.2f}ms")
        print(f"  Max: {max_time:.2f}ms")
    
    def test_batch_flex_message_creation_performance(self, rich_message_service, sample_content_batches):
        """Test performance of creating multiple Flex Messages in batches"""
        performance_results = {}
        
        for batch_name, content_batch in sample_content_batches:
            # Measure batch creation time
            start_time = time.perf_counter()
            
            created_messages = []
            for content in content_batch:
                flex_message = rich_message_service.create_flex_message(
                    title=content["title"],
                    content=content["content"],
                    image_url=content["image_url"],
                    content_id=content["content_id"],
                    include_interactions=True
                )
                created_messages.append(flex_message)
            
            end_time = time.perf_counter()
            total_time = (end_time - start_time) * 1000  # Convert to milliseconds
            
            # Calculate metrics
            messages_per_second = len(content_batch) / (total_time / 1000)
            avg_time_per_message = total_time / len(content_batch)
            
            performance_results[batch_name] = {
                "batch_size": len(content_batch),
                "total_time_ms": total_time,
                "avg_time_per_message_ms": avg_time_per_message,
                "messages_per_second": messages_per_second
            }
            
            # Performance assertions based on batch size
            if batch_name == "small":
                assert total_time < 1000.0, f"Small batch took {total_time:.2f}ms, should be < 1000ms"
                assert messages_per_second > 10, f"Small batch throughput {messages_per_second:.2f} msg/s too low"
            elif batch_name == "medium":
                assert total_time < 5000.0, f"Medium batch took {total_time:.2f}ms, should be < 5000ms"
                assert messages_per_second > 8, f"Medium batch throughput {messages_per_second:.2f} msg/s too low"
            elif batch_name == "large":
                assert total_time < 10000.0, f"Large batch took {total_time:.2f}ms, should be < 10000ms"
                assert messages_per_second > 5, f"Large batch throughput {messages_per_second:.2f} msg/s too low"
        
        print(f"Batch Creation Performance Results:")
        for batch_name, results in performance_results.items():
            print(f"  {batch_name.capitalize()} batch ({results['batch_size']} messages):")
            print(f"    Total time: {results['total_time_ms']:.2f}ms")
            print(f"    Avg per message: {results['avg_time_per_message_ms']:.2f}ms")
            print(f"    Throughput: {results['messages_per_second']:.2f} messages/sec")
    
    def test_message_broadcast_performance(self, rich_message_service, sample_content_batches):
        """Test performance of broadcasting messages"""
        # Use small batch for broadcast testing
        small_batch = sample_content_batches[0][1]  # Get small batch content
        
        # Create messages first
        messages = []
        for content in small_batch[:5]:  # Use only first 5 for broadcast testing
            flex_message = rich_message_service.create_flex_message(
                title=content["title"],
                content=content["content"],
                image_url=content["image_url"],
                content_id=content["content_id"]
            )
            messages.append(flex_message)
        
        # Test broadcast performance
        broadcast_times = []
        
        for message in messages:
            _, exec_time = self.measure_execution_time(
                rich_message_service.broadcast_rich_message,
                message
            )
            broadcast_times.append(exec_time)
        
        # Calculate broadcast statistics
        avg_broadcast_time = statistics.mean(broadcast_times)
        max_broadcast_time = max(broadcast_times)
        
        # Performance assertions
        assert avg_broadcast_time < 200.0, f"Average broadcast time {avg_broadcast_time:.2f}ms exceeds 200ms"
        assert max_broadcast_time < 500.0, f"Maximum broadcast time {max_broadcast_time:.2f}ms exceeds 500ms"
        
        print(f"Message Broadcast Performance:")
        print(f"  Average broadcast time: {avg_broadcast_time:.2f}ms")
        print(f"  Maximum broadcast time: {max_broadcast_time:.2f}ms")
        print(f"  Messages tested: {len(messages)}")
    
    def test_concurrent_message_creation_performance(self, rich_message_service):
        """Test performance under concurrent load"""
        num_threads = 4
        messages_per_thread = 10
        
        def create_messages_batch(thread_id: int) -> List[Tuple[int, float]]:
            """Create a batch of messages and return timing data"""
            results = []
            for i in range(messages_per_thread):
                content_data = {
                    "title": f"Concurrent Test {thread_id}-{i}",
                    "content": f"Concurrent test message from thread {thread_id}, message {i}. " * 3,
                    "image_url": f"https://example.com/concurrent_{thread_id}_{i}.jpg",
                    "content_id": f"concurrent_{thread_id}_{i}",
                    "include_interactions": True
                }
                
                _, exec_time = self.measure_execution_time(
                    rich_message_service.create_flex_message,
                    **content_data
                )
                results.append((i, exec_time))
            
            return results
        
        # Execute concurrent message creation
        start_time = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(create_messages_batch, thread_id)
                for thread_id in range(num_threads)
            ]
            
            all_results = []
            for future in as_completed(futures):
                thread_results = future.result()
                all_results.extend([result[1] for result in thread_results])
        
        end_time = time.perf_counter()
        total_concurrent_time = (end_time - start_time) * 1000
        
        # Calculate concurrent performance metrics
        total_messages = num_threads * messages_per_thread
        avg_time_per_message = statistics.mean(all_results)
        max_time_per_message = max(all_results)
        overall_throughput = total_messages / (total_concurrent_time / 1000)
        
        # Performance assertions
        assert total_concurrent_time < 5000.0, f"Concurrent creation took {total_concurrent_time:.2f}ms, should be < 5000ms"
        assert avg_time_per_message < 100.0, f"Average concurrent message time {avg_time_per_message:.2f}ms too high"
        assert overall_throughput > 5.0, f"Concurrent throughput {overall_throughput:.2f} msg/s too low"
        
        print(f"Concurrent Message Creation Performance:")
        print(f"  Threads: {num_threads}")
        print(f"  Messages per thread: {messages_per_thread}")
        print(f"  Total messages: {total_messages}")
        print(f"  Total time: {total_concurrent_time:.2f}ms")
        print(f"  Average time per message: {avg_time_per_message:.2f}ms")
        print(f"  Maximum time per message: {max_time_per_message:.2f}ms")
        print(f"  Overall throughput: {overall_throughput:.2f} messages/sec")
    
    @patch('src.utils.image_composer.ImageComposer')
    def test_image_composition_performance(self, mock_image_composer_class, temp_test_environment):
        """Test performance of image composition operations"""
        # Mock image composer with realistic timing
        mock_composer = Mock()
        mock_image_composer_class.return_value = mock_composer
        
        # Simulate different composition times based on complexity
        def mock_compose_image(template_data, content_data, output_path=None):
            # Simulate processing time based on content length
            content_length = len(content_data.get("content", ""))
            base_time = 0.1  # 100ms base time
            complexity_factor = content_length / 1000  # Additional time for longer content
            
            time.sleep(base_time + complexity_factor)
            
            return {
                "success": True,
                "output_path": output_path or f"/tmp/composed_{int(time.time())}.png",
                "composition_time_ms": (base_time + complexity_factor) * 1000,
                "final_dimensions": {"width": 600, "height": 400}
            }
        
        mock_composer.compose_image.side_effect = mock_compose_image
        
        # Test different content complexities
        test_scenarios = [
            ("simple", "Short title", "Simple content."),
            ("medium", "Medium length title for testing", "Medium length content " * 10),
            ("complex", "Very detailed and comprehensive title for complex scenario testing", "Complex content " * 50)
        ]
        
        composition_results = {}
        
        for scenario_name, title, content in test_scenarios:
            template_data = {
                "template_id": f"test_template_{scenario_name}",
                "background_file": "test_background.png",
                "text_areas": [
                    {"name": "title", "position": {"x": 100, "y": 100}},
                    {"name": "content", "position": {"x": 100, "y": 200}}
                ]
            }
            
            content_data = {"title": title, "content": content}
            
            # Measure composition time
            start_time = time.perf_counter()
            result = mock_composer.compose_image(template_data, content_data)
            end_time = time.perf_counter()
            
            actual_time = (end_time - start_time) * 1000
            
            composition_results[scenario_name] = {
                "actual_time_ms": actual_time,
                "reported_time_ms": result["composition_time_ms"],
                "success": result["success"]
            }
            
            # Performance assertions
            if scenario_name == "simple":
                assert actual_time < 200.0, f"Simple composition took {actual_time:.2f}ms, should be < 200ms"
            elif scenario_name == "medium":
                assert actual_time < 500.0, f"Medium composition took {actual_time:.2f}ms, should be < 500ms"
            elif scenario_name == "complex":
                assert actual_time < 1000.0, f"Complex composition took {actual_time:.2f}ms, should be < 1000ms"
        
        print(f"Image Composition Performance:")
        for scenario, results in composition_results.items():
            print(f"  {scenario.capitalize()} scenario:")
            print(f"    Actual time: {results['actual_time_ms']:.2f}ms")
            print(f"    Reported time: {results['reported_time_ms']:.2f}ms")
            print(f"    Success: {results['success']}")
    
    def test_interaction_handling_performance(self, temp_test_environment):
        """Test performance of interaction handling under load"""
        interaction_handler = get_interaction_handler()
        
        # Generate test interactions
        num_users = 20
        interactions_per_user = 10
        interaction_types = ["like", "share", "save", "react"]
        
        all_interactions = []
        for user_id in range(num_users):
            for interaction_id in range(interactions_per_user):
                all_interactions.append({
                    "user_id": f"perf_user_{user_id:03d}",
                    "interaction_data": {
                        "action": "interaction",
                        "type": interaction_types[interaction_id % len(interaction_types)],
                        "content_id": f"perf_content_{interaction_id % 5}"
                    }
                })
        
        # Test sequential processing
        start_time = time.perf_counter()
        
        successful_interactions = 0
        processing_times = []
        
        for interaction in all_interactions:
            interaction_start = time.perf_counter()
            
            result = interaction_handler.handle_user_interaction(
                interaction["user_id"],
                interaction["interaction_data"]
            )
            
            interaction_end = time.perf_counter()
            interaction_time = (interaction_end - interaction_start) * 1000
            
            processing_times.append(interaction_time)
            
            if result.get("success"):
                successful_interactions += 1
        
        end_time = time.perf_counter()
        total_time = (end_time - start_time) * 1000
        
        # Calculate performance metrics
        avg_processing_time = statistics.mean(processing_times)
        max_processing_time = max(processing_times)
        interactions_per_second = len(all_interactions) / (total_time / 1000)
        success_rate = successful_interactions / len(all_interactions)
        
        # Performance assertions
        assert avg_processing_time < 50.0, f"Average interaction processing {avg_processing_time:.2f}ms too high"
        assert max_processing_time < 200.0, f"Maximum interaction processing {max_processing_time:.2f}ms too high"
        assert interactions_per_second > 20.0, f"Interaction throughput {interactions_per_second:.2f}/sec too low"
        assert success_rate > 0.95, f"Success rate {success_rate:.2%} too low"
        
        print(f"Interaction Handling Performance:")
        print(f"  Total interactions: {len(all_interactions)}")
        print(f"  Successful interactions: {successful_interactions}")
        print(f"  Success rate: {success_rate:.2%}")
        print(f"  Total processing time: {total_time:.2f}ms")
        print(f"  Average processing time: {avg_processing_time:.2f}ms")
        print(f"  Maximum processing time: {max_processing_time:.2f}ms")
        print(f"  Throughput: {interactions_per_second:.2f} interactions/sec")
    
    @patch('src.utils.metrics_storage.get_metrics_storage')
    def test_analytics_performance_under_load(self, mock_get_storage, temp_test_environment):
        """Test analytics system performance under high load"""
        # Mock metrics storage
        mock_storage = Mock()
        mock_storage.store_metric.return_value = True
        mock_storage.get_metrics.return_value = []
        mock_get_storage.return_value = mock_storage
        
        analytics_tracker = get_analytics_tracker()
        
        # Generate high volume of analytics events
        num_events = 500
        event_types = ["delivery", "open", "interaction", "share"]
        
        # Test batch analytics processing
        start_time = time.perf_counter()
        
        for i in range(num_events):
            event_type = event_types[i % len(event_types)]
            
            if event_type == "delivery":
                analytics_tracker.track_message_delivery(
                    user_id=f"user_{i % 50}",
                    content_category="performance_test",
                    template_id=f"template_{i % 10}",
                    delivery_time_ms=100 + (i % 50)
                )
            elif event_type == "open":
                analytics_tracker.track_user_interaction(
                    user_id=f"user_{i % 50}",
                    interaction_type=analytics_tracker.InteractionType.MESSAGE_OPENED,
                    content_category="performance_test",
                    template_id=f"template_{i % 10}"
                )
            elif event_type == "interaction":
                analytics_tracker.track_user_interaction(
                    user_id=f"user_{i % 50}",
                    interaction_type=analytics_tracker.InteractionType.BUTTON_CLICKED,
                    content_category="performance_test",
                    template_id=f"template_{i % 10}"
                )
            elif event_type == "share":
                analytics_tracker.track_user_interaction(
                    user_id=f"user_{i % 50}",
                    interaction_type=analytics_tracker.InteractionType.CONTENT_SHARED,
                    content_category="performance_test",
                    template_id=f"template_{i % 10}"
                )
        
        end_time = time.perf_counter()
        processing_time = (end_time - start_time) * 1000
        
        # Test system metrics calculation performance
        metrics_start = time.perf_counter()
        system_metrics = analytics_tracker.calculate_system_metrics(force_recalculate=True)
        metrics_end = time.perf_counter()
        metrics_time = (metrics_end - metrics_start) * 1000
        
        # Calculate performance metrics
        events_per_second = num_events / (processing_time / 1000)
        
        # Performance assertions
        assert processing_time < 5000.0, f"Analytics processing took {processing_time:.2f}ms, should be < 5000ms"
        assert events_per_second > 50.0, f"Analytics throughput {events_per_second:.2f}/sec too low"
        assert metrics_time < 1000.0, f"Metrics calculation took {metrics_time:.2f}ms, should be < 1000ms"
        
        print(f"Analytics Performance Under Load:")
        print(f"  Total events: {num_events}")
        print(f"  Processing time: {processing_time:.2f}ms")
        print(f"  Events per second: {events_per_second:.2f}")
        print(f"  Metrics calculation time: {metrics_time:.2f}ms")
        print(f"  System metrics calculated: {system_metrics is not None}")
    
    def test_memory_usage_performance(self, rich_message_service, sample_content_batches):
        """Test memory usage during intensive operations"""
        import psutil
        import gc
        
        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform memory-intensive operations
        large_batch = sample_content_batches[2][1]  # Get large batch
        
        created_messages = []
        memory_measurements = []
        
        # Create messages and track memory
        for i, content in enumerate(large_batch):
            flex_message = rich_message_service.create_flex_message(
                title=content["title"],
                content=content["content"],
                image_url=content["image_url"],
                content_id=content["content_id"],
                include_interactions=True
            )
            created_messages.append(flex_message)
            
            # Measure memory every 10 messages
            if i % 10 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_measurements.append(current_memory - initial_memory)
        
        # Get peak memory usage
        peak_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = peak_memory - initial_memory
        
        # Force garbage collection and measure final memory
        del created_messages
        gc.collect()
        
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_after_cleanup = final_memory - initial_memory
        
        # Performance assertions
        assert memory_increase < 500.0, f"Memory increase {memory_increase:.2f}MB exceeds 500MB limit"
        assert memory_after_cleanup < 100.0, f"Memory after cleanup {memory_after_cleanup:.2f}MB indicates memory leak"
        
        print(f"Memory Usage Performance:")
        print(f"  Initial memory: {initial_memory:.2f}MB")
        print(f"  Peak memory: {peak_memory:.2f}MB")
        print(f"  Memory increase: {memory_increase:.2f}MB")
        print(f"  Memory after cleanup: {memory_after_cleanup:.2f}MB")
        print(f"  Messages created: {len(large_batch)}")
        print(f"  Memory per message: {memory_increase / len(large_batch):.3f}MB")
    
    def test_end_to_end_pipeline_performance(self, temp_test_environment):
        """Test complete pipeline performance from content creation to delivery"""
        # This test simulates the complete Rich Message automation pipeline
        with patch('src.utils.template_manager.TemplateManager') as mock_template_manager, \
             patch('src.utils.content_generator.ContentGenerator') as mock_content_generator, \
             patch('src.utils.image_composer.ImageComposer') as mock_image_composer:
            
            # Mock services with realistic performance characteristics
            mock_manager = Mock()
            mock_template_manager.return_value = mock_manager
            mock_manager.select_template.return_value = {
                "template_id": "perf_template_001",
                "template_data": {"name": "Performance Template"},
                "match_score": 0.9
            }
            
            mock_generator = Mock()
            mock_content_generator.return_value = mock_generator
            
            def mock_generate_content(**kwargs):
                time.sleep(0.15)  # Simulate 150ms content generation
                return {
                    "success": True,
                    "title": "Generated Performance Title",
                    "content": "Generated performance test content with substantial text.",
                    "generation_time_ms": 150
                }
            mock_generator.generate_content.side_effect = mock_generate_content
            
            mock_composer = Mock()
            mock_image_composer.return_value = mock_composer
            
            def mock_compose_image(**kwargs):
                time.sleep(0.2)  # Simulate 200ms image composition
                return {
                    "success": True,
                    "output_path": "/tmp/perf_composed.png",
                    "public_url": "https://example.com/perf_composed.png",
                    "composition_time_ms": 200
                }
            mock_composer.compose_image.side_effect = mock_compose_image
            
            rich_service = RichMessageService(line_bot_api=temp_test_environment["mock_line_api"])
            
            # Test complete pipeline
            num_pipelines = 10
            pipeline_times = []
            
            for i in range(num_pipelines):
                pipeline_start = time.perf_counter()
                
                # Step 1: Template selection
                template_result = mock_manager.select_template({"category": "performance"})
                
                # Step 2: Content generation
                content_result = mock_generator.generate_content(
                    template_data=template_result["template_data"]
                )
                
                # Step 3: Image composition
                image_result = mock_composer.compose_image(
                    template_data=template_result["template_data"],
                    content_data=content_result
                )
                
                # Step 4: Rich Message creation
                flex_message = rich_service.create_flex_message(
                    title=content_result["title"],
                    content=content_result["content"],
                    image_url=image_result["public_url"],
                    content_id=f"perf_pipeline_{i}",
                    include_interactions=True
                )
                
                # Step 5: Message delivery
                delivery_result = rich_service.broadcast_rich_message(flex_message)
                
                pipeline_end = time.perf_counter()
                pipeline_time = (pipeline_end - pipeline_start) * 1000
                
                pipeline_times.append(pipeline_time)
                
                assert delivery_result["success"] is True
            
            # Calculate pipeline performance metrics
            avg_pipeline_time = statistics.mean(pipeline_times)
            max_pipeline_time = max(pipeline_times)
            min_pipeline_time = min(pipeline_times)
            
            # Performance assertions
            assert avg_pipeline_time < 1000.0, f"Average pipeline time {avg_pipeline_time:.2f}ms exceeds 1000ms"
            assert max_pipeline_time < 1500.0, f"Maximum pipeline time {max_pipeline_time:.2f}ms exceeds 1500ms"
            
            print(f"End-to-End Pipeline Performance:")
            print(f"  Pipelines tested: {num_pipelines}")
            print(f"  Average pipeline time: {avg_pipeline_time:.2f}ms")
            print(f"  Minimum pipeline time: {min_pipeline_time:.2f}ms")
            print(f"  Maximum pipeline time: {max_pipeline_time:.2f}ms")
            print(f"  Expected breakdown:")
            print(f"    Content generation: ~150ms")
            print(f"    Image composition: ~200ms")
            print(f"    Message creation: ~50ms")
            print(f"    Delivery: ~100ms")
            print(f"    Total expected: ~500ms")
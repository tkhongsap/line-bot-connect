"""
Unit tests for Engagement Metrics Storage System
"""

import pytest
import tempfile
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, Mock
import json

from src.utils.metrics_storage import (
    EngagementMetricsStorage, EngagementMetric, AggregatedMetrics,
    get_metrics_storage
)


class TestEngagementMetricsStorage:
    """Test cases for EngagementMetricsStorage"""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create a temporary database file for testing"""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as temp_file:
            temp_path = temp_file.name
        yield temp_path
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def metrics_storage(self, temp_db_path):
        """Create EngagementMetricsStorage instance with temporary database"""
        return EngagementMetricsStorage(db_path=temp_db_path)
    
    @pytest.fixture
    def sample_metric(self):
        """Create a sample engagement metric"""
        return EngagementMetric(
            metric_id="metric_001",
            user_id="user_123",
            content_id="content_456",
            interaction_type="like",
            timestamp=datetime.now(timezone.utc),
            response_time_ms=150,
            session_duration_ms=30000,
            engagement_score=0.8,
            content_category="motivation",
            template_id="template_001",
            user_timezone="Asia/Bangkok",
            platform="line_bot",
            metadata={"button_clicked": "like", "source": "rich_message"}
        )
    
    def test_initialization(self, metrics_storage, temp_db_path):
        """Test EngagementMetricsStorage initialization"""
        assert metrics_storage.db_path == temp_db_path
        assert metrics_storage.metric_retention_days == 90
        assert metrics_storage.aggregation_batch_size == 1000
        assert os.path.exists(temp_db_path)
        
        # Test database tables were created
        import sqlite3
        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.cursor()
            
            # Check engagement_metrics table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='engagement_metrics'"
            )
            assert cursor.fetchone() is not None
            
            # Check aggregated_metrics table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='aggregated_metrics'"
            )
            assert cursor.fetchone() is not None
    
    def test_store_metric_success(self, metrics_storage, sample_metric):
        """Test storing a single engagement metric"""
        result = metrics_storage.store_metric(sample_metric)
        
        assert result is True
        
        # Verify metric was stored
        retrieved_metrics = metrics_storage.get_metrics(
            user_id=sample_metric.user_id,
            limit=1
        )
        
        assert len(retrieved_metrics) == 1
        retrieved = retrieved_metrics[0]
        assert retrieved.metric_id == sample_metric.metric_id
        assert retrieved.user_id == sample_metric.user_id
        assert retrieved.content_id == sample_metric.content_id
        assert retrieved.interaction_type == sample_metric.interaction_type
        assert retrieved.response_time_ms == sample_metric.response_time_ms
        assert retrieved.content_category == sample_metric.content_category
        assert retrieved.metadata == sample_metric.metadata
    
    def test_store_metrics_batch_success(self, metrics_storage):
        """Test storing multiple metrics in a batch"""
        metrics = []
        for i in range(5):
            metric = EngagementMetric(
                metric_id=f"metric_{i:03d}",
                user_id=f"user_{i}",
                content_id=f"content_{i}",
                interaction_type="like" if i % 2 == 0 else "share",
                timestamp=datetime.now(timezone.utc) - timedelta(minutes=i)
            )
            metrics.append(metric)
        
        stored_count = metrics_storage.store_metrics_batch(metrics)
        
        assert stored_count == 5
        
        # Verify all metrics were stored
        retrieved_metrics = metrics_storage.get_metrics()
        assert len(retrieved_metrics) == 5
    
    def test_store_metrics_batch_empty(self, metrics_storage):
        """Test storing empty batch"""
        stored_count = metrics_storage.store_metrics_batch([])
        assert stored_count == 0
    
    def test_get_metrics_no_filters(self, metrics_storage):
        """Test retrieving metrics without filters"""
        # Store sample metrics
        metrics = []
        for i in range(3):
            metric = EngagementMetric(
                metric_id=f"metric_{i}",
                user_id=f"user_{i}",
                content_id=f"content_{i}",
                interaction_type="like",
                timestamp=datetime.now(timezone.utc) - timedelta(hours=i)
            )
            metrics.append(metric)
        
        metrics_storage.store_metrics_batch(metrics)
        
        retrieved = metrics_storage.get_metrics()
        
        assert len(retrieved) == 3
        # Should be ordered by timestamp DESC (newest first)
        assert retrieved[0].metric_id == "metric_0"
        assert retrieved[1].metric_id == "metric_1"
        assert retrieved[2].metric_id == "metric_2"
    
    def test_get_metrics_with_filters(self, metrics_storage):
        """Test retrieving metrics with various filters"""
        # Store sample metrics
        now = datetime.now(timezone.utc)
        metrics = [
            EngagementMetric("metric_1", "user_a", "content_1", "like", now - timedelta(hours=1)),
            EngagementMetric("metric_2", "user_b", "content_2", "share", now - timedelta(hours=2)),
            EngagementMetric("metric_3", "user_a", "content_3", "save", now - timedelta(hours=3)),
        ]
        metrics_storage.store_metrics_batch(metrics)
        
        # Test user filter
        user_a_metrics = metrics_storage.get_metrics(user_id="user_a")
        assert len(user_a_metrics) == 2
        
        # Test content filter
        content_1_metrics = metrics_storage.get_metrics(content_id="content_1")
        assert len(content_1_metrics) == 1
        
        # Test interaction type filter
        like_metrics = metrics_storage.get_metrics(interaction_type="like")
        assert len(like_metrics) == 1
        
        # Test date range filter
        start_date = now - timedelta(hours=2.5)
        end_date = now
        recent_metrics = metrics_storage.get_metrics(
            start_date=start_date, 
            end_date=end_date
        )
        assert len(recent_metrics) == 2
        
        # Test limit
        limited_metrics = metrics_storage.get_metrics(limit=2)
        assert len(limited_metrics) == 2
    
    def test_calculate_aggregated_metrics_empty(self, metrics_storage):
        """Test calculating aggregated metrics with no data"""
        start_date = datetime.now(timezone.utc) - timedelta(days=1)
        end_date = datetime.now(timezone.utc)
        
        aggregated = metrics_storage.calculate_aggregated_metrics(
            time_period="daily",
            start_date=start_date,
            end_date=end_date
        )
        
        assert aggregated is not None
        assert aggregated.time_period == "daily"
        assert aggregated.period_start == start_date
        assert aggregated.period_end == end_date
        assert aggregated.total_interactions == 0
        assert aggregated.unique_users == 0
    
    def test_calculate_aggregated_metrics_with_data(self, metrics_storage):
        """Test calculating aggregated metrics with sample data"""
        # Create sample data
        now = datetime.now(timezone.utc)
        metrics = [
            EngagementMetric("m1", "user1", "content1", "like", now, response_time_ms=100),
            EngagementMetric("m2", "user2", "content1", "like", now, response_time_ms=200),
            EngagementMetric("m3", "user1", "content2", "share", now, response_time_ms=150),
            EngagementMetric("m4", "user3", "content1", "save", now, response_time_ms=180),
            EngagementMetric("m5", "user2", "content2", "react", now, response_time_ms=120),
        ]
        metrics_storage.store_metrics_batch(metrics)
        
        start_date = now - timedelta(hours=1)
        end_date = now + timedelta(hours=1)
        
        aggregated = metrics_storage.calculate_aggregated_metrics(
            time_period="hourly",
            start_date=start_date,
            end_date=end_date
        )
        
        assert aggregated is not None
        assert aggregated.total_interactions == 5
        assert aggregated.unique_users == 3
        assert aggregated.like_rate == 0.4  # 2 likes out of 5 interactions
        assert aggregated.share_rate == 0.2  # 1 share out of 5 interactions
        assert aggregated.save_rate == 0.2   # 1 save out of 5 interactions
        assert aggregated.reaction_rate == 0.2  # 1 react out of 5 interactions
        assert aggregated.avg_response_time_ms == 150.0  # (100+200+150+180+120)/5
    
    def test_store_aggregated_metrics(self, metrics_storage):
        """Test storing aggregated metrics"""
        start_date = datetime.now(timezone.utc) - timedelta(days=1)
        end_date = datetime.now(timezone.utc)
        
        aggregated = AggregatedMetrics(
            time_period="daily",
            period_start=start_date,
            period_end=end_date,
            total_interactions=100,
            unique_users=50,
            like_rate=0.3,
            share_rate=0.1,
            save_rate=0.2,
            reaction_rate=0.15
        )
        
        result = metrics_storage.store_aggregated_metrics(aggregated)
        assert result is True
        
        # Verify storage by checking database directly
        import sqlite3
        with sqlite3.connect(metrics_storage.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM aggregated_metrics WHERE time_period = ? AND period_start = ?",
                ("daily", start_date.isoformat())
            )
            row = cursor.fetchone()
            assert row is not None
            
            # Parse stored data
            stored_data = json.loads(row[3])  # metrics_data column
            assert stored_data["total_interactions"] == 100
            assert stored_data["unique_users"] == 50
    
    def test_cleanup_old_metrics(self, metrics_storage):
        """Test cleaning up old metrics"""
        now = datetime.now(timezone.utc)
        
        # Create old and new metrics
        old_metrics = [
            EngagementMetric("old1", "user1", "content1", "like", now - timedelta(days=100)),
            EngagementMetric("old2", "user2", "content2", "share", now - timedelta(days=50)),
        ]
        
        new_metrics = [
            EngagementMetric("new1", "user3", "content3", "save", now - timedelta(days=10)),
            EngagementMetric("new2", "user4", "content4", "react", now - timedelta(days=5)),
        ]
        
        metrics_storage.store_metrics_batch(old_metrics + new_metrics)
        
        # Cleanup with 30 days retention
        removed_count = metrics_storage.cleanup_old_metrics(days_to_keep=30)
        
        assert removed_count == 2
        
        # Verify only new metrics remain
        remaining_metrics = metrics_storage.get_metrics()
        assert len(remaining_metrics) == 2
        remaining_ids = [m.metric_id for m in remaining_metrics]
        assert "new1" in remaining_ids
        assert "new2" in remaining_ids
        assert "old1" not in remaining_ids
        assert "old2" not in remaining_ids
    
    def test_get_storage_statistics(self, metrics_storage):
        """Test getting storage statistics"""
        # Add some sample data
        metrics = [
            EngagementMetric("m1", "user1", "content1", "like", datetime.now(timezone.utc)),
            EngagementMetric("m2", "user2", "content2", "share", datetime.now(timezone.utc)),
            EngagementMetric("m3", "user1", "content3", "save", datetime.now(timezone.utc)),
        ]
        metrics_storage.store_metrics_batch(metrics)
        
        # Add aggregated metric
        aggregated = AggregatedMetrics(
            time_period="daily",
            period_start=datetime.now(timezone.utc) - timedelta(days=1),
            period_end=datetime.now(timezone.utc)
        )
        metrics_storage.store_aggregated_metrics(aggregated)
        
        stats = metrics_storage.get_storage_statistics()
        
        assert stats["total_metrics"] == 3
        assert stats["aggregated_metrics"] == 1
        assert stats["unique_users"] == 2
        assert stats["unique_content"] == 3
        assert "date_range" in stats
        assert "database_size_bytes" in stats
        assert stats["database_path"] == metrics_storage.db_path
        assert stats["retention_days"] == 90
    
    def test_engagement_metric_dataclass(self):
        """Test EngagementMetric dataclass creation"""
        timestamp = datetime.now(timezone.utc)
        
        metric = EngagementMetric(
            metric_id="test_metric",
            user_id="test_user",
            content_id="test_content",
            interaction_type="like",
            timestamp=timestamp,
            response_time_ms=250,
            session_duration_ms=45000,
            engagement_score=0.75,
            content_category="wellness",
            template_id="template_123",
            user_timezone="Europe/London",
            platform="mobile_app",
            metadata={"source": "push_notification"}
        )
        
        assert metric.metric_id == "test_metric"
        assert metric.user_id == "test_user"
        assert metric.content_id == "test_content"
        assert metric.interaction_type == "like"
        assert metric.timestamp == timestamp
        assert metric.response_time_ms == 250
        assert metric.session_duration_ms == 45000
        assert metric.engagement_score == 0.75
        assert metric.content_category == "wellness"
        assert metric.template_id == "template_123"
        assert metric.user_timezone == "Europe/London"
        assert metric.platform == "mobile_app"
        assert metric.metadata == {"source": "push_notification"}
    
    def test_engagement_metric_post_init(self):
        """Test EngagementMetric __post_init__ method"""
        metric = EngagementMetric(
            metric_id="test",
            user_id="user",
            content_id="content",
            interaction_type="like",
            timestamp=datetime.now(timezone.utc)
        )
        
        # metadata should be initialized to empty dict
        assert metric.metadata == {}
    
    def test_aggregated_metrics_dataclass(self):
        """Test AggregatedMetrics dataclass creation"""
        start_date = datetime.now(timezone.utc) - timedelta(days=1)
        end_date = datetime.now(timezone.utc)
        
        aggregated = AggregatedMetrics(
            time_period="daily",
            period_start=start_date,
            period_end=end_date,
            total_interactions=500,
            unique_users=200,
            total_content_views=450,
            like_rate=0.35,
            share_rate=0.15,
            save_rate=0.20,
            reaction_rate=0.25,
            avg_response_time_ms=175.5,
            avg_session_duration_ms=35000.0,
            avg_engagement_score=0.72,
            top_content_categories=["motivation", "wellness"],
            top_templates=["template_1", "template_2"],
            high_engagement_users=50,
            medium_engagement_users=100,
            low_engagement_users=50
        )
        
        assert aggregated.time_period == "daily"
        assert aggregated.period_start == start_date
        assert aggregated.period_end == end_date
        assert aggregated.total_interactions == 500
        assert aggregated.unique_users == 200
        assert aggregated.like_rate == 0.35
        assert aggregated.top_content_categories == ["motivation", "wellness"]
        assert aggregated.high_engagement_users == 50
    
    def test_aggregated_metrics_post_init(self):
        """Test AggregatedMetrics __post_init__ method"""
        aggregated = AggregatedMetrics(
            time_period="hourly",
            period_start=datetime.now(timezone.utc) - timedelta(hours=1),
            period_end=datetime.now(timezone.utc)
        )
        
        # Lists should be initialized to empty
        assert aggregated.top_content_categories == []
        assert aggregated.top_templates == []
    
    def test_database_error_handling(self, temp_db_path):
        """Test database error handling"""
        # Create storage with invalid database path
        invalid_path = "/invalid/path/database.db"
        
        with pytest.raises(Exception):
            EngagementMetricsStorage(db_path=invalid_path)
    
    def test_metric_storage_error_handling(self, metrics_storage):
        """Test error handling in metric storage"""
        # Create invalid metric (missing required fields)
        invalid_metric = EngagementMetric(
            metric_id="",  # Invalid empty ID
            user_id="user",
            content_id="content",
            interaction_type="like",
            timestamp=datetime.now(timezone.utc)
        )
        
        # Should handle gracefully
        result = metrics_storage.store_metric(invalid_metric)
        # Depending on implementation, this might succeed or fail gracefully
        assert isinstance(result, bool)
    
    def test_concurrent_access(self, metrics_storage):
        """Test thread-safe access to metrics storage"""
        import threading
        import time
        
        results = []
        
        def store_metrics(thread_id):
            for i in range(5):
                metric = EngagementMetric(
                    metric_id=f"thread_{thread_id}_metric_{i}",
                    user_id=f"user_{thread_id}",
                    content_id=f"content_{i}",
                    interaction_type="like",
                    timestamp=datetime.now(timezone.utc)
                )
                result = metrics_storage.store_metric(metric)
                results.append(result)
                time.sleep(0.001)  # Small delay to increase chance of race conditions
        
        # Create multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=store_metrics, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check that all operations succeeded
        assert len(results) == 15  # 3 threads × 5 metrics each
        assert all(results)  # All should be True
        
        # Verify all metrics were stored
        stored_metrics = metrics_storage.get_metrics()
        assert len(stored_metrics) == 15
    
    def test_get_metrics_storage_singleton(self):
        """Test global metrics storage singleton"""
        storage1 = get_metrics_storage()
        storage2 = get_metrics_storage()
        
        assert storage1 is storage2
        assert isinstance(storage1, EngagementMetricsStorage)
    
    @patch('src.utils.metrics_storage.sqlite3.connect')
    def test_database_connection_error(self, mock_connect):
        """Test handling database connection errors"""
        mock_connect.side_effect = Exception("Database connection failed")
        
        with pytest.raises(Exception):
            EngagementMetricsStorage()
    
    def test_large_batch_storage(self, metrics_storage):
        """Test storing large batch of metrics"""
        # Create large batch of metrics
        large_batch = []
        for i in range(1000):
            metric = EngagementMetric(
                metric_id=f"large_batch_metric_{i:04d}",
                user_id=f"user_{i % 100}",  # 100 different users
                content_id=f"content_{i % 50}",  # 50 different content pieces
                interaction_type=["like", "share", "save", "react"][i % 4],
                timestamp=datetime.now(timezone.utc) - timedelta(minutes=i)
            )
            large_batch.append(metric)
        
        stored_count = metrics_storage.store_metrics_batch(large_batch)
        assert stored_count == 1000
        
        # Verify storage
        retrieved_count = len(metrics_storage.get_metrics())
        assert retrieved_count == 1000
        
        # Test aggregation with large dataset
        start_date = datetime.now(timezone.utc) - timedelta(hours=24)
        end_date = datetime.now(timezone.utc)
        
        aggregated = metrics_storage.calculate_aggregated_metrics(
            time_period="daily",
            start_date=start_date,
            end_date=end_date
        )
        
        assert aggregated is not None
        assert aggregated.total_interactions == 1000
        assert aggregated.unique_users == 100
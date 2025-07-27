"""
Engagement Metrics Collection and Storage System.

This module provides persistent storage and retrieval of engagement metrics
for Rich Message interactions, with support for aggregation and reporting.
"""

import logging
import json
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class EngagementMetric:
    """Individual engagement metric record"""
    metric_id: str
    user_id: str
    content_id: str
    interaction_type: str
    timestamp: datetime
    
    # Metric values
    response_time_ms: Optional[int] = None
    session_duration_ms: Optional[int] = None
    engagement_score: Optional[float] = None
    
    # Context data
    content_category: Optional[str] = None
    template_id: Optional[str] = None
    user_timezone: Optional[str] = None
    platform: Optional[str] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class AggregatedMetrics:
    """Aggregated engagement metrics for reporting"""
    time_period: str  # 'hourly', 'daily', 'weekly', 'monthly'
    period_start: datetime
    period_end: datetime
    
    # Counts
    total_interactions: int = 0
    unique_users: int = 0
    total_content_views: int = 0
    
    # Engagement rates
    like_rate: float = 0.0
    share_rate: float = 0.0
    save_rate: float = 0.0
    reaction_rate: float = 0.0
    
    # Performance metrics
    avg_response_time_ms: float = 0.0
    avg_session_duration_ms: float = 0.0
    avg_engagement_score: float = 0.0
    
    # Top content
    top_content_categories: List[str] = None
    top_templates: List[str] = None
    
    # User segments
    high_engagement_users: int = 0
    medium_engagement_users: int = 0
    low_engagement_users: int = 0
    
    def __post_init__(self):
        if self.top_content_categories is None:
            self.top_content_categories = []
        if self.top_templates is None:
            self.top_templates = []


class EngagementMetricsStorage:
    """
    Persistent storage system for engagement metrics with SQLite backend.
    
    Provides thread-safe operations for storing, retrieving, and aggregating
    engagement metrics with automatic cleanup and performance optimization.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize metrics storage.
        
        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        if db_path is None:
            # Create data directory if it doesn't exist
            data_dir = Path("data")
            data_dir.mkdir(exist_ok=True)
            db_path = str(data_dir / "engagement_metrics.db")
        
        self.db_path = db_path
        self.lock = threading.Lock()
        
        # Configuration
        self.metric_retention_days = 90
        self.aggregation_batch_size = 1000
        
        # Initialize database
        self._initialize_database()
        
        logger.info(f"EngagementMetricsStorage initialized with database: {db_path}")
    
    def _initialize_database(self):
        """Initialize SQLite database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create engagement_metrics table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS engagement_metrics (
                        metric_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        content_id TEXT NOT NULL,
                        interaction_type TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        response_time_ms INTEGER,
                        session_duration_ms INTEGER,
                        engagement_score REAL,
                        content_category TEXT,
                        template_id TEXT,
                        user_timezone TEXT,
                        platform TEXT,
                        metadata TEXT,
                        created_at TEXT NOT NULL
                    )
                ''')
                
                # Create aggregated_metrics table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS aggregated_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        time_period TEXT NOT NULL,
                        period_start TEXT NOT NULL,
                        period_end TEXT NOT NULL,
                        metrics_data TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        UNIQUE(time_period, period_start, period_end)
                    )
                ''')
                
                # Create indexes for performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON engagement_metrics(timestamp)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_user_id ON engagement_metrics(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_content_id ON engagement_metrics(content_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_interaction_type ON engagement_metrics(interaction_type)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_aggregated_period ON aggregated_metrics(time_period, period_start)')
                
                conn.commit()
                logger.info("Database tables initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise
    
    def store_metric(self, metric: EngagementMetric) -> bool:
        """
        Store an engagement metric.
        
        Args:
            metric: EngagementMetric object to store
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO engagement_metrics (
                            metric_id, user_id, content_id, interaction_type, timestamp,
                            response_time_ms, session_duration_ms, engagement_score,
                            content_category, template_id, user_timezone, platform,
                            metadata, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        metric.metric_id,
                        metric.user_id,
                        metric.content_id,
                        metric.interaction_type,
                        metric.timestamp.isoformat(),
                        metric.response_time_ms,
                        metric.session_duration_ms,
                        metric.engagement_score,
                        metric.content_category,
                        metric.template_id,
                        metric.user_timezone,
                        metric.platform,
                        json.dumps(metric.metadata) if metric.metadata else None,
                        datetime.now(timezone.utc).isoformat()
                    ))
                    
                    conn.commit()
                    
            logger.debug(f"Stored engagement metric: {metric.metric_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store engagement metric: {str(e)}")
            return False
    
    def store_metrics_batch(self, metrics: List[EngagementMetric]) -> int:
        """
        Store multiple engagement metrics in a batch.
        
        Args:
            metrics: List of EngagementMetric objects
            
        Returns:
            Number of metrics successfully stored
        """
        if not metrics:
            return 0
        
        stored_count = 0
        
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    for metric in metrics:
                        try:
                            cursor.execute('''
                                INSERT OR REPLACE INTO engagement_metrics (
                                    metric_id, user_id, content_id, interaction_type, timestamp,
                                    response_time_ms, session_duration_ms, engagement_score,
                                    content_category, template_id, user_timezone, platform,
                                    metadata, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                metric.metric_id,
                                metric.user_id,
                                metric.content_id,
                                metric.interaction_type,
                                metric.timestamp.isoformat(),
                                metric.response_time_ms,
                                metric.session_duration_ms,
                                metric.engagement_score,
                                metric.content_category,
                                metric.template_id,
                                metric.user_timezone,
                                metric.platform,
                                json.dumps(metric.metadata) if metric.metadata else None,
                                datetime.now(timezone.utc).isoformat()
                            ))
                            stored_count += 1
                            
                        except Exception as e:
                            logger.warning(f"Failed to store individual metric {metric.metric_id}: {str(e)}")
                    
                    conn.commit()
                    
            logger.info(f"Stored {stored_count}/{len(metrics)} engagement metrics in batch")
            return stored_count
            
        except Exception as e:
            logger.error(f"Failed to store metrics batch: {str(e)}")
            return stored_count
    
    def get_metrics(self, 
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None,
                   user_id: Optional[str] = None,
                   content_id: Optional[str] = None,
                   interaction_type: Optional[str] = None,
                   limit: Optional[int] = None) -> List[EngagementMetric]:
        """
        Retrieve engagement metrics with optional filtering.
        
        Args:
            start_date: Filter metrics after this date
            end_date: Filter metrics before this date
            user_id: Filter by specific user
            content_id: Filter by specific content
            interaction_type: Filter by interaction type
            limit: Maximum number of results
            
        Returns:
            List of EngagementMetric objects
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build query with filters
                query = "SELECT * FROM engagement_metrics WHERE 1=1"
                params = []
                
                if start_date:
                    query += " AND timestamp >= ?"
                    params.append(start_date.isoformat())
                
                if end_date:
                    query += " AND timestamp <= ?"
                    params.append(end_date.isoformat())
                
                if user_id:
                    query += " AND user_id = ?"
                    params.append(user_id)
                
                if content_id:
                    query += " AND content_id = ?"
                    params.append(content_id)
                
                if interaction_type:
                    query += " AND interaction_type = ?"
                    params.append(interaction_type)
                
                query += " ORDER BY timestamp DESC"
                
                if limit:
                    query += " LIMIT ?"
                    params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                # Convert rows to EngagementMetric objects
                metrics = []
                for row in rows:
                    metadata = json.loads(row[12]) if row[12] else {}
                    
                    metric = EngagementMetric(
                        metric_id=row[0],
                        user_id=row[1],
                        content_id=row[2],
                        interaction_type=row[3],
                        timestamp=datetime.fromisoformat(row[4]),
                        response_time_ms=row[5],
                        session_duration_ms=row[6],
                        engagement_score=row[7],
                        content_category=row[8],
                        template_id=row[9],
                        user_timezone=row[10],
                        platform=row[11],
                        metadata=metadata
                    )
                    metrics.append(metric)
                
                logger.debug(f"Retrieved {len(metrics)} engagement metrics")
                return metrics
                
        except Exception as e:
            logger.error(f"Failed to retrieve engagement metrics: {str(e)}")
            return []
    
    def calculate_aggregated_metrics(self, 
                                   time_period: str,
                                   start_date: datetime,
                                   end_date: datetime) -> Optional[AggregatedMetrics]:
        """
        Calculate aggregated metrics for a time period.
        
        Args:
            time_period: 'hourly', 'daily', 'weekly', 'monthly'
            start_date: Period start date
            end_date: Period end date
            
        Returns:
            AggregatedMetrics object or None if calculation fails
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get metrics for the period
                cursor.execute('''
                    SELECT interaction_type, user_id, content_category, template_id,
                           response_time_ms, session_duration_ms, engagement_score
                    FROM engagement_metrics
                    WHERE timestamp >= ? AND timestamp <= ?
                ''', (start_date.isoformat(), end_date.isoformat()))
                
                rows = cursor.fetchall()
                
                if not rows:
                    return AggregatedMetrics(
                        time_period=time_period,
                        period_start=start_date,
                        period_end=end_date
                    )
                
                # Calculate metrics
                total_interactions = len(rows)
                unique_users = len(set(row[1] for row in rows))
                
                # Count interaction types
                interaction_counts = {}
                response_times = []
                session_durations = []
                engagement_scores = []
                content_categories = {}
                templates = {}
                
                for row in rows:
                    interaction_type, user_id, category, template_id, response_time, session_duration, engagement_score = row
                    
                    interaction_counts[interaction_type] = interaction_counts.get(interaction_type, 0) + 1
                    
                    if response_time:
                        response_times.append(response_time)
                    if session_duration:
                        session_durations.append(session_duration)
                    if engagement_score:
                        engagement_scores.append(engagement_score)
                    
                    if category:
                        content_categories[category] = content_categories.get(category, 0) + 1
                    if template_id:
                        templates[template_id] = templates.get(template_id, 0) + 1
                
                # Calculate rates (as percentages of total interactions)
                like_rate = interaction_counts.get('like', 0) / total_interactions
                share_rate = interaction_counts.get('share', 0) / total_interactions
                save_rate = interaction_counts.get('save', 0) / total_interactions
                reaction_rate = interaction_counts.get('react', 0) / total_interactions
                
                # Calculate averages
                avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0
                avg_session_duration = sum(session_durations) / len(session_durations) if session_durations else 0.0
                avg_engagement_score = sum(engagement_scores) / len(engagement_scores) if engagement_scores else 0.0
                
                # Top categories and templates
                top_categories = sorted(content_categories.items(), key=lambda x: x[1], reverse=True)[:5]
                top_templates = sorted(templates.items(), key=lambda x: x[1], reverse=True)[:5]
                
                # User engagement segmentation (simplified)
                high_engagement = unique_users // 3
                medium_engagement = unique_users // 3
                low_engagement = unique_users - high_engagement - medium_engagement
                
                aggregated = AggregatedMetrics(
                    time_period=time_period,
                    period_start=start_date,
                    period_end=end_date,
                    total_interactions=total_interactions,
                    unique_users=unique_users,
                    total_content_views=total_interactions,  # Simplified
                    like_rate=like_rate,
                    share_rate=share_rate,
                    save_rate=save_rate,
                    reaction_rate=reaction_rate,
                    avg_response_time_ms=avg_response_time,
                    avg_session_duration_ms=avg_session_duration,
                    avg_engagement_score=avg_engagement_score,
                    top_content_categories=[cat for cat, _ in top_categories],
                    top_templates=[tmpl for tmpl, _ in top_templates],
                    high_engagement_users=high_engagement,
                    medium_engagement_users=medium_engagement,
                    low_engagement_users=low_engagement
                )
                
                return aggregated
                
        except Exception as e:
            logger.error(f"Failed to calculate aggregated metrics: {str(e)}")
            return None
    
    def store_aggregated_metrics(self, metrics: AggregatedMetrics) -> bool:
        """
        Store aggregated metrics for caching.
        
        Args:
            metrics: AggregatedMetrics object to store
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    metrics_data = json.dumps(asdict(metrics))
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO aggregated_metrics (
                            time_period, period_start, period_end, metrics_data, created_at
                        ) VALUES (?, ?, ?, ?, ?)
                    ''', (
                        metrics.time_period,
                        metrics.period_start.isoformat(),
                        metrics.period_end.isoformat(),
                        metrics_data,
                        datetime.now(timezone.utc).isoformat()
                    ))
                    
                    conn.commit()
                    
            logger.debug(f"Stored aggregated metrics for {metrics.time_period} period")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store aggregated metrics: {str(e)}")
            return False
    
    def cleanup_old_metrics(self, days_to_keep: Optional[int] = None) -> int:
        """
        Clean up old engagement metrics.
        
        Args:
            days_to_keep: Number of days to keep (uses instance default if None)
            
        Returns:
            Number of metrics removed
        """
        if days_to_keep is None:
            days_to_keep = self.metric_retention_days
        
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
            
            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Count records to be deleted
                    cursor.execute(
                        "SELECT COUNT(*) FROM engagement_metrics WHERE timestamp < ?",
                        (cutoff_date.isoformat(),)
                    )
                    count_to_delete = cursor.fetchone()[0]
                    
                    # Delete old records
                    cursor.execute(
                        "DELETE FROM engagement_metrics WHERE timestamp < ?",
                        (cutoff_date.isoformat(),)
                    )
                    
                    # Also cleanup old aggregated metrics
                    cursor.execute(
                        "DELETE FROM aggregated_metrics WHERE period_end < ?",
                        (cutoff_date.isoformat(),)
                    )
                    
                    conn.commit()
                    
            if count_to_delete > 0:
                logger.info(f"Cleaned up {count_to_delete} old engagement metrics")
            
            return count_to_delete
            
        except Exception as e:
            logger.error(f"Failed to cleanup old metrics: {str(e)}")
            return 0
    
    def get_storage_statistics(self) -> Dict[str, Any]:
        """
        Get storage statistics and health information.
        
        Returns:
            Dictionary with storage statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Count total metrics
                cursor.execute("SELECT COUNT(*) FROM engagement_metrics")
                total_metrics = cursor.fetchone()[0]
                
                # Count aggregated metrics
                cursor.execute("SELECT COUNT(*) FROM aggregated_metrics")
                aggregated_count = cursor.fetchone()[0]
                
                # Get date range
                cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM engagement_metrics")
                date_range = cursor.fetchone()
                
                # Get unique users and content
                cursor.execute("SELECT COUNT(DISTINCT user_id) FROM engagement_metrics")
                unique_users = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(DISTINCT content_id) FROM engagement_metrics")
                unique_content = cursor.fetchone()[0]
                
                # Get database file size
                db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
                
                return {
                    "total_metrics": total_metrics,
                    "aggregated_metrics": aggregated_count,
                    "unique_users": unique_users,
                    "unique_content": unique_content,
                    "date_range": {
                        "earliest": date_range[0],
                        "latest": date_range[1]
                    },
                    "database_size_bytes": db_size,
                    "database_path": self.db_path,
                    "retention_days": self.metric_retention_days
                }
                
        except Exception as e:
            logger.error(f"Failed to get storage statistics: {str(e)}")
            return {
                "error": str(e),
                "database_path": self.db_path
            }


# Global metrics storage instance
_metrics_storage = None

def get_metrics_storage() -> EngagementMetricsStorage:
    """Get global metrics storage instance."""
    global _metrics_storage
    if _metrics_storage is None:
        _metrics_storage = EngagementMetricsStorage()
    return _metrics_storage
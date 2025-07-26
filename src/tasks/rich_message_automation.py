"""
Celery tasks for Rich Message automation system.

This module contains automated tasks for daily Rich Message generation,
content creation, template composition, and delivery coordination.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, time, timedelta
from celery import Celery, Task
from celery.schedules import crontab
import os

from src.services.rich_message_service import RichMessageService
from src.services.line_service import LineService
from src.services.openai_service import OpenAIService
from src.services.conversation_service import ConversationService
from src.utils.template_manager import TemplateManager
from src.utils.content_generator import ContentGenerator, ContentRequest
from src.utils.image_composer import ImageComposer
from src.utils.template_selector import TemplateSelector, SelectionCriteria, SelectionStrategy
from src.utils.content_validator import ContentValidator, ValidationLevel
from src.utils.timezone_manager import get_timezone_manager, DeliverySchedule
from src.utils.delivery_tracker import get_delivery_tracker, ErrorType
from src.utils.analytics_tracker import get_analytics_tracker, InteractionType
from src.models.rich_message_models import ContentCategory, ContentTheme, DeliveryRecord, DeliveryStatus
from src.config.settings import Settings
from src.config.rich_message_config import get_rich_message_config

logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery('rich_message_automation')

# Configure Celery
celery_app.conf.update(
    broker_url=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    result_backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_compression='gzip',
    result_compression='gzip',
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    'generate-daily-rich-messages': {
        'task': 'src.tasks.rich_message_automation.generate_daily_rich_messages',
        'schedule': crontab(hour=6, minute=0),  # 6:00 AM UTC
    },
    'coordinate-timezone-deliveries': {
        'task': 'src.tasks.rich_message_automation.coordinate_timezone_deliveries',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
    'cleanup-delivery-records': {
        'task': 'src.tasks.rich_message_automation.cleanup_old_delivery_records',
        'schedule': crontab(hour=2, minute=0),  # 2:00 AM UTC daily
    },
    'process-delivery-retries': {
        'task': 'src.tasks.rich_message_automation.process_delivery_retries',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'health-check': {
        'task': 'src.tasks.rich_message_automation.health_check_task',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
}


class RichMessageTask(Task):
    """Base task class with error handling and logging."""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Task {self.name} failed: {exc}", extra={
            'task_id': task_id,
            'args': args,
            'kwargs': kwargs,
            'exception_info': str(einfo)
        })
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        logger.info(f"Task {self.name} completed successfully", extra={
            'task_id': task_id,
            'result': retval
        })


@celery_app.task(base=RichMessageTask, bind=True, max_retries=2)
def coordinate_timezone_deliveries(self, categories: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Coordinate Rich Message deliveries across multiple timezones.
    
    Args:
        categories: Optional list of specific categories to coordinate
        
    Returns:
        Dictionary with coordination results
    """
    try:
        start_time = datetime.now()
        logger.info("Starting timezone delivery coordination")
        
        # Initialize timezone manager
        timezone_manager = get_timezone_manager()
        config = get_rich_message_config()
        
        # Determine categories to process
        if categories:
            target_categories = [ContentCategory(cat) for cat in categories 
                               if cat in [c.value for c in ContentCategory]]
        else:
            target_categories = config.get_enabled_categories()
        
        results = {
            'total_categories': len(target_categories),
            'timezone_deliveries_scheduled': 0,
            'timezone_deliveries_executed': 0,
            'failed_deliveries': 0,
            'timezone_groups_processed': 0,
            'delivery_results': {},
            'errors': []
        }
        
        # Process each category
        for category in target_categories:
            try:
                # Get optimal delivery schedule for this category
                optimal_schedules = timezone_manager.get_optimal_delivery_schedule(category.value)
                
                if not optimal_schedules:
                    logger.info(f"No delivery schedules found for category {category.value}")
                    continue
                
                # Check which deliveries should be executed now
                upcoming_deliveries = []
                now = datetime.now()
                delivery_window = timedelta(minutes=30)  # 30-minute delivery window
                
                for schedule in optimal_schedules:
                    time_diff = abs(schedule.delivery_time_utc - now)
                    if time_diff <= delivery_window:
                        upcoming_deliveries.append(schedule)
                
                if not upcoming_deliveries:
                    logger.debug(f"No deliveries due now for category {category.value}")
                    continue
                
                # Execute deliveries
                category_results = []
                for schedule in upcoming_deliveries:
                    delivery_result = execute_timezone_delivery.delay(
                        schedule.timezone,
                        schedule.target_users,
                        category.value,
                        schedule.local_delivery_time.strftime("%H:%M")
                    )
                    
                    try:
                        result = delivery_result.get(timeout=300)  # 5 minutes
                        category_results.append(result)
                        
                        if result.get('success', False):
                            results['timezone_deliveries_executed'] += 1
                        else:
                            results['failed_deliveries'] += 1
                            results['errors'].append(f"Delivery to {schedule.timezone}: {result.get('error', 'Unknown error')}")
                            
                    except Exception as e:
                        logger.error(f"Failed to execute delivery for {schedule.timezone}: {str(e)}")
                        results['failed_deliveries'] += 1
                        results['errors'].append(f"Execution failed for {schedule.timezone}: {str(e)}")
                
                results['delivery_results'][category.value] = category_results
                results['timezone_deliveries_scheduled'] += len(upcoming_deliveries)
                results['timezone_groups_processed'] += len(set(s.timezone for s in upcoming_deliveries))
                
            except Exception as e:
                logger.error(f"Failed to coordinate deliveries for category {category.value}: {str(e)}")
                results['errors'].append(f"Category {category.value}: {str(e)}")
        
        # Calculate metrics
        execution_time = (datetime.now() - start_time).total_seconds()
        results['execution_time_seconds'] = execution_time
        results['success_rate'] = (results['timezone_deliveries_executed'] / 
                                 max(1, results['timezone_deliveries_scheduled']))
        
        logger.info(f"Timezone delivery coordination completed in {execution_time:.2f}s", extra=results)
        
        return results
        
    except Exception as e:
        logger.error(f"Timezone delivery coordination failed: {str(e)}")
        self.retry(countdown=60 * (self.request.retries + 1))


@celery_app.task(base=RichMessageTask, bind=True, max_retries=2)
def execute_timezone_delivery(self, timezone_name: str, target_users: List[str],
                             category: str, local_time: str) -> Dict[str, Any]:
    """
    Execute Rich Message delivery for specific timezone and users.
    
    Args:
        timezone_name: IANA timezone identifier
        target_users: List of user IDs to target
        category: Content category
        local_time: Local delivery time (HH:MM format)
        
    Returns:
        Dictionary with delivery execution results
    """
    try:
        start_time = datetime.now()
        logger.info(f"Executing delivery for timezone {timezone_name}, {len(target_users)} users")
        
        if not target_users:
            return {
                'success': True,
                'timezone': timezone_name,
                'users_count': 0,
                'message': 'No users to deliver to'
            }
        
        # Generate Rich Message for this timezone/category
        generation_result = generate_rich_message_for_category.delay(
            category, local_time
        )
        generated_message = generation_result.get(timeout=300)  # 5 minutes
        
        if not generated_message.get('success', False):
            return {
                'success': False,
                'timezone': timezone_name,
                'users_count': len(target_users),
                'error': f"Message generation failed: {generated_message.get('error', 'Unknown error')}",
                'stage': 'message_generation'
            }
        
        # Send to targeted users
        delivery_results = []
        successful_deliveries = 0
        failed_deliveries = 0
        
        # Send to users in batches for better performance
        batch_size = 50
        for i in range(0, len(target_users), batch_size):
            batch_users = target_users[i:i + batch_size]
            
            batch_result = send_rich_message_to_user_batch.delay(
                batch_users,
                generated_message.get('image_path', ''),
                generated_message.get('content_data', {}),
                category,
                timezone_name
            )
            
            try:
                batch_delivery = batch_result.get(timeout=120)  # 2 minutes
                delivery_results.append(batch_delivery)
                
                successful_deliveries += batch_delivery.get('successful_deliveries', 0)
                failed_deliveries += batch_delivery.get('failed_deliveries', 0)
                
            except Exception as e:
                logger.error(f"Batch delivery failed for {len(batch_users)} users: {str(e)}")
                failed_deliveries += len(batch_users)
                delivery_results.append({
                    'success': False,
                    'error': str(e),
                    'users_count': len(batch_users)
                })
        
        # Calculate metrics
        execution_time = (datetime.now() - start_time).total_seconds()
        total_users = successful_deliveries + failed_deliveries
        success_rate = successful_deliveries / max(1, total_users)
        
        result = {
            'success': success_rate > 0.5,  # Consider successful if >50% delivered
            'timezone': timezone_name,
            'users_count': len(target_users),
            'successful_deliveries': successful_deliveries,
            'failed_deliveries': failed_deliveries,
            'success_rate': success_rate,
            'execution_time_seconds': execution_time,
            'batch_results': delivery_results,
            'category': category,
            'local_delivery_time': local_time
        }
        
        if success_rate <= 0.5:
            result['error'] = f"Low success rate: {success_rate:.2%}"
        
        logger.info(f"Timezone delivery for {timezone_name} completed: "
                   f"{successful_deliveries}/{total_users} successful", extra=result)
        
        return result
        
    except Exception as e:
        logger.error(f"Timezone delivery execution failed for {timezone_name}: {str(e)}")
        self.retry(countdown=30 * (self.request.retries + 1))


@celery_app.task(base=RichMessageTask)
def process_delivery_retries(self) -> Dict[str, Any]:
    """
    Process pending delivery retries.
    
    Returns:
        Dictionary with retry processing results
    """
    try:
        start_time = datetime.now()
        logger.info("Processing delivery retries")
        
        delivery_tracker = get_delivery_tracker()
        
        # Get deliveries ready for retry
        ready_retries = delivery_tracker.get_pending_retries()
        
        if not ready_retries:
            return {
                'success': True,
                'message': 'No retries pending',
                'retries_processed': 0
            }
        
        results = {
            'success': True,
            'retries_processed': 0,
            'successful_retries': 0,
            'failed_retries': 0,
            'retry_results': [],
            'errors': []
        }
        
        # Process each retry
        for delivery_id in ready_retries:
            try:
                delivery_record = delivery_tracker.get_delivery_record(delivery_id)
                if not delivery_record:
                    continue
                
                # Execute retry
                retry_result = retry_failed_delivery.delay(
                    delivery_id,
                    delivery_record.user_id,
                    delivery_record.content_category,
                    delivery_record.timezone
                )
                
                # Get result with timeout
                result = retry_result.get(timeout=120)  # 2 minutes
                results['retry_results'].append(result)
                results['retries_processed'] += 1
                
                if result.get('success', False):
                    results['successful_retries'] += 1
                else:
                    results['failed_retries'] += 1
                    results['errors'].append(f"Retry {delivery_id}: {result.get('error', 'Unknown error')}")
                
            except Exception as e:
                logger.error(f"Failed to process retry for {delivery_id}: {str(e)}")
                results['failed_retries'] += 1
                results['errors'].append(f"Retry processing error {delivery_id}: {str(e)}")
        
        # Calculate metrics
        execution_time = (datetime.now() - start_time).total_seconds()
        results['execution_time_seconds'] = execution_time
        results['success_rate'] = (results['successful_retries'] / 
                                 max(1, results['retries_processed']))
        
        logger.info(f"Processed {results['retries_processed']} retries in {execution_time:.2f}s, "
                   f"{results['successful_retries']} successful")
        
        return results
        
    except Exception as e:
        logger.error(f"Retry processing failed: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'retries_processed': 0
        }


@celery_app.task(base=RichMessageTask, bind=True, max_retries=2)
def retry_failed_delivery(self, delivery_id: str, user_id: str, 
                         category: str, timezone_name: str) -> Dict[str, Any]:
    """
    Retry a failed delivery.
    
    Args:
        delivery_id: Original delivery ID
        user_id: User identifier
        category: Content category
        timezone_name: Target timezone
        
    Returns:
        Dictionary with retry results
    """
    try:
        logger.info(f"Retrying delivery {delivery_id} for user {user_id[:8]}...")
        
        delivery_tracker = get_delivery_tracker()
        
        # Start new attempt
        attempt_id = delivery_tracker.start_delivery_attempt(delivery_id)
        if not attempt_id:
            return {
                'success': False,
                'error': 'Could not start retry attempt',
                'delivery_id': delivery_id
            }
        
        # Generate fresh content for retry
        generation_result = generate_rich_message_for_category.delay(
            category, "09:00"  # Default time for retries
        )
        generated_message = generation_result.get(timeout=300)  # 5 minutes
        
        if not generated_message.get('success', False):
            error_msg = f"Content generation failed: {generated_message.get('error', 'Unknown error')}"
            delivery_tracker.record_delivery_failure(
                delivery_id, attempt_id, error_msg, ErrorType.GENERATION_ERROR
            )
            return {
                'success': False,
                'error': error_msg,
                'delivery_id': delivery_id,
                'stage': 'content_generation'
            }
        
        # Send to user
        delivery_start = datetime.now()
        
        batch_result = send_rich_message_to_user_batch.delay(
            [user_id],
            generated_message.get('image_path', ''),
            generated_message.get('content_data', {}),
            category,
            timezone_name,
            delivery_id=delivery_id,
            attempt_id=attempt_id
        )
        
        batch_delivery = batch_result.get(timeout=60)  # 1 minute
        delivery_time = int((datetime.now() - delivery_start).total_seconds() * 1000)
        
        if batch_delivery.get('success', False) and batch_delivery.get('successful_deliveries', 0) > 0:
            # Record success
            delivery_tracker.record_delivery_success(delivery_id, attempt_id, delivery_time)
            
            return {
                'success': True,
                'delivery_id': delivery_id,
                'attempt_id': attempt_id,
                'delivery_time_ms': delivery_time,
                'user_id': user_id[:8] + "...",
                'category': category
            }
        else:
            # Record failure
            error_msg = batch_delivery.get('error', 'Batch delivery failed')
            delivery_tracker.record_delivery_failure(
                delivery_id, attempt_id, error_msg, ErrorType.NETWORK_ERROR, delivery_time
            )
            
            return {
                'success': False,
                'error': error_msg,
                'delivery_id': delivery_id,
                'stage': 'delivery'
            }
        
    except Exception as e:
        logger.error(f"Retry failed for delivery {delivery_id}: {str(e)}")
        
        # Record failure if we have tracking info
        if 'attempt_id' in locals():
            delivery_tracker = get_delivery_tracker()
            delivery_tracker.record_delivery_failure(
                delivery_id, attempt_id, str(e), ErrorType.SYSTEM_ERROR
            )
        
        self.retry(countdown=30 * (self.request.retries + 1))


@celery_app.task(base=RichMessageTask, bind=True, max_retries=2)
def send_rich_message_to_user_batch(self, user_ids: List[str], image_path: str,
                                   content_data: Dict[str, Any], category: str,
                                   timezone_name: str, delivery_id: Optional[str] = None,
                                   attempt_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Send Rich Message to a batch of users with delivery tracking.
    
    Args:
        user_ids: List of user IDs
        image_path: Path to composed image
        content_data: Content data for the message
        category: Content category
        timezone_name: Target timezone
        delivery_id: Optional delivery ID for tracking
        attempt_id: Optional attempt ID for tracking
        
    Returns:
        Dictionary with batch delivery results
    """
    try:
        delivery_start = datetime.now()
        logger.info(f"Sending Rich Message to {len(user_ids)} users in {timezone_name}")
        
        delivery_tracker = get_delivery_tracker()
        
        # Initialize services
        settings = Settings()
        openai_service = OpenAIService(settings)
        conversation_service = ConversationService(settings)
        line_service = LineService(settings, openai_service, conversation_service)
        
        config = get_rich_message_config()
        template_manager = TemplateManager(config)
        content_generator = ContentGenerator(openai_service, config)
        
        rich_message_service = RichMessageService(
            line_bot_api=line_service.line_bot_api,
            template_manager=template_manager,
            content_generator=content_generator
        )
        
        # Create Flex Message
        flex_message = rich_message_service.create_flex_message(
            title=content_data.get('title', ''),
            content=content_data.get('content', ''),
            image_url=None,
            image_path=image_path
        )
        
        if not flex_message:
            error_msg = 'Failed to create Flex Message'
            
            # Record failure for tracked delivery
            if delivery_id and attempt_id:
                delivery_tracker.record_delivery_failure(
                    delivery_id, attempt_id, error_msg, ErrorType.CONTENT_ERROR
                )
            
            return {
                'success': False,
                'error': error_msg,
                'users_count': len(user_ids),
                'successful_deliveries': 0,
                'failed_deliveries': len(user_ids)
            }
        
        # Send to each user with individual tracking
        successful_deliveries = 0
        failed_deliveries = 0
        delivery_errors = []
        
        for user_id in user_ids:
            user_delivery_start = datetime.now()
            
            # Create delivery record if not tracking an existing delivery
            user_delivery_id = delivery_id
            user_attempt_id = attempt_id
            
            if not user_delivery_id:
                # Create new delivery record for this user
                delivery_record = delivery_tracker.create_delivery_record(
                    user_id=user_id,
                    content_category=category,
                    timezone_name=timezone_name,
                    scheduled_time=datetime.now(timezone.utc),
                    content_title=content_data.get('title')
                )
                user_delivery_id = delivery_record.delivery_id
                user_attempt_id = delivery_tracker.start_delivery_attempt(user_delivery_id)
            
            try:
                # Send individual message
                line_service.line_bot_api.push_message(user_id, flex_message)
                
                # Calculate delivery time
                delivery_time_ms = int((datetime.now() - user_delivery_start).total_seconds() * 1000)
                
                # Record success
                if user_delivery_id and user_attempt_id:
                    delivery_tracker.record_delivery_success(
                        user_delivery_id, user_attempt_id, delivery_time_ms
                    )
                
                successful_deliveries += 1
                
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Failed to send message to user {user_id[:8]}...: {error_msg}")
                
                # Classify error type
                error_type = ErrorType.NETWORK_ERROR
                if "rate limit" in error_msg.lower():
                    error_type = ErrorType.RATE_LIMIT
                elif "forbidden" in error_msg.lower() or "user not found" in error_msg.lower():
                    error_type = ErrorType.INVALID_USER
                elif "timeout" in error_msg.lower():
                    error_type = ErrorType.TIMEOUT_ERROR
                
                # Calculate delivery time
                delivery_time_ms = int((datetime.now() - user_delivery_start).total_seconds() * 1000)
                
                # Record failure
                if user_delivery_id and user_attempt_id:
                    delivery_tracker.record_delivery_failure(
                        user_delivery_id, user_attempt_id, error_msg, error_type, delivery_time_ms
                    )
                
                failed_deliveries += 1
                delivery_errors.append(f"User {user_id[:8]}...: {error_msg}")
        
        # Calculate total processing time
        total_time_ms = int((datetime.now() - delivery_start).total_seconds() * 1000)
        
        result = {
            'success': successful_deliveries > 0,
            'users_count': len(user_ids),
            'successful_deliveries': successful_deliveries,
            'failed_deliveries': failed_deliveries,
            'success_rate': successful_deliveries / len(user_ids) if user_ids else 0,
            'timezone': timezone_name,
            'category': category,
            'delivery_errors': delivery_errors[:5],  # Limit error list
            'total_processing_time_ms': total_time_ms,
            'tracked_delivery': delivery_id is not None
        }
        
        logger.info(f"Batch delivery completed: {successful_deliveries}/{len(user_ids)} successful "
                   f"in {total_time_ms}ms")
        
        return result
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Batch delivery failed: {error_msg}")
        
        # Record failure for tracked delivery
        if delivery_id and attempt_id:
            delivery_tracker = get_delivery_tracker()
            delivery_tracker.record_delivery_failure(
                delivery_id, attempt_id, error_msg, ErrorType.SYSTEM_ERROR
            )
        
        self.retry(countdown=30 * (self.request.retries + 1))


@celery_app.task(base=RichMessageTask, bind=True, max_retries=2)
def update_user_timezone_from_activity(self, user_id: str, activity_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update user timezone based on activity patterns.
    
    Args:
        user_id: User identifier
        activity_data: User activity data for timezone detection
        
    Returns:
        Dictionary with timezone update results
    """
    try:
        logger.info(f"Updating timezone for user {user_id[:8]}... from activity data")
        
        timezone_manager = get_timezone_manager()
        
        # Detect timezone from activity data
        timezone_info = timezone_manager.detect_user_timezone(user_id, activity_data)
        
        if timezone_info:
            logger.info(f"Detected timezone {timezone_info.timezone} for user {user_id[:8]}... "
                       f"(method: {timezone_info.detected_method}, confidence: {timezone_info.confidence:.2f})")
            
            return {
                'success': True,
                'user_id': user_id[:8] + "...",
                'detected_timezone': timezone_info.timezone,
                'detection_method': timezone_info.detected_method,
                'confidence': timezone_info.confidence,
                'offset_hours': timezone_info.offset_hours
            }
        else:
            return {
                'success': False,
                'user_id': user_id[:8] + "...",
                'error': 'Could not detect timezone from activity data'
            }
        
    except Exception as e:
        logger.error(f"Timezone update failed for user {user_id[:8]}...: {str(e)}")
        self.retry(countdown=30 * (self.request.retries + 1))


@celery_app.task(base=RichMessageTask)
def cleanup_timezone_data(self, days_to_keep: int = 30) -> Dict[str, Any]:
    """
    Clean up old timezone data and delivery schedules.
    
    Args:
        days_to_keep: Keep data newer than this many days
        
    Returns:
        Dictionary with cleanup results
    """
    try:
        logger.info(f"Cleaning up timezone data older than {days_to_keep} days")
        
        timezone_manager = get_timezone_manager()
        
        # Cleanup old delivery schedules
        removed_schedules = timezone_manager.cleanup_old_schedules(hours_past=days_to_keep * 24)
        
        # Get current statistics
        stats = timezone_manager.get_timezone_statistics()
        
        return {
            'success': True,
            'removed_schedules': removed_schedules,
            'current_stats': stats,
            'days_to_keep': days_to_keep
        }
        
    except Exception as e:
        logger.error(f"Timezone cleanup failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@celery_app.task(base=RichMessageTask, bind=True, max_retries=3)
def generate_daily_rich_messages(self, categories: Optional[List[str]] = None,
                                target_time: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate and deliver daily Rich Messages for all active categories.
    
    Args:
        categories: Optional list of specific categories to generate
        target_time: Optional target time for delivery (HH:MM format)
        
    Returns:
        Dictionary with generation results
    """
    try:
        start_time = datetime.now()
        logger.info("Starting daily Rich Message generation")
        
        # Initialize services
        config = get_rich_message_config()
        settings = Settings()
        
        # Parse target time
        if target_time:
            hour, minute = map(int, target_time.split(':'))
            delivery_time = time(hour, minute)
        else:
            delivery_time = time(config.scheduling.default_send_hour, 0)
        
        # Determine categories to process
        if categories:
            target_categories = [ContentCategory(cat) for cat in categories 
                               if cat in [c.value for c in ContentCategory]]
        else:
            target_categories = config.get_enabled_categories()
        
        results = {
            'total_categories': len(target_categories),
            'successful_generations': 0,
            'failed_generations': 0,
            'delivery_results': {},
            'errors': []
        }
        
        # Generate content for each category
        for category in target_categories:
            try:
                generation_result = generate_rich_message_for_category.delay(
                    category.value,
                    delivery_time.strftime("%H:%M")
                )
                
                # Get result (with timeout)
                category_result = generation_result.get(timeout=300)  # 5 minutes
                
                if category_result.get('success', False):
                    results['successful_generations'] += 1
                else:
                    results['failed_generations'] += 1
                    results['errors'].append(f"Category {category.value}: {category_result.get('error', 'Unknown error')}")
                
                results['delivery_results'][category.value] = category_result
                
            except Exception as e:
                logger.error(f"Failed to process category {category.value}: {str(e)}")
                results['failed_generations'] += 1
                results['errors'].append(f"Category {category.value}: {str(e)}")
        
        # Calculate metrics
        execution_time = (datetime.now() - start_time).total_seconds()
        results['execution_time_seconds'] = execution_time
        results['success_rate'] = (results['successful_generations'] / 
                                 max(1, results['total_categories']))
        
        logger.info(f"Daily Rich Message generation completed in {execution_time:.2f}s", extra=results)
        
        return results
        
    except Exception as e:
        logger.error(f"Daily Rich Message generation failed: {str(e)}")
        self.retry(countdown=60 * (self.request.retries + 1))


@celery_app.task(base=RichMessageTask, bind=True, max_retries=2)
def generate_rich_message_for_category(self, category: str, 
                                     target_time: str = "09:00") -> Dict[str, Any]:
    """
    Generate and deliver Rich Message for a specific category.
    
    Args:
        category: Content category name
        target_time: Target delivery time (HH:MM format)
        
    Returns:
        Dictionary with generation result
    """
    try:
        start_time = datetime.now()
        logger.info(f"Generating Rich Message for category: {category}")
        
        # Initialize services
        settings = Settings()
        config = get_rich_message_config()
        
        openai_service = OpenAIService(settings)
        conversation_service = ConversationService(settings)
        line_service = LineService(settings, openai_service, conversation_service)
        
        template_manager = TemplateManager(config)
        content_generator = ContentGenerator(openai_service, config)
        image_composer = ImageComposer(config)
        template_selector = TemplateSelector(template_manager, config)
        content_validator = ContentValidator(ValidationLevel.MODERATE)
        
        rich_message_service = RichMessageService(
            line_bot_api=line_service.line_bot_api,
            template_manager=template_manager,
            content_generator=content_generator
        )
        
        # Parse delivery time
        hour, minute = map(int, target_time.split(':'))
        delivery_time = time(hour, minute)
        
        # Parse category
        content_category = ContentCategory(category)
        
        # Step 1: Generate content
        content_result = generate_content_for_delivery.delay(
            category, target_time
        )
        generated_content = content_result.get(timeout=120)  # 2 minutes
        
        if not generated_content.get('success', False):
            return {
                'success': False,
                'error': f"Content generation failed: {generated_content.get('error', 'Unknown error')}",
                'stage': 'content_generation'
            }
        
        # Step 2: Select template
        template_result = select_template_for_content.delay(
            category, target_time, generated_content['content_metadata']
        )
        template_selection = template_result.get(timeout=60)  # 1 minute
        
        if not template_selection.get('success', False):
            return {
                'success': False,
                'error': f"Template selection failed: {template_selection.get('error', 'Unknown error')}",
                'stage': 'template_selection'
            }
        
        # Step 3: Compose image
        composition_result = compose_rich_message_image.delay(
            template_selection['template_id'],
            generated_content['content_data']
        )
        image_composition = composition_result.get(timeout=180)  # 3 minutes
        
        if not image_composition.get('success', False):
            return {
                'success': False,
                'error': f"Image composition failed: {image_composition.get('error', 'Unknown error')}",
                'stage': 'image_composition'
            }
        
        # Step 4: Create and broadcast Rich Message
        broadcast_result = broadcast_rich_message.delay(
            image_composition['image_path'],
            generated_content['content_data'],
            category
        )
        delivery_result = broadcast_result.get(timeout=120)  # 2 minutes
        
        # Calculate metrics
        execution_time = (datetime.now() - start_time).total_seconds()
        
        result = {
            'success': delivery_result.get('success', False),
            'category': category,
            'target_time': target_time,
            'execution_time_seconds': execution_time,
            'content_title': generated_content.get('content_data', {}).get('title', ''),
            'template_id': template_selection.get('template_id', ''),
            'image_path': image_composition.get('image_path', ''),
            'delivery_result': delivery_result,
            'stages_completed': 4 if delivery_result.get('success', False) else 3
        }
        
        if not delivery_result.get('success', False):
            result['error'] = delivery_result.get('error', 'Broadcast failed')
            result['stage'] = 'broadcast'
        
        logger.info(f"Rich Message generation for {category} completed", extra=result)
        return result
        
    except Exception as e:
        logger.error(f"Rich Message generation for {category} failed: {str(e)}")
        self.retry(countdown=30 * (self.request.retries + 1))


@celery_app.task(base=RichMessageTask, bind=True, max_retries=2)
def generate_content_for_delivery(self, category: str, target_time: str) -> Dict[str, Any]:
    """Generate appropriate content for delivery."""
    try:
        # Initialize services
        settings = Settings()
        config = get_rich_message_config()
        openai_service = OpenAIService(settings)
        content_generator = ContentGenerator(openai_service, config)
        content_validator = ContentValidator(ValidationLevel.MODERATE)
        
        # Parse parameters
        content_category = ContentCategory(category)
        hour, minute = map(int, target_time.split(':'))
        delivery_time = time(hour, minute)
        
        # Generate content
        generated_content = content_generator.generate_daily_content(
            content_category,
            delivery_time,
            language="en"  # TODO: Support multiple languages
        )
        
        if not generated_content:
            return {
                'success': False,
                'error': 'Failed to generate content'
            }
        
        # Validate content
        validation_result = content_validator.validate_content(generated_content)
        
        if validation_result.result.value == 'rejected':
            return {
                'success': False,
                'error': f'Content validation failed: {", ".join([issue.message for issue in validation_result.issues])}'
            }
        
        return {
            'success': True,
            'content_data': {
                'title': generated_content.title,
                'content': generated_content.content,
                'language': generated_content.language,
                'category': generated_content.category.value,
                'theme': generated_content.theme.value if generated_content.theme else None
            },
            'content_metadata': {
                'generation_time': generated_content.generation_time.isoformat(),
                'validation_score': validation_result.score,
                'validation_result': validation_result.result.value
            }
        }
        
    except Exception as e:
        logger.error(f"Content generation failed: {str(e)}")
        self.retry(countdown=30 * (self.request.retries + 1))


@celery_app.task(base=RichMessageTask, bind=True, max_retries=2)
def select_template_for_content(self, category: str, target_time: str, 
                               content_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Select appropriate template for content."""
    try:
        # Initialize services
        config = get_rich_message_config()
        template_manager = TemplateManager(config)
        template_selector = TemplateSelector(template_manager, config)
        
        # Parse parameters
        content_category = ContentCategory(category)
        hour, minute = map(int, target_time.split(':'))
        delivery_time = time(hour, minute)
        
        # Create selection criteria
        criteria = SelectionCriteria(
            category=content_category,
            time_context=delivery_time,
            energy_level="medium",  # TODO: Determine from content
            strategy=SelectionStrategy.TIME_OPTIMIZED
        )
        
        # Select template
        selected_template = template_selector.select_template(criteria)
        
        if not selected_template:
            return {
                'success': False,
                'error': f'No suitable template found for category {category}'
            }
        
        return {
            'success': True,
            'template_id': selected_template.template_id,
            'template_metadata': {
                'category': selected_template.category.value,
                'theme': getattr(selected_template, 'theme', None),
                'mood': getattr(selected_template, 'mood', None),
                'energy_level': getattr(selected_template, 'energy_level', None)
            }
        }
        
    except Exception as e:
        logger.error(f"Template selection failed: {str(e)}")
        self.retry(countdown=30 * (self.request.retries + 1))


@celery_app.task(base=RichMessageTask, bind=True, max_retries=2)
def compose_rich_message_image(self, template_id: str, content_data: Dict[str, Any]) -> Dict[str, Any]:
    """Compose Rich Message image from template and content."""
    try:
        # Initialize services
        config = get_rich_message_config()
        template_manager = TemplateManager(config)
        image_composer = ImageComposer(config)
        
        # Load template
        template = template_manager.load_template(template_id)
        if not template:
            return {
                'success': False,
                'error': f'Template {template_id} not found'
            }
        
        # Create content object
        from src.utils.content_generator import GeneratedContent
        generated_content = GeneratedContent(
            title=content_data['title'],
            content=content_data['content'],
            language=content_data['language'],
            category=ContentCategory(content_data['category']),
            theme=ContentTheme(content_data['theme']) if content_data.get('theme') else None,
            metadata={},
            generation_time=datetime.now()
        )
        
        # Get template image path
        template_image_path = template_manager.get_template_file_path(template_id)
        if not template_image_path:
            return {
                'success': False,
                'error': f'Template image file not found for {template_id}'
            }
        
        # Compose image
        composition_result = image_composer.compose_image(
            template=template,
            content=generated_content,
            template_image_path=template_image_path
        )
        
        if not composition_result.success:
            return {
                'success': False,
                'error': f'Image composition failed: {composition_result.error_message}'
            }
        
        return {
            'success': True,
            'image_path': composition_result.image_path,
            'image_size': composition_result.image_size,
            'composition_metadata': composition_result.metadata
        }
        
    except Exception as e:
        logger.error(f"Image composition failed: {str(e)}")
        self.retry(countdown=30 * (self.request.retries + 1))


@celery_app.task(base=RichMessageTask, bind=True, max_retries=3)
def broadcast_rich_message(self, image_path: str, content_data: Dict[str, Any], 
                          category: str) -> Dict[str, Any]:
    """Broadcast Rich Message to users."""
    try:
        # Initialize services
        settings = Settings()
        config = get_rich_message_config()
        
        openai_service = OpenAIService(settings)
        conversation_service = ConversationService(settings)
        line_service = LineService(settings, openai_service, conversation_service)
        
        rich_message_service = RichMessageService(
            line_bot_api=line_service.line_bot_api,
            template_manager=None,
            content_generator=None
        )
        
        # Create Flex Message
        flex_message = rich_message_service.create_flex_message(
            title=content_data['title'],
            content=content_data['content'],
            image_url=None,  # Will use local image
            image_path=image_path
        )
        
        if not flex_message:
            return {
                'success': False,
                'error': 'Failed to create Flex Message'
            }
        
        # Broadcast message
        broadcast_result = rich_message_service.broadcast_rich_message(
            flex_message,
            target_audience=None  # Broadcast to all users
        )
        
        # Create delivery record
        delivery_record = DeliveryRecord(
            delivery_id=f"broadcast_{category}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            category=ContentCategory(category),
            content_title=content_data['title'],
            template_id="",  # TODO: Pass template_id
            scheduled_time=datetime.now(),
            status=DeliveryStatus.SENT if broadcast_result.get('success') else DeliveryStatus.FAILED,
            created_at=datetime.now()
        )
        
        if broadcast_result.get('success'):
            delivery_record.mark_as_sent()
        else:
            delivery_record.mark_as_failed(broadcast_result.get('error', 'Unknown error'))
        
        return {
            'success': broadcast_result.get('success', False),
            'delivery_record_id': delivery_record.delivery_id,
            'broadcast_details': broadcast_result,
            'message_type': 'rich_message',
            'category': category
        }
        
    except Exception as e:
        logger.error(f"Rich Message broadcast failed: {str(e)}")
        self.retry(countdown=60 * (self.request.retries + 1))


@celery_app.task(base=RichMessageTask)
def cleanup_old_delivery_records(days_to_keep: int = 30) -> Dict[str, Any]:
    """Clean up old delivery records."""
    try:
        logger.info(f"Cleaning up delivery records older than {days_to_keep} days")
        
        # TODO: Implement actual database cleanup when persistence is added
        # For now, this is a placeholder
        
        return {
            'success': True,
            'records_cleaned': 0,
            'days_to_keep': days_to_keep
        }
        
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


@celery_app.task(base=RichMessageTask)
def health_check_task() -> Dict[str, Any]:
    """Comprehensive health check task for monitoring."""
    try:
        start_time = datetime.now()
        
        # Initialize monitoring systems
        delivery_tracker = get_delivery_tracker()
        analytics_tracker = get_analytics_tracker()
        timezone_manager = get_timezone_manager()
        config = get_rich_message_config()
        
        # Basic health status
        health_status = {
            'timestamp': start_time.isoformat(),
            'celery_worker_active': True,
            'config_loaded': config is not None,
            'services_status': {},
            'delivery_health': {},
            'analytics_health': {},
            'timezone_health': {},
            'overall_status': 'healthy',
            'issues': []
        }
        
        # Check individual services
        try:
            settings = Settings()
            health_status['services_status']['settings'] = 'healthy'
        except Exception as e:
            health_status['services_status']['settings'] = f'error: {str(e)}'
            health_status['issues'].append(f'Settings service error: {str(e)}')
        
        try:
            # Check OpenAI service
            openai_service = OpenAIService(settings)
            health_status['services_status']['openai'] = 'healthy'
        except Exception as e:
            health_status['services_status']['openai'] = f'error: {str(e)}'
            health_status['issues'].append(f'OpenAI service error: {str(e)}')
        
        try:
            # Check LINE service
            conversation_service = ConversationService(settings)
            line_service = LineService(settings, openai_service, conversation_service)
            health_status['services_status']['line'] = 'healthy'
        except Exception as e:
            health_status['services_status']['line'] = f'error: {str(e)}'
            health_status['issues'].append(f'LINE service error: {str(e)}')
        
        # Delivery system health
        try:
            delivery_health = delivery_tracker.get_delivery_health_status()
            health_status['delivery_health'] = delivery_health
            
            if delivery_health['status'] == 'critical':
                health_status['overall_status'] = 'critical'
                health_status['issues'].extend(delivery_health['issues'])
            elif delivery_health['status'] == 'warning' and health_status['overall_status'] == 'healthy':
                health_status['overall_status'] = 'warning'
                health_status['issues'].extend(delivery_health['issues'])
                
        except Exception as e:
            health_status['delivery_health'] = {'status': 'error', 'error': str(e)}
            health_status['issues'].append(f'Delivery tracking error: {str(e)}')
        
        # Analytics system health
        try:
            system_metrics = analytics_tracker.calculate_system_metrics()
            engagement_summary = analytics_tracker.get_user_engagement_summary()
            
            health_status['analytics_health'] = {
                'status': 'healthy',
                'total_users': system_metrics.total_users,
                'active_users': system_metrics.active_users,
                'overall_open_rate': system_metrics.overall_open_rate,
                'overall_interaction_rate': system_metrics.overall_interaction_rate,
                'user_retention_rate': system_metrics.user_retention_rate,
                'system_uptime_percentage': system_metrics.system_uptime_percentage
            }
            
            # Check for analytics issues
            if system_metrics.overall_open_rate < 0.1:  # Less than 10% open rate
                health_status['issues'].append(f'Low open rate: {system_metrics.overall_open_rate:.1%}')
                if health_status['overall_status'] == 'healthy':
                    health_status['overall_status'] = 'warning'
            
            if system_metrics.user_retention_rate < 0.3:  # Less than 30% retention
                health_status['issues'].append(f'Low retention rate: {system_metrics.user_retention_rate:.1%}')
                if health_status['overall_status'] == 'healthy':
                    health_status['overall_status'] = 'warning'
                    
        except Exception as e:
            health_status['analytics_health'] = {'status': 'error', 'error': str(e)}
            health_status['issues'].append(f'Analytics tracking error: {str(e)}')
        
        # Timezone system health
        try:
            timezone_stats = timezone_manager.get_timezone_statistics()
            
            health_status['timezone_health'] = {
                'status': 'healthy',
                'total_users_with_timezone': timezone_stats['total_users'],
                'timezones_covered': timezone_stats['timezones_count'],
                'timezone_groups': timezone_stats['groups_count'],
                'scheduled_deliveries': timezone_stats['scheduled_deliveries']
            }
            
            # Check for timezone issues
            if timezone_stats['total_users'] == 0:
                health_status['issues'].append('No users with detected timezones')
                if health_status['overall_status'] == 'healthy':
                    health_status['overall_status'] = 'warning'
                    
        except Exception as e:
            health_status['timezone_health'] = {'status': 'error', 'error': str(e)}
            health_status['issues'].append(f'Timezone management error: {str(e)}')
        
        # Template system health
        try:
            template_manager = TemplateManager(config)
            available_templates = len(template_manager.templates)
            
            health_status['template_health'] = {
                'status': 'healthy',
                'available_templates': available_templates
            }
            
            if available_templates == 0:
                health_status['template_health']['status'] = 'critical'
                health_status['issues'].append('No templates available')
                health_status['overall_status'] = 'critical'
                
        except Exception as e:
            health_status['template_health'] = {'status': 'error', 'error': str(e)}
            health_status['issues'].append(f'Template system error: {str(e)}')
        
        # Performance metrics
        execution_time = (datetime.now() - start_time).total_seconds()
        health_status['health_check_execution_time_ms'] = int(execution_time * 1000)
        
        # Determine overall status based on issues
        if any('critical' in issue.lower() or 'error' in issue.lower() for issue in health_status['issues']):
            health_status['overall_status'] = 'critical'
        elif health_status['issues']:
            health_status['overall_status'] = 'warning'
        
        logger.info(f"Health check completed in {execution_time:.2f}s, status: {health_status['overall_status']}")
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'critical',
            'error': str(e),
            'issues': [f'Health check system failure: {str(e)}']
        }


@celery_app.task(base=RichMessageTask, bind=True)
def send_rich_message_to_user(self, user_id: str, category: str, 
                             custom_content: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Send personalized Rich Message to specific user."""
    try:
        logger.info(f"Sending Rich Message to user {user_id[:8]}... category: {category}")
        
        # TODO: Implement personalized message delivery
        # This would include user preference checking, timezone adjustment, etc.
        
        return {
            'success': True,
            'user_id': user_id[:8] + "...",  # Truncated for privacy
            'category': category,
            'delivered_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Personal Rich Message delivery failed: {str(e)}")
        self.retry(countdown=30 * (self.request.retries + 1))


# Task routing configuration
celery_app.conf.task_routes = {
    'src.tasks.rich_message_automation.generate_daily_rich_messages': {'queue': 'high_priority'},
    'src.tasks.rich_message_automation.coordinate_timezone_deliveries': {'queue': 'high_priority'},
    'src.tasks.rich_message_automation.execute_timezone_delivery': {'queue': 'timezone_delivery'},
    'src.tasks.rich_message_automation.send_rich_message_to_user_batch': {'queue': 'batch_delivery'},
    'src.tasks.rich_message_automation.process_delivery_retries': {'queue': 'retry_processing'},
    'src.tasks.rich_message_automation.retry_failed_delivery': {'queue': 'retry_delivery'},
    'src.tasks.rich_message_automation.update_user_timezone_from_activity': {'queue': 'timezone_management'},
    'src.tasks.rich_message_automation.cleanup_timezone_data': {'queue': 'maintenance'},
    'src.tasks.rich_message_automation.generate_rich_message_for_category': {'queue': 'default'},
    'src.tasks.rich_message_automation.generate_content_for_delivery': {'queue': 'content_generation'},
    'src.tasks.rich_message_automation.select_template_for_content': {'queue': 'template_processing'},
    'src.tasks.rich_message_automation.compose_rich_message_image': {'queue': 'image_processing'},
    'src.tasks.rich_message_automation.broadcast_rich_message': {'queue': 'delivery'},
    'src.tasks.rich_message_automation.cleanup_old_delivery_records': {'queue': 'maintenance'},
    'src.tasks.rich_message_automation.health_check_task': {'queue': 'monitoring'},
    'src.tasks.rich_message_automation.send_rich_message_to_user': {'queue': 'personal_delivery'},
}


if __name__ == "__main__":
    # For testing purposes
    celery_app.start()
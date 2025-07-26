"""
Background tasks for image processing
"""

import logging
from celery import current_task
from src.utils.celery_app import celery_app
from src.utils.image_utils import ImageProcessor
from src.utils.async_http import download_image_async
import asyncio

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_image_async(self, line_bot_api_token: str, message_id: str, user_id: str):
    """
    Background task to process LINE image messages
    
    Args:
        line_bot_api_token: LINE Bot API token
        message_id: LINE message ID
        user_id: User ID for tracking
    
    Returns:
        Dict with processing result
    """
    try:
        logger.info(f"Processing image {message_id} for user {user_id}")
        
        # Update task state
        current_task.update_state(
            state='PROGRESS',
            meta={'status': 'Downloading image...', 'progress': 25}
        )
        
        # Create image processor
        with ImageProcessor() as processor:
            # Download image (this would need to be adapted for async)
            # For now, we'll use the existing sync method
            from linebot import LineBotApi
            line_bot_api = LineBotApi(line_bot_api_token)
            
            result = processor.download_image_from_line(line_bot_api, message_id)
            
            if not result['success']:
                logger.error(f"Failed to download image: {result['error']}")
                return {
                    'success': False,
                    'error': result['error'],
                    'user_id': user_id
                }
            
            # Update progress
            current_task.update_state(
                state='PROGRESS',
                meta={'status': 'Processing image...', 'progress': 75}
            )
            
            # Process image for AI
            processed_result = processor.process_image_for_openai(
                result['image_data'],
                result['format']
            )
            
            if processed_result['success']:
                current_task.update_state(
                    state='SUCCESS',
                    meta={'status': 'Complete', 'progress': 100}
                )
                
                return {
                    'success': True,
                    'base64_image': processed_result['base64_image'],
                    'format': processed_result['format'],
                    'size_info': processed_result['size_info'],
                    'user_id': user_id
                }
            else:
                return {
                    'success': False,
                    'error': processed_result['error'],
                    'user_id': user_id
                }
                
    except Exception as exc:
        logger.error(f"Image processing error: {exc}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying image processing (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {
            'success': False,
            'error': f'Image processing failed after {self.max_retries} retries: {str(exc)}',
            'user_id': user_id
        }

@celery_app.task
def cleanup_temp_files(file_paths: list):
    """
    Background task to clean up temporary files
    
    Args:
        file_paths: List of file paths to delete
    """
    import os
    
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to clean up {file_path}: {e}")
    
    return f"Cleaned up {len(file_paths)} files"
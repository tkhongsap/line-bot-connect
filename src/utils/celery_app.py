"""
Celery configuration for background task processing
"""

import os
from celery import Celery

# Celery configuration
BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/1')
RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

# Create Celery app
celery_app = Celery(
    'line_bot_tasks',
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=[
        'src.tasks.image_processing',
        'src.tasks.ai_processing'
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Task routing
    task_routes={
        'src.tasks.image_processing.*': {'queue': 'image_queue'},
        'src.tasks.ai_processing.*': {'queue': 'ai_queue'},
    },
    
    # Worker settings
    worker_max_tasks_per_child=100,
    worker_prefetch_multiplier=1,
    
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
    
    # Result settings
    result_expires=3600,  # 1 hour
)

# Health check task
@celery_app.task
def ping():
    """Simple ping task to check Celery health"""
    return 'pong'
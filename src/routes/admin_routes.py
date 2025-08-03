"""
Administrative Routes for Rich Message Automation System.

This module provides Flask routes for the administrative web interface,
including campaign management, analytics dashboard, and system monitoring.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from typing import Dict, Any

from src.utils.admin_controller import get_admin_controller, CampaignStatus
from src.config.settings import Settings

logger = logging.getLogger(__name__)

# Create Blueprint for admin routes
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Simple authentication middleware (for demo purposes)
def require_admin_auth():
    """Simple admin authentication check."""
    # In production, implement proper authentication
    auth_header = request.headers.get('Authorization')
    if not auth_header or auth_header != 'Bearer admin_token':
        # For demo, allow access without authentication
        # return jsonify({"error": "Admin authentication required"}), 401
        pass


@admin_bp.before_request
def before_admin_request():
    """Run before each admin request."""
    require_admin_auth()


@admin_bp.route('/')
def admin_dashboard():
    """Main admin dashboard."""
    try:
        admin_controller = get_admin_controller()
        
        # Get dashboard data
        dashboard_result = admin_controller.get_analytics_dashboard(days=7)
        
        if dashboard_result['success']:
            dashboard_data = dashboard_result['dashboard_data']
        else:
            dashboard_data = {"error": dashboard_result.get('error', 'Unknown error')}
        
        # Get system health
        health_status = admin_controller.check_system_health()
        
        # Get recent campaigns
        campaigns_result = admin_controller.get_campaign_list(limit=10)
        recent_campaigns = campaigns_result.get('campaigns', []) if campaigns_result['success'] else []
        
        return render_template('admin/dashboard.html',
                             dashboard_data=dashboard_data,
                             health_status=health_status.__dict__,
                             recent_campaigns=recent_campaigns,
                             page_title="Admin Dashboard")
        
    except Exception as e:
        logger.error(f"Admin dashboard error: {str(e)}")
        return render_template('admin/error.html', 
                             error=str(e), 
                             page_title="Dashboard Error"), 500


@admin_bp.route('/campaigns')
def campaigns_list():
    """Campaign management page."""
    try:
        admin_controller = get_admin_controller()
        
        # Get filter parameters
        status_filter = request.args.get('status')
        if status_filter:
            try:
                status_filter = CampaignStatus(status_filter)
            except ValueError:
                status_filter = None
        
        # Get campaigns
        campaigns_result = admin_controller.get_campaign_list(status_filter=status_filter)
        
        if campaigns_result['success']:
            campaigns = campaigns_result['campaigns']
        else:
            campaigns = []
            flash(f"Error loading campaigns: {campaigns_result.get('error')}", 'error')
        
        return render_template('admin/campaigns.html',
                             campaigns=campaigns,
                             status_filter=status_filter.value if status_filter else None,
                             campaign_statuses=[status.value for status in CampaignStatus],
                             page_title="Campaign Management")
        
    except Exception as e:
        logger.error(f"Campaigns list error: {str(e)}")
        return render_template('admin/error.html', 
                             error=str(e), 
                             page_title="Campaigns Error"), 500


@admin_bp.route('/campaigns/create', methods=['GET', 'POST'])
def create_campaign():
    """Create new campaign."""
    if request.method == 'GET':
        return render_template('admin/create_campaign.html', 
                             page_title="Create Campaign")
    
    try:
        admin_controller = get_admin_controller()
        
        # Get form data
        data = request.get_json() if request.is_json else request.form
        
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        content_title = data.get('content_title', '').strip()
        content_message = data.get('content_message', '').strip()
        image_url = data.get('image_url', '').strip() or None
        content_category = data.get('content_category', 'general')
        include_interactions = data.get('include_interactions', True)
        
        # Validation
        if not all([name, content_title, content_message]):
            return jsonify({
                "success": False,
                "error": "Name, title, and message are required"
            }), 400
        
        # Create campaign
        result = admin_controller.create_campaign(
            name=name,
            description=description,
            content_title=content_title,
            content_message=content_message,
            image_url=image_url,
            content_category=content_category,
            include_interactions=bool(include_interactions),
            created_by=request.remote_addr  # Use IP as simple user identifier
        )
        
        if result['success']:
            if request.is_json:
                return jsonify(result)
            else:
                flash(f"Campaign '{name}' created successfully!", 'success')
                return redirect(url_for('admin.campaign_details', 
                                      campaign_id=result['campaign_id']))
        else:
            if request.is_json:
                return jsonify(result), 400
            else:
                flash(f"Error creating campaign: {result.get('error')}", 'error')
                return render_template('admin/create_campaign.html', 
                                     form_data=data,
                                     page_title="Create Campaign")
        
    except Exception as e:
        logger.error(f"Create campaign error: {str(e)}")
        if request.is_json:
            return jsonify({"success": False, "error": str(e)}), 500
        else:
            flash(f"Error creating campaign: {str(e)}", 'error')
            return render_template('admin/create_campaign.html', 
                                 page_title="Create Campaign")


@admin_bp.route('/campaigns/<campaign_id>')
def campaign_details(campaign_id: str):
    """Campaign details page."""
    try:
        admin_controller = get_admin_controller()
        
        # Get campaign details
        result = admin_controller.get_campaign_details(campaign_id)
        
        if not result['success']:
            flash(f"Campaign not found: {result.get('error')}", 'error')
            return redirect(url_for('admin.campaigns_list'))
        
        campaign_data = result['campaign']
        interaction_stats = result.get('interaction_stats')
        content_metrics = result.get('content_metrics')
        
        return render_template('admin/campaign_details.html',
                             campaign=campaign_data,
                             interaction_stats=interaction_stats,
                             content_metrics=content_metrics,
                             page_title=f"Campaign: {campaign_data['name']}")
        
    except Exception as e:
        logger.error(f"Campaign details error: {str(e)}")
        return render_template('admin/error.html', 
                             error=str(e), 
                             page_title="Campaign Error"), 500


@admin_bp.route('/campaigns/<campaign_id>/trigger', methods=['POST'])
def trigger_campaign(campaign_id: str):
    """Manually trigger a campaign."""
    try:
        admin_controller = get_admin_controller()
        
        data = request.get_json() if request.is_json else request.form
        target_audience = data.get('target_audience', 'all')
        
        result = admin_controller.trigger_campaign_manual(
            campaign_id=campaign_id,
            target_audience=target_audience,
            triggered_by=request.remote_addr
        )
        
        if request.is_json:
            return jsonify(result)
        else:
            if result['success']:
                flash("Campaign triggered successfully!", 'success')
            else:
                flash(f"Failed to trigger campaign: {result.get('error')}", 'error')
            
            return redirect(url_for('admin.campaign_details', campaign_id=campaign_id))
        
    except Exception as e:
        logger.error(f"Trigger campaign error: {str(e)}")
        if request.is_json:
            return jsonify({"success": False, "error": str(e)}), 500
        else:
            flash(f"Error triggering campaign: {str(e)}", 'error')
            return redirect(url_for('admin.campaign_details', campaign_id=campaign_id))


@admin_bp.route('/campaigns/<campaign_id>/pause', methods=['POST'])
def pause_campaign(campaign_id: str):
    """Pause a campaign."""
    try:
        admin_controller = get_admin_controller()
        
        result = admin_controller.pause_campaign(
            campaign_id=campaign_id,
            paused_by=request.remote_addr
        )
        
        if request.is_json:
            return jsonify(result)
        else:
            if result['success']:
                flash("Campaign paused successfully!", 'success')
            else:
                flash(f"Failed to pause campaign: {result.get('error')}", 'error')
            
            return redirect(url_for('admin.campaign_details', campaign_id=campaign_id))
        
    except Exception as e:
        logger.error(f"Pause campaign error: {str(e)}")
        if request.is_json:
            return jsonify({"success": False, "error": str(e)}), 500
        else:
            flash(f"Error pausing campaign: {str(e)}", 'error')
            return redirect(url_for('admin.campaign_details', campaign_id=campaign_id))


@admin_bp.route('/analytics')
def analytics_dashboard():
    """Analytics dashboard page."""
    try:
        admin_controller = get_admin_controller()
        
        # Get time period from query params
        days = int(request.args.get('days', 7))
        days = max(1, min(days, 90))  # Limit to reasonable range
        
        # Get analytics data
        dashboard_result = admin_controller.get_analytics_dashboard(days=days)
        
        if dashboard_result['success']:
            analytics_data = dashboard_result['dashboard_data']
        else:
            analytics_data = {"error": dashboard_result.get('error')}
            flash(f"Error loading analytics: {dashboard_result.get('error')}", 'error')
        
        return render_template('admin/analytics.html',
                             analytics_data=analytics_data,
                             selected_days=days,
                             page_title="Analytics Dashboard")
        
    except Exception as e:
        logger.error(f"Analytics dashboard error: {str(e)}")
        return render_template('admin/error.html', 
                             error=str(e), 
                             page_title="Analytics Error"), 500


@admin_bp.route('/system/health')
def system_health():
    """System health monitoring page."""
    try:
        admin_controller = get_admin_controller()
        
        # Get health status
        health_status = admin_controller.check_system_health()
        
        return render_template('admin/system_health.html',
                             health_status=health_status.__dict__,
                             page_title="System Health")
        
    except Exception as e:
        logger.error(f"System health error: {str(e)}")
        return render_template('admin/error.html', 
                             error=str(e), 
                             page_title="System Health Error"), 500


@admin_bp.route('/system/cleanup', methods=['POST'])
def system_cleanup():
    """System data cleanup."""
    try:
        admin_controller = get_admin_controller()
        
        data = request.get_json() if request.is_json else request.form
        days_to_keep = int(data.get('days_to_keep', 30))
        days_to_keep = max(7, min(days_to_keep, 365))  # Reasonable limits
        
        result = admin_controller.cleanup_old_data(days_to_keep=days_to_keep)
        
        if request.is_json:
            return jsonify(result)
        else:
            if result['success']:
                cleanup_results = result['cleanup_results']
                flash(f"Cleanup completed: {cleanup_results}", 'success')
            else:
                flash(f"Cleanup failed: {result.get('error')}", 'error')
            
            return redirect(url_for('admin.system_health'))
        
    except Exception as e:
        logger.error(f"System cleanup error: {str(e)}")
        if request.is_json:
            return jsonify({"success": False, "error": str(e)}), 500
        else:
            flash(f"Cleanup error: {str(e)}", 'error')
            return redirect(url_for('admin.system_health'))


# API Routes for programmatic access

@admin_bp.route('/api/campaigns', methods=['GET'])
def api_get_campaigns():
    """API: Get campaigns list."""
    try:
        admin_controller = get_admin_controller()
        
        status_filter = request.args.get('status')
        if status_filter:
            try:
                status_filter = CampaignStatus(status_filter)
            except ValueError:
                return jsonify({"error": "Invalid status filter"}), 400
        
        limit = request.args.get('limit', type=int)
        
        result = admin_controller.get_campaign_list(
            status_filter=status_filter,
            limit=limit
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"API get campaigns error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route('/api/campaigns', methods=['POST'])
def api_create_campaign():
    """API: Create new campaign."""
    try:
        admin_controller = get_admin_controller()
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON data required"}), 400
        
        # Extract required fields
        required_fields = ['name', 'content_title', 'content_message']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"Field '{field}' is required"}), 400
        
        result = admin_controller.create_campaign(
            name=data['name'],
            description=data.get('description', ''),
            content_title=data['content_title'],
            content_message=data['content_message'],
            created_by=data.get('created_by', 'api'),
            **{k: v for k, v in data.items() if k not in required_fields + ['description', 'created_by']}
        )
        
        return jsonify(result), 201 if result['success'] else 400
        
    except Exception as e:
        logger.error(f"API create campaign error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route('/api/campaigns/<campaign_id>', methods=['GET'])
def api_get_campaign(campaign_id: str):
    """API: Get campaign details."""
    try:
        admin_controller = get_admin_controller()
        result = admin_controller.get_campaign_details(campaign_id)
        
        return jsonify(result), 200 if result['success'] else 404
        
    except Exception as e:
        logger.error(f"API get campaign error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route('/api/campaigns/<campaign_id>/trigger', methods=['POST'])
def api_trigger_campaign(campaign_id: str):
    """API: Trigger campaign."""
    try:
        admin_controller = get_admin_controller()
        
        data = request.get_json() or {}
        result = admin_controller.trigger_campaign_manual(
            campaign_id=campaign_id,
            target_audience=data.get('target_audience', 'all'),
            triggered_by=data.get('triggered_by', 'api')
        )
        
        return jsonify(result), 200 if result['success'] else 400
        
    except Exception as e:
        logger.error(f"API trigger campaign error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route('/api/analytics/dashboard')
def api_analytics_dashboard():
    """API: Get analytics dashboard data."""
    try:
        admin_controller = get_admin_controller()
        
        days = int(request.args.get('days', 7))
        days = max(1, min(days, 90))
        
        result = admin_controller.get_analytics_dashboard(days=days)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"API analytics dashboard error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route('/api/system/health')
def api_system_health():
    """API: Get system health status."""
    try:
        admin_controller = get_admin_controller()
        health_status = admin_controller.check_system_health()
        
        return jsonify({
            "success": True,
            "health_status": health_status.__dict__
        })
        
    except Exception as e:
        logger.error(f"API system health error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route('/api/system/cleanup', methods=['POST'])
def api_system_cleanup():
    """API: Perform system cleanup."""
    try:
        admin_controller = get_admin_controller()
        
        data = request.get_json() or {}
        days_to_keep = int(data.get('days_to_keep', 30))
        days_to_keep = max(7, min(days_to_keep, 365))
        
        result = admin_controller.cleanup_old_data(days_to_keep=days_to_keep)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"API system cleanup error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# Error handlers for admin blueprint

@admin_bp.errorhandler(404)
def admin_not_found(error):
    """Handle 404 errors in admin section."""
    if request.path.startswith('/admin/api/'):
        return jsonify({"error": "API endpoint not found"}), 404
    return render_template('admin/error.html', 
                         error="Page not found", 
                         page_title="Not Found"), 404


@admin_bp.errorhandler(500)
def admin_server_error(error):
    """Handle 500 errors in admin section."""
    if request.path.startswith('/admin/api/'):
        return jsonify({"error": "Internal server error"}), 500
    return render_template('admin/error.html', 
                         error="Internal server error", 
                         page_title="Server Error"), 500


@admin_bp.route('/health/azure-openai')
def azure_openai_health():
    """
    Health check endpoint for Azure OpenAI API capabilities and status.
    
    Returns current API capabilities, routing status, and performance metrics.
    """
    try:
        from src.config.centralized_config import get_config
        from src.utils.capability_cache import get_capability_cache
        import json
        from pathlib import Path
        
        start_time = time.time()
        config = get_config()
        
        # Get cached capabilities
        capability_cache = get_capability_cache()
        cache_file = Path("data/api_capabilities.json")
        
        capabilities = {
            'responses_api_available': False,
            'chat_completions_available': True,
            'models_api_available': False,
            'last_updated': None,
            'cache_age_seconds': None,
            'cache_source': 'default'
        }
        
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                    
                capabilities.update(cache_data.get('capabilities', {}))
                capabilities['last_updated'] = cache_data.get('last_updated')
                capabilities['cache_age_seconds'] = cache_data.get('ttl_seconds', 300)
                capabilities['cache_source'] = 'file'
                
                # Calculate actual age
                if capabilities['last_updated']:
                    from datetime import datetime
                    last_updated = datetime.fromisoformat(capabilities['last_updated'])
                    age = (datetime.now() - last_updated).total_seconds()
                    capabilities['actual_age_seconds'] = age
                    
            except Exception as e:
                logger.warning(f"Could not read capability cache: {e}")
        
        # Get configuration status
        config_status = {
            'prefer_responses_api': config.azure_openai.prefer_responses_api,
            'force_chat_completions': config.azure_openai.force_chat_completions,
            'enable_startup_validation': config.azure_openai.enable_startup_validation,
            'capability_cache_ttl': config.azure_openai.capability_cache_ttl,
            'deployment_name': config.azure_openai.deployment_name[:20] + "..." if len(config.azure_openai.deployment_name) > 20 else config.azure_openai.deployment_name,
            'endpoint_configured': bool(config.azure_openai.endpoint)
        }
        
        # Determine current routing decision
        routing_status = "unknown"
        if config.azure_openai.force_chat_completions:
            routing_status = "forced_chat_completions"
        elif capabilities['responses_api_available'] and config.azure_openai.prefer_responses_api:
            routing_status = "prefer_responses_api"
        else:
            routing_status = "default_chat_completions"
        
        # Calculate response time
        response_time_ms = (time.time() - start_time) * 1000
        
        response_data = {
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'capabilities': capabilities,
            'configuration': config_status,
            'routing_status': routing_status,
            'performance': {
                'health_check_time_ms': round(response_time_ms, 2),
                'cache_access_time_ms': round((time.time() - start_time) * 1000, 2)
            },
            'system_info': {
                'intelligent_routing_enabled': True,
                'capability_detection_enabled': True,
                'cache_file_exists': cache_file.exists(),
                'cache_file_path': str(cache_file)
            }
        }
        
        # Set appropriate HTTP status based on capabilities
        if capabilities['responses_api_available'] or capabilities['chat_completions_available']:
            return jsonify(response_data), 200
        else:
            response_data['status'] = 'degraded'
            return jsonify(response_data), 206  # Partial Content
            
    except Exception as e:
        logger.error(f"Azure OpenAI health check failed: {e}")
        return jsonify({
            'status': 'error',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': str(e),
            'health_check_failed': True
        }), 500
-- Rich Message Automation System - Database Initialization
-- This script initializes the PostgreSQL database for production use

-- Create database if it doesn't exist (this will be handled by Docker)
-- CREATE DATABASE rich_message_db;

-- Connect to the database
\c rich_message_db;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS admin;
CREATE SCHEMA IF NOT EXISTS monitoring;

-- Create analytics tables
CREATE TABLE IF NOT EXISTS analytics.engagement_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    content_id VARCHAR(255) NOT NULL,
    interaction_type VARCHAR(100) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    additional_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    INDEX idx_engagement_metrics_user_id (user_id),
    INDEX idx_engagement_metrics_content_id (content_id),
    INDEX idx_engagement_metrics_timestamp (timestamp),
    INDEX idx_engagement_metrics_interaction_type (interaction_type)
);

CREATE TABLE IF NOT EXISTS analytics.message_delivery_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    content_category VARCHAR(100) NOT NULL,
    template_id VARCHAR(255),
    delivery_time_ms INTEGER,
    delivery_status VARCHAR(50) NOT NULL DEFAULT 'delivered',
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    metadata JSONB,
    
    INDEX idx_delivery_logs_user_id (user_id),
    INDEX idx_delivery_logs_timestamp (timestamp),
    INDEX idx_delivery_logs_status (delivery_status)
);

CREATE TABLE IF NOT EXISTS analytics.system_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(255) NOT NULL,
    metric_value DECIMAL(15,4),
    metric_type VARCHAR(100) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    tags JSONB,
    
    INDEX idx_system_metrics_name (metric_name),
    INDEX idx_system_metrics_timestamp (timestamp),
    INDEX idx_system_metrics_type (metric_type)
);

-- Create admin tables
CREATE TABLE IF NOT EXISTS admin.campaigns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    content_title VARCHAR(500) NOT NULL,
    content_message TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    scheduled_time TIMESTAMP WITH TIME ZONE,
    target_audience VARCHAR(255),
    image_url TEXT,
    template_id VARCHAR(255),
    content_category VARCHAR(100),
    include_interactions BOOLEAN DEFAULT true,
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    total_sent INTEGER DEFAULT 0,
    total_delivered INTEGER DEFAULT 0,
    total_opened INTEGER DEFAULT 0,
    total_interactions INTEGER DEFAULT 0,
    
    INDEX idx_campaigns_campaign_id (campaign_id),
    INDEX idx_campaigns_status (status),
    INDEX idx_campaigns_created_at (created_at),
    INDEX idx_campaigns_scheduled_time (scheduled_time)
);

CREATE TABLE IF NOT EXISTS admin.admin_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) UNIQUE NOT NULL,
    admin_user VARCHAR(255) NOT NULL,
    login_time TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_activity TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT,
    permissions JSONB,
    is_active BOOLEAN DEFAULT true,
    
    INDEX idx_admin_sessions_session_id (session_id),
    INDEX idx_admin_sessions_admin_user (admin_user),
    INDEX idx_admin_sessions_last_activity (last_activity)
);

-- Create monitoring tables
CREATE TABLE IF NOT EXISTS monitoring.health_checks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    check_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    response_time_ms INTEGER,
    error_message TEXT,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    metadata JSONB,
    
    INDEX idx_health_checks_name (check_name),
    INDEX idx_health_checks_timestamp (timestamp),
    INDEX idx_health_checks_status (status)
);

CREATE TABLE IF NOT EXISTS monitoring.error_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    error_level VARCHAR(50) NOT NULL,
    error_message TEXT NOT NULL,
    error_traceback TEXT,
    component VARCHAR(255),
    user_id VARCHAR(255),
    request_id VARCHAR(255),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    context JSONB,
    
    INDEX idx_error_logs_level (error_level),
    INDEX idx_error_logs_timestamp (timestamp),
    INDEX idx_error_logs_component (component)
);

-- Create functions for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for automatic timestamp updates
CREATE TRIGGER update_campaigns_updated_at 
    BEFORE UPDATE ON admin.campaigns 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create views for common queries
CREATE OR REPLACE VIEW analytics.user_engagement_summary AS
SELECT 
    user_id,
    COUNT(*) as total_interactions,
    COUNT(DISTINCT content_id) as unique_content_interacted,
    COUNT(DISTINCT DATE(timestamp)) as active_days,
    MIN(timestamp) as first_interaction,
    MAX(timestamp) as last_interaction,
    array_agg(DISTINCT interaction_type) as interaction_types
FROM analytics.engagement_metrics 
GROUP BY user_id;

CREATE OR REPLACE VIEW analytics.content_performance AS
SELECT 
    content_id,
    COUNT(*) as total_interactions,
    COUNT(DISTINCT user_id) as unique_users,
    array_agg(DISTINCT interaction_type) as interaction_types,
    MIN(timestamp) as first_interaction,
    MAX(timestamp) as last_interaction,
    COUNT(*) * 1.0 / COUNT(DISTINCT user_id) as avg_interactions_per_user
FROM analytics.engagement_metrics 
GROUP BY content_id;

CREATE OR REPLACE VIEW admin.campaign_summary AS
SELECT 
    c.*,
    CASE 
        WHEN c.total_sent > 0 THEN (c.total_delivered * 100.0 / c.total_sent)
        ELSE 0 
    END as delivery_rate,
    CASE 
        WHEN c.total_delivered > 0 THEN (c.total_opened * 100.0 / c.total_delivered)
        ELSE 0 
    END as open_rate,
    CASE 
        WHEN c.total_opened > 0 THEN (c.total_interactions * 100.0 / c.total_opened)
        ELSE 0 
    END as interaction_rate
FROM admin.campaigns c;

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_engagement_metrics_user_timestamp 
    ON analytics.engagement_metrics (user_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_engagement_metrics_content_timestamp 
    ON analytics.engagement_metrics (content_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_delivery_logs_user_timestamp 
    ON analytics.message_delivery_logs (user_id, timestamp DESC);

-- Create partitioning for large tables (optional, for high-volume deployments)
-- Uncomment if you expect high data volumes

-- CREATE TABLE analytics.engagement_metrics_2024 PARTITION OF analytics.engagement_metrics
--     FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

-- CREATE TABLE analytics.message_delivery_logs_2024 PARTITION OF analytics.message_delivery_logs
--     FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

-- Grant permissions
GRANT USAGE ON SCHEMA analytics TO postgres;
GRANT USAGE ON SCHEMA admin TO postgres;
GRANT USAGE ON SCHEMA monitoring TO postgres;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA analytics TO postgres;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA admin TO postgres;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA monitoring TO postgres;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA analytics TO postgres;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA admin TO postgres;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA monitoring TO postgres;

-- Insert initial data
INSERT INTO monitoring.health_checks (check_name, status, response_time_ms) 
VALUES ('database_initialization', 'healthy', 0)
ON CONFLICT DO NOTHING;

-- Create stored procedures for common operations
CREATE OR REPLACE FUNCTION analytics.get_user_engagement_stats(
    p_user_id VARCHAR(255),
    p_days_back INTEGER DEFAULT 30
)
RETURNS TABLE (
    total_interactions BIGINT,
    unique_content BIGINT,
    avg_daily_interactions NUMERIC,
    most_common_interaction VARCHAR(100)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*) as total_interactions,
        COUNT(DISTINCT content_id) as unique_content,
        ROUND(COUNT(*) * 1.0 / GREATEST(p_days_back, 1), 2) as avg_daily_interactions,
        (SELECT interaction_type 
         FROM analytics.engagement_metrics em2 
         WHERE em2.user_id = p_user_id 
           AND em2.timestamp >= NOW() - INTERVAL '1 day' * p_days_back
         GROUP BY interaction_type 
         ORDER BY COUNT(*) DESC 
         LIMIT 1) as most_common_interaction
    FROM analytics.engagement_metrics em
    WHERE em.user_id = p_user_id
      AND em.timestamp >= NOW() - INTERVAL '1 day' * p_days_back;
END;
$$ LANGUAGE plpgsql;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Rich Message Automation System database initialized successfully';
    RAISE NOTICE 'Created schemas: analytics, admin, monitoring';
    RAISE NOTICE 'Created tables, indexes, views, and functions';
    RAISE NOTICE 'Database is ready for production use';
END $$;
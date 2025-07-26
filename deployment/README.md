# Rich Message Automation System - Deployment Guide

This directory contains all the necessary files and scripts for deploying the Rich Message Automation System to production environments.

## 🚀 Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- At least 4GB RAM and 20GB disk space
- SSL certificates (for HTTPS)

### Basic Deployment

1. **Copy environment configuration:**
   ```bash
   cp config/production.env.example config/production.env
   ```

2. **Edit configuration:**
   ```bash
   nano config/production.env
   ```
   Fill in your actual values for:
   - LINE Bot credentials
   - Azure OpenAI credentials
   - Database passwords
   - Domain names

3. **Deploy:**
   ```bash
   ./scripts/deploy.sh
   ```

## 📁 Directory Structure

```
deployment/
├── Dockerfile                 # Production Docker image
├── docker-compose.yml        # Main services configuration
├── README.md                 # This file
├── config/
│   ├── production.env.example # Environment template
│   ├── nginx.conf            # Nginx reverse proxy config
│   └── prometheus.yml        # Monitoring configuration
└── scripts/
    ├── deploy.sh             # Main deployment script
    ├── backup.sh             # Backup script
    ├── entrypoint.sh         # Docker entrypoint
    └── init-db.sql           # Database initialization
```

## 🔧 Configuration

### Environment Variables

Key environment variables that must be configured:

| Variable | Description | Required |
|----------|-------------|----------|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Bot API access token | Yes |
| `LINE_CHANNEL_SECRET` | LINE webhook signature key | Yes |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | Yes |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | Yes |
| `POSTGRES_PASSWORD` | PostgreSQL database password | Yes |
| `REDIS_PASSWORD` | Redis password | Yes |
| `SECRET_KEY` | Flask secret key | Yes |

### SSL/TLS Configuration

For production deployments with HTTPS:

1. Place your SSL certificates in `config/ssl/`:
   ```
   config/ssl/
   ├── cert.pem
   └── key.pem
   ```

2. Update domain name in `config/nginx.conf`:
   ```nginx
   server_name your-domain.com;
   ```

## 🐳 Services

The deployment includes the following services:

### Core Services
- **app**: Main Flask application
- **postgres**: PostgreSQL database
- **redis**: Redis cache and session store
- **nginx**: Reverse proxy and SSL termination

### Optional Services
- **prometheus**: Metrics collection
- **grafana**: Monitoring dashboards
- **fluentd**: Log aggregation

## 📋 Deployment Commands

### Standard Deployment
```bash
./scripts/deploy.sh
```

### Environment-Specific Deployment
```bash
./scripts/deploy.sh -e staging
```

### Fresh Build (No Cache)
```bash
./scripts/deploy.sh -f
```

### Skip Tests and Backup
```bash
./scripts/deploy.sh -t -s
```

## 💾 Backup and Recovery

### Create Backup
```bash
./scripts/backup.sh
```

### Full Backup with Custom Retention
```bash
./scripts/backup.sh --full --retention 7
```

### Backup to Custom Directory
```bash
./scripts/backup.sh -d /backup/path
```

### Restore from Backup
```bash
# Stop services
docker-compose down

# Restore database
gunzip < backups/20241201_120000/database_backup.sql.gz | \
  docker-compose exec -T postgres psql -U postgres -d rich_message_db

# Restore Redis
gunzip < backups/20241201_120000/redis_backup.rdb.gz > /tmp/dump.rdb
docker cp /tmp/dump.rdb rich-message-redis:/data/dump.rdb

# Start services
docker-compose up -d
```

## 📊 Monitoring

### Health Checks

- Application health: `http://your-domain.com/health`
- Service status: `docker-compose ps`
- Resource usage: `docker stats`

### Prometheus Metrics

Access Prometheus at `http://your-domain.com:9090`

Key metrics to monitor:
- `flask_http_request_total`
- `flask_http_request_duration_seconds`
- `line_api_requests_total`
- `rich_message_creation_total`
- `user_interactions_total`

### Grafana Dashboards

Access Grafana at `http://your-domain.com:3000`

Default login: `admin` / `(configured password)`

## 🔧 Maintenance

### View Logs
```bash
# Application logs
docker-compose logs -f app

# All services
docker-compose logs -f

# Specific timeframe
docker-compose logs --since="1h" app
```

### Update Application
```bash
# Pull latest changes
git pull

# Rebuild and deploy
./scripts/deploy.sh -f
```

### Scale Services
```bash
# Scale application instances
docker-compose up -d --scale app=3
```

### Database Maintenance
```bash
# Connect to database
docker-compose exec postgres psql -U postgres -d rich_message_db

# Run database cleanup
docker-compose exec postgres psql -U postgres -d rich_message_db -c "
DELETE FROM analytics.engagement_metrics 
WHERE timestamp < NOW() - INTERVAL '90 days';
"
```

## 🛡️ Security

### Security Checklist

- [ ] Change all default passwords
- [ ] Use strong SECRET_KEY
- [ ] Configure SSL certificates
- [ ] Set up firewall rules
- [ ] Enable log monitoring
- [ ] Configure backup encryption
- [ ] Set up intrusion detection
- [ ] Regular security updates

### Firewall Configuration

```bash
# Allow SSH (if needed)
ufw allow 22

# Allow HTTP/HTTPS
ufw allow 80
ufw allow 443

# Allow monitoring (if external access needed)
ufw allow 3000  # Grafana
ufw allow 9090  # Prometheus

# Enable firewall
ufw enable
```

## 🚨 Troubleshooting

### Common Issues

1. **Services won't start**
   ```bash
   # Check logs
   docker-compose logs
   
   # Check disk space
   df -h
   
   # Check memory
   free -h
   ```

2. **Database connection errors**
   ```bash
   # Check PostgreSQL status
   docker-compose exec postgres pg_isready
   
   # Reset database
   docker-compose down
   docker volume rm rich-message-production_postgres_data
   docker-compose up -d
   ```

3. **SSL certificate issues**
   ```bash
   # Verify certificate files
   openssl x509 -in config/ssl/cert.pem -text -noout
   
   # Test certificate validity
   openssl verify config/ssl/cert.pem
   ```

4. **High memory usage**
   ```bash
   # Monitor resource usage
   docker stats
   
   # Restart services
   docker-compose restart
   
   # Scale down if needed
   docker-compose up -d --scale app=1
   ```

### Performance Tuning

1. **Database optimization**
   ```sql
   -- Analyze database performance
   SELECT * FROM pg_stat_activity;
   
   -- Optimize tables
   VACUUM ANALYZE;
   ```

2. **Redis optimization**
   ```bash
   # Check Redis memory usage
   docker-compose exec redis redis-cli info memory
   
   # Clear cache if needed
   docker-compose exec redis redis-cli flushall
   ```

3. **Application tuning**
   - Adjust `GUNICORN_WORKERS` in environment config
   - Monitor response times in Grafana
   - Scale horizontally if needed

## 📞 Support

For deployment issues:

1. Check the logs: `docker-compose logs`
2. Verify configuration: `docker-compose config`
3. Test connectivity: `curl -f http://localhost:5000/health`
4. Review this documentation
5. Check application logs in `/app/logs`

## 🔄 Updates and Maintenance

### Regular Maintenance Tasks

- Daily: Monitor logs and metrics
- Weekly: Review backup integrity
- Monthly: Update dependencies and security patches
- Quarterly: Review and update configurations

### Update Procedure

1. Create backup: `./scripts/backup.sh`
2. Test in staging environment
3. Deploy during maintenance window
4. Verify all services are healthy
5. Monitor for 24 hours post-deployment
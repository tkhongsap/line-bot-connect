#!/bin/bash

# Rich Message Automation System - Backup Script
set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$DEPLOYMENT_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
ENVIRONMENT="${ENVIRONMENT:-production}"

# Timestamp for backup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FOLDER="$BACKUP_DIR/$TIMESTAMP"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Help function
show_help() {
    cat << EOF
Rich Message Automation System Backup Script

Usage: $0 [OPTIONS]

OPTIONS:
    -e, --environment ENV    Environment to backup (production, staging, development)
    -d, --backup-dir DIR     Backup directory (default: deployment/backups)
    -r, --retention DAYS     Retention period in days (default: 30)
    -f, --full              Full backup including logs and temporary files
    -q, --quiet             Quiet mode (minimal output)
    -h, --help              Show this help message

EXAMPLES:
    $0                                    # Standard backup
    $0 -e staging -d /backup/staging      # Backup staging to custom directory
    $0 --full --retention 7               # Full backup with 7-day retention

EOF
}

# Parse command line arguments
FULL_BACKUP=false
QUIET_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -d|--backup-dir)
            BACKUP_DIR="$2"
            shift 2
            ;;
        -r|--retention)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        -f|--full)
            FULL_BACKUP=true
            shift
            ;;
        -q|--quiet)
            QUIET_MODE=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate inputs
if [[ ! "$RETENTION_DAYS" =~ ^[0-9]+$ ]] || [[ "$RETENTION_DAYS" -lt 1 ]]; then
    log_error "Invalid retention days: $RETENTION_DAYS. Must be a positive integer."
    exit 1
fi

# Create backup directory
mkdir -p "$BACKUP_FOLDER"

# Change to deployment directory
cd "$DEPLOYMENT_DIR"

# Set Docker Compose project name
export COMPOSE_PROJECT_NAME="rich-message-${ENVIRONMENT}"

log_info "Starting backup for $ENVIRONMENT environment..."
log_info "Backup location: $BACKUP_FOLDER"

# Check if services are running
if ! docker-compose ps | grep -q "Up"; then
    log_warn "No running containers found. Some backups may not be possible."
fi

# Backup database
log_info "Backing up PostgreSQL database..."
if docker-compose exec -T postgres pg_isready -U "${POSTGRES_USER:-postgres}" > /dev/null 2>&1; then
    # Create database backup
    if docker-compose exec -T postgres pg_dump \
        -U "${POSTGRES_USER:-postgres}" \
        -h localhost \
        "${POSTGRES_DB:-rich_message_db}" \
        --no-owner --no-privileges --clean --if-exists \
        > "$BACKUP_FOLDER/database_backup.sql" 2>/dev/null; then
        
        # Compress database backup
        gzip "$BACKUP_FOLDER/database_backup.sql"
        log_success "Database backup completed: database_backup.sql.gz"
    else
        log_error "Database backup failed"
    fi
    
    # Backup database schema only
    if docker-compose exec -T postgres pg_dump \
        -U "${POSTGRES_USER:-postgres}" \
        -h localhost \
        "${POSTGRES_DB:-rich_message_db}" \
        --schema-only --no-owner --no-privileges \
        > "$BACKUP_FOLDER/schema_backup.sql" 2>/dev/null; then
        
        gzip "$BACKUP_FOLDER/schema_backup.sql"
        log_success "Schema backup completed: schema_backup.sql.gz"
    else
        log_warn "Schema backup failed"
    fi
else
    log_warn "PostgreSQL is not accessible. Skipping database backup."
fi

# Backup Redis data
log_info "Backing up Redis data..."
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    # Create Redis backup
    if docker-compose exec -T redis redis-cli --rdb /tmp/dump.rdb > /dev/null 2>&1; then
        # Copy Redis backup from container
        if docker cp "rich-message-redis:/tmp/dump.rdb" "$BACKUP_FOLDER/redis_backup.rdb" 2>/dev/null; then
            gzip "$BACKUP_FOLDER/redis_backup.rdb"
            log_success "Redis backup completed: redis_backup.rdb.gz"
        else
            log_warn "Failed to copy Redis backup from container"
        fi
    else
        log_warn "Redis backup creation failed"
    fi
    
    # Backup Redis configuration
    if docker-compose exec -T redis cat /usr/local/etc/redis/redis.conf > "$BACKUP_FOLDER/redis_config.conf" 2>/dev/null; then
        log_success "Redis configuration backed up"
    else
        log_warn "Redis configuration backup failed"
    fi
else
    log_warn "Redis is not accessible. Skipping Redis backup."
fi

# Backup application data
log_info "Backing up application data..."

# Backup application logs
if docker-compose ps | grep -q "app.*Up"; then
    mkdir -p "$BACKUP_FOLDER/app_data"
    
    # Copy application logs
    if docker cp "rich-message-app:/app/logs" "$BACKUP_FOLDER/app_data/" 2>/dev/null; then
        log_success "Application logs backed up"
    else
        log_warn "Application logs backup failed"
    fi
    
    # Copy application data directory
    if docker cp "rich-message-app:/app/data" "$BACKUP_FOLDER/app_data/" 2>/dev/null; then
        log_success "Application data backed up"
    else
        log_warn "Application data backup failed"
    fi
    
    # Backup environment configuration (without secrets)
    if [[ -f "config/${ENVIRONMENT}.env" ]]; then
        # Create sanitized config backup (remove sensitive values)
        grep -E '^[^=]+=' "config/${ENVIRONMENT}.env" | \
        sed -E 's/(PASSWORD|SECRET|KEY|TOKEN)=.*/\1=***REDACTED***/' \
        > "$BACKUP_FOLDER/config_${ENVIRONMENT}.env"
        log_success "Configuration backed up (secrets redacted)"
    fi
else
    log_warn "Application container not running. Skipping application data backup."
fi

# Backup Docker Compose configuration
log_info "Backing up Docker Compose configuration..."
cp docker-compose.yml "$BACKUP_FOLDER/"
if [[ -f "docker-compose.${ENVIRONMENT}.yml" ]]; then
    cp "docker-compose.${ENVIRONMENT}.yml" "$BACKUP_FOLDER/"
fi
log_success "Docker Compose configuration backed up"

# Backup monitoring data (if enabled)
if docker-compose ps | grep -q "prometheus.*Up"; then
    log_info "Backing up Prometheus data..."
    mkdir -p "$BACKUP_FOLDER/monitoring"
    
    # Backup Prometheus configuration
    if docker cp "rich-message-prometheus:/etc/prometheus/prometheus.yml" "$BACKUP_FOLDER/monitoring/" 2>/dev/null; then
        log_success "Prometheus configuration backed up"
    fi
    
    # Backup Prometheus data (snapshot)
    if docker-compose exec -T prometheus promtool tsdb create-blocks-from openmetrics /tmp/backup.txt < /dev/null 2>/dev/null; then
        log_success "Prometheus data snapshot created"
    else
        log_warn "Prometheus data backup failed"
    fi
fi

if docker-compose ps | grep -q "grafana.*Up"; then
    log_info "Backing up Grafana data..."
    
    # Backup Grafana dashboards and datasources
    if docker cp "rich-message-grafana:/var/lib/grafana" "$BACKUP_FOLDER/monitoring/grafana_data" 2>/dev/null; then
        log_success "Grafana data backed up"
    else
        log_warn "Grafana data backup failed"
    fi
fi

# Full backup additional items
if [[ "$FULL_BACKUP" == "true" ]]; then
    log_info "Performing full backup (including logs and temporary files)..."
    
    # Backup Nginx logs
    if docker-compose ps | grep -q "nginx.*Up"; then
        mkdir -p "$BACKUP_FOLDER/nginx_logs"
        if docker cp "rich-message-nginx:/var/log/nginx" "$BACKUP_FOLDER/nginx_logs/" 2>/dev/null; then
            log_success "Nginx logs backed up"
        fi
    fi
    
    # Backup all Docker volumes
    docker-compose config --volumes | while read volume; do
        if docker volume inspect "rich-message-${ENVIRONMENT}_${volume}" > /dev/null 2>&1; then
            log_info "Backing up volume: $volume"
            docker run --rm \
                -v "rich-message-${ENVIRONMENT}_${volume}:/source:ro" \
                -v "$BACKUP_FOLDER:/backup" \
                alpine tar czf "/backup/volume_${volume}.tar.gz" -C /source . 2>/dev/null || \
                log_warn "Failed to backup volume: $volume"
        fi
    done
fi

# Create backup manifest
log_info "Creating backup manifest..."
cat > "$BACKUP_FOLDER/backup_manifest.json" << EOF
{
    "backup_timestamp": "$TIMESTAMP",
    "environment": "$ENVIRONMENT",
    "backup_type": "$(if [[ "$FULL_BACKUP" == "true" ]]; then echo "full"; else echo "standard"; fi)",
    "retention_days": $RETENTION_DAYS,
    "backup_size": "$(du -sh "$BACKUP_FOLDER" | cut -f1)",
    "files": [
$(find "$BACKUP_FOLDER" -type f -printf '        "%f",\n' | sed '$ s/,$//')
    ],
    "services_status": {
$(docker-compose ps --format json | jq -r '["        \"" + .Service + "\": \"" + .State + "\","] | @tsv' | sed '$ s/,$//')
    }
}
EOF

# Calculate backup size
BACKUP_SIZE=$(du -sh "$BACKUP_FOLDER" | cut -f1)
log_success "Backup manifest created"

# Compress entire backup (optional)
if command -v tar > /dev/null 2>&1; then
    log_info "Compressing backup archive..."
    cd "$BACKUP_DIR"
    tar czf "${TIMESTAMP}_backup.tar.gz" "$TIMESTAMP"
    if [[ $? -eq 0 ]]; then
        rm -rf "$TIMESTAMP"
        log_success "Backup compressed to: ${TIMESTAMP}_backup.tar.gz"
        BACKUP_SIZE=$(du -sh "${TIMESTAMP}_backup.tar.gz" | cut -f1)
    else
        log_warn "Backup compression failed. Keeping uncompressed backup."
    fi
    cd "$DEPLOYMENT_DIR"
fi

# Cleanup old backups
log_info "Cleaning up old backups (retention: $RETENTION_DAYS days)..."
find "$BACKUP_DIR" -name "*_backup.tar.gz" -type f -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
find "$BACKUP_DIR" -maxdepth 1 -type d -name "[0-9]*_[0-9]*" -mtime +$RETENTION_DAYS -exec rm -rf {} \; 2>/dev/null || true

REMAINING_BACKUPS=$(find "$BACKUP_DIR" -name "*backup*" -type f | wc -l)
log_success "Cleanup completed. $REMAINING_BACKUPS backups remaining."

# Backup verification
log_info "Verifying backup integrity..."
VERIFICATION_PASSED=true

# Verify database backup
if [[ -f "$BACKUP_DIR/${TIMESTAMP}_backup.tar.gz" ]]; then
    if tar -tzf "$BACKUP_DIR/${TIMESTAMP}_backup.tar.gz" > /dev/null 2>&1; then
        log_success "Backup archive integrity verified"
    else
        log_error "Backup archive is corrupted"
        VERIFICATION_PASSED=false
    fi
elif [[ -d "$BACKUP_FOLDER" ]]; then
    if [[ -f "$BACKUP_FOLDER/database_backup.sql.gz" ]]; then
        if gzip -t "$BACKUP_FOLDER/database_backup.sql.gz" 2>/dev/null; then
            log_success "Database backup integrity verified"
        else
            log_error "Database backup is corrupted"
            VERIFICATION_PASSED=false
        fi
    fi
fi

# Final status
echo ""
log_info "Backup Summary:"
echo "  Environment: $ENVIRONMENT"
echo "  Timestamp: $TIMESTAMP"
echo "  Location: $BACKUP_DIR"
echo "  Size: $BACKUP_SIZE"
echo "  Type: $(if [[ "$FULL_BACKUP" == "true" ]]; then echo "Full"; else echo "Standard"; fi)"
echo "  Retention: $RETENTION_DAYS days"
echo "  Verification: $(if [[ "$VERIFICATION_PASSED" == "true" ]]; then echo "Passed"; else echo "Failed"; fi)"

if [[ "$VERIFICATION_PASSED" == "true" ]]; then
    log_success "Backup completed successfully!"
    exit 0
else
    log_error "Backup completed with errors. Please check the backup integrity."
    exit 1
fi
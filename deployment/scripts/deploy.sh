#!/bin/bash

# Rich Message Automation System - Deployment Script
set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOYMENT_DIR="$PROJECT_ROOT/deployment"

# Default values
ENVIRONMENT="production"
BUILD_FRESH="false"
RUN_TESTS="true"
BACKUP_DATA="true"
HEALTH_CHECK_TIMEOUT=120

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
Rich Message Automation System Deployment Script

Usage: $0 [OPTIONS]

OPTIONS:
    -e, --environment ENV    Deployment environment (production, staging, development)
    -f, --fresh             Force fresh build (no cache)
    -t, --skip-tests        Skip running tests before deployment
    -s, --skip-backup       Skip data backup before deployment
    -h, --help              Show this help message

EXAMPLES:
    $0                                    # Deploy to production with defaults
    $0 -e staging -f                      # Fresh deploy to staging
    $0 --skip-tests --skip-backup         # Quick deploy without tests/backup

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -f|--fresh)
            BUILD_FRESH="true"
            shift
            ;;
        -t|--skip-tests)
            RUN_TESTS="false"
            shift
            ;;
        -s|--skip-backup)
            BACKUP_DATA="false"
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

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(production|staging|development)$ ]]; then
    log_error "Invalid environment: $ENVIRONMENT. Must be one of: production, staging, development"
    exit 1
fi

log_info "Starting deployment to $ENVIRONMENT environment..."

# Change to project root
cd "$PROJECT_ROOT"

# Check if Docker and Docker Compose are available
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed or not in PATH"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    log_error "Docker Compose is not installed or not in PATH"
    exit 1
fi

# Check if environment configuration exists
ENV_FILE="$DEPLOYMENT_DIR/config/${ENVIRONMENT}.env"
if [[ ! -f "$ENV_FILE" ]]; then
    log_error "Environment configuration file not found: $ENV_FILE"
    log_info "Please create the environment file based on the example:"
    log_info "cp $DEPLOYMENT_DIR/config/production.env.example $ENV_FILE"
    exit 1
fi

# Run tests if requested
if [[ "$RUN_TESTS" == "true" ]]; then
    log_info "Running tests before deployment..."
    
    if [[ -f "$PROJECT_ROOT/scripts/run_tests.sh" ]]; then
        bash "$PROJECT_ROOT/scripts/run_tests.sh" all
        if [[ $? -ne 0 ]]; then
            log_error "Tests failed. Aborting deployment."
            exit 1
        fi
        log_success "All tests passed!"
    else
        log_warn "Test script not found. Skipping tests."
    fi
fi

# Backup existing data if requested
if [[ "$BACKUP_DATA" == "true" ]]; then
    log_info "Creating backup of existing data..."
    
    BACKUP_DIR="$DEPLOYMENT_DIR/backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # Check if containers are running
    if docker-compose -f "$DEPLOYMENT_DIR/docker-compose.yml" ps | grep -q "Up"; then
        # Backup database
        if docker-compose -f "$DEPLOYMENT_DIR/docker-compose.yml" exec -T postgres pg_dump -U "${POSTGRES_USER:-postgres}" "${POSTGRES_DB:-rich_message_db}" > "$BACKUP_DIR/database_backup.sql" 2>/dev/null; then
            log_success "Database backup created: $BACKUP_DIR/database_backup.sql"
        else
            log_warn "Database backup failed or no database found"
        fi
        
        # Backup Redis data
        if docker-compose -f "$DEPLOYMENT_DIR/docker-compose.yml" exec -T redis redis-cli --rdb /tmp/dump.rdb > /dev/null 2>&1; then
            docker cp rich-message-redis:/tmp/dump.rdb "$BACKUP_DIR/redis_backup.rdb" 2>/dev/null || log_warn "Redis backup failed"
        fi
        
        # Backup application logs
        docker cp rich-message-app:/app/logs "$BACKUP_DIR/app_logs" 2>/dev/null || log_warn "Application logs backup failed"
    else
        log_warn "No running containers found. Skipping data backup."
    fi
fi

# Build and deploy
log_info "Building Docker images..."

cd "$DEPLOYMENT_DIR"

# Set environment variables for Docker Compose
export COMPOSE_PROJECT_NAME="rich-message-${ENVIRONMENT}"
export COMPOSE_FILE="docker-compose.yml"

# Add environment-specific overrides if they exist
if [[ -f "docker-compose.${ENVIRONMENT}.yml" ]]; then
    export COMPOSE_FILE="docker-compose.yml:docker-compose.${ENVIRONMENT}.yml"
    log_info "Using environment-specific override: docker-compose.${ENVIRONMENT}.yml"
fi

# Build options
BUILD_ARGS=""
if [[ "$BUILD_FRESH" == "true" ]]; then
    BUILD_ARGS="--no-cache --pull"
    log_info "Performing fresh build (no cache)"
fi

# Stop existing services
log_info "Stopping existing services..."
docker-compose down --remove-orphans

# Build new images
docker-compose build $BUILD_ARGS

# Start services
log_info "Starting services..."
docker-compose up -d

# Wait for services to be healthy
log_info "Waiting for services to be healthy (timeout: ${HEALTH_CHECK_TIMEOUT}s)..."

TIMEOUT=$HEALTH_CHECK_TIMEOUT
while [[ $TIMEOUT -gt 0 ]]; do
    if docker-compose ps | grep -E "(healthy|starting)" | grep -qv "unhealthy"; then
        # Check if main app is responding
        if curl -f -s http://localhost:5000/health > /dev/null 2>&1; then
            log_success "Application is healthy and responding!"
            break
        fi
    fi
    
    sleep 5
    TIMEOUT=$((TIMEOUT - 5))
    
    if [[ $TIMEOUT -le 0 ]]; then
        log_error "Health check timeout. Application may not be ready."
        log_info "Current container status:"
        docker-compose ps
        log_info "Application logs:"
        docker-compose logs app | tail -20
        exit 1
    fi
    
    echo -n "."
done

echo ""

# Show deployment status
log_info "Deployment status:"
docker-compose ps

# Show running services
log_info "Service endpoints:"
echo "  Application: http://localhost:5000"
echo "  Health check: http://localhost:5000/health"
echo "  Admin dashboard: http://localhost:5000/admin"

if docker-compose ps | grep -q "grafana.*Up"; then
    echo "  Grafana monitoring: http://localhost:3000"
fi

if docker-compose ps | grep -q "prometheus.*Up"; then
    echo "  Prometheus metrics: http://localhost:9090"
fi

# Run post-deployment verification
log_info "Running post-deployment verification..."

# Test health endpoint
if curl -f -s http://localhost:5000/health | grep -q "healthy"; then
    log_success "Health endpoint is responding correctly"
else
    log_warn "Health endpoint is not responding as expected"
fi

# Test admin endpoint
if curl -f -s http://localhost:5000/ > /dev/null; then
    log_success "Admin dashboard is accessible"
else
    log_warn "Admin dashboard is not accessible"
fi

# Show resource usage
log_info "Resource usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Final success message
log_success "Deployment to $ENVIRONMENT completed successfully!"
log_info "To view logs: docker-compose logs -f"
log_info "To stop services: docker-compose down"
log_info "To update services: docker-compose pull && docker-compose up -d"

# Show next steps
cat << EOF

${GREEN}Next Steps:${NC}
1. Verify application functionality through the web interface
2. Check monitoring dashboards if enabled
3. Review application logs for any warnings
4. Test Rich Message creation and delivery
5. Set up monitoring alerts if needed

${YELLOW}Important Files:${NC}
- Environment config: $ENV_FILE
- Docker Compose: $DEPLOYMENT_DIR/docker-compose.yml
- Application logs: docker-compose logs app
- Backup location: $DEPLOYMENT_DIR/backups/

EOF
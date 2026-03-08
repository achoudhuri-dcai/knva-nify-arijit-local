#!/bin/bash

# DCAI + Opik Integration using Git Clone
# This approach clones the official Opik repository and uses their docker-compose files directly

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPIK_NGINX_PORT="${OPIK_NGINX_PORT:-5175}"
OPIK_PROFILES_ARGS="--profile opik"
if [[ "${OPIK_ENABLE_OTEL:-true}" =~ ^([Tt][Rr][Uu][Ee]|1|[Yy][Ee][Ss]|[Oo][Nn])$ ]]; then
    OPIK_PROFILES_ARGS="${OPIK_PROFILES_ARGS} --profile opik-otel"
fi

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; }
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

# Determine which docker compose command to use
set +e
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
else
    echo "Debug: Failed to detect docker compose."
    echo "  'docker compose version' result: $(docker compose version 2>&1)"
    echo "  'docker-compose' location: $(command -v docker-compose 2>&1)"
    error "Docker Compose not found. Please install Docker Compose."
    exit 1
fi
set -e

# Extract Elasticsearch snapshot
extract_es_snapshot() {
    local es_backup_zip="${SCRIPT_DIR}/es_backup/snapshot.zip"
    local es_backup_dir="${SCRIPT_DIR}/es_backup"
    
    if [ -f "$es_backup_zip" ]; then
        # Check if already extracted by looking for common ES snapshot files
        if [ ! -f "$es_backup_dir/index-0" ] && [ ! -f "$es_backup_dir/meta-0" ]; then
            log "Extracting Elasticsearch snapshot: $es_backup_zip"
            if command -v unzip &> /dev/null; then
                cd "$es_backup_dir"
                unzip -o "snapshot.zip"
                cd - > /dev/null
                log "Elasticsearch snapshot extracted successfully"
            else
                error "unzip command not found. Please install unzip to extract ES snapshot."
                exit 1
            fi
        else
            info "Elasticsearch snapshot already extracted, skipping..."
        fi
    else
        warn "Elasticsearch snapshot not found at: $es_backup_zip"
    fi
}

# Set config script path & Check if Opik repository exists
CONFIG_PROJECT_SCRIPT="${SCRIPT_DIR}/../config_project.sh"
OPIK_REPO_PATH="../opik-repo"
if [ ! -d "$OPIK_REPO_PATH" ] || [ ! -f "$OPIK_REPO_PATH/deployment/docker-compose/docker-compose.yaml" ]; then
    if [ "$1" != "deploy" ] && [ "$1" != "config" ] && [ "$1" != "production" ]; then
        log "Cloning Opik repository to $OPIK_REPO_PATH..."
        if [ -d "$OPIK_REPO_PATH" ]; then
            rm -rf "$OPIK_REPO_PATH"
        fi
        git clone https://github.com/comet-ml/opik.git "$OPIK_REPO_PATH"
    fi
fi

case "$1" in
    "init")
        log "Initializing all services (first time setup)..."
        # Ensure Opik repo is available
        if [ ! -d "$OPIK_REPO_PATH" ] || [ ! -f "$OPIK_REPO_PATH/deployment/docker-compose/docker-compose.yaml" ]; then
            log "Cloning Opik repository to $OPIK_REPO_PATH..."
            git clone https://github.com/comet-ml/opik.git "$OPIK_REPO_PATH"
        fi
        
        # Extract Elasticsearch snapshot before starting services
        extract_es_snapshot
        
        NGINX_PORT="$OPIK_NGINX_PORT" $DOCKER_COMPOSE_CMD -f "$OPIK_REPO_PATH/deployment/docker-compose/docker-compose.yaml" $OPIK_PROFILES_ARGS up -d
        
        log "Waiting for Opik to be ready..."
        sleep 10
        
        # Try to connect dcai-app to opik network if it exists
        log "Starting DCAI services..."
        $DOCKER_COMPOSE_CMD up -d
        
        # Connect dcai-app to opik network if both exist
        if docker network ls | grep -q opik_default && docker ps | grep -q dcai-app; then
            log "Connecting DCAI app to Opik network..."
            docker network connect opik_default dcai-app 2>/dev/null || warn "Could not connect to Opik network (this is OK if already connected)"
        fi
        
        log "All services initialized! Access points:"
        echo "  • Opik UI: http://localhost:${OPIK_NGINX_PORT}"
        echo "  • React UI: http://localhost:5173"
        echo "  • DCAI App: http://localhost:8000"
        echo "  • Elasticsearch: http://localhost:9200"
        echo "  • Kibana: http://localhost:5601"
        ;;
    "start"|"")
        # Check if opik-repo exists
        if [ ! -d "$OPIK_REPO_PATH" ] || [ ! -f "$OPIK_REPO_PATH/deployment/docker-compose/docker-compose.yaml" ]; then
            error "Opik not initialized. Run './manage.sh init' first."
            exit 1
        fi
        
        log "Starting/restarting all services..."
        
        # Extract Elasticsearch snapshot before starting services
        extract_es_snapshot
        
        NGINX_PORT="$OPIK_NGINX_PORT" $DOCKER_COMPOSE_CMD -f "$OPIK_REPO_PATH/deployment/docker-compose/docker-compose.yaml" $OPIK_PROFILES_ARGS up -d
        $DOCKER_COMPOSE_CMD up -d
        
        log "All services started! Access points:"
        echo "  • Opik UI: http://localhost:${OPIK_NGINX_PORT}"
        echo "  • React UI: http://localhost:5173"
        echo "  • DCAI App: http://localhost:8000"
        echo "  • Elasticsearch: http://localhost:9200"
        echo "  • Kibana: http://localhost:5601"
        ;;
    "stop")
        log "Stopping all services..."
        $DOCKER_COMPOSE_CMD stop
        $DOCKER_COMPOSE_CMD -f "$OPIK_REPO_PATH/deployment/docker-compose/docker-compose.yaml" $OPIK_PROFILES_ARGS stop
        ;;
    "update")
        log "Updating Opik repository..."
        if [ -d "$OPIK_REPO_PATH" ]; then
            cd "$OPIK_REPO_PATH"
            git pull origin main
            cd - > /dev/null
        else
            log "Opik repository not found, cloning to $OPIK_REPO_PATH..."
            git clone https://github.com/comet-ml/opik.git "$OPIK_REPO_PATH"
        fi
        ;;
    "clean")
        warn "This will remove ALL data!"
        read -p "Continue? (y/N): " -n 1 -r
        echo
        [[ $REPLY =~ ^[Yy]$ ]] && {
            $DOCKER_COMPOSE_CMD down -v
            $DOCKER_COMPOSE_CMD -f "$OPIK_REPO_PATH/deployment/docker-compose/docker-compose.yaml" $OPIK_PROFILES_ARGS down -v
            log "All data cleaned"
        }
        ;;
    "logs")
        echo "=== DCAI Services ==="
        if $DOCKER_COMPOSE_CMD ps | grep -q "Up\|running"; then
            $DOCKER_COMPOSE_CMD logs --tail=20
        else
            echo "No DCAI services are currently running."
            echo "Current DCAI service status:"
            $DOCKER_COMPOSE_CMD ps 2>/dev/null || echo "  Could not get service status"
        fi
        echo -e "\n=== Opik Services ==="
        if [ -d "$OPIK_REPO_PATH" ]; then
            if $DOCKER_COMPOSE_CMD -f "$OPIK_REPO_PATH/deployment/docker-compose/docker-compose.yaml" ps | grep -q "Up\|running"; then
                $DOCKER_COMPOSE_CMD -f "$OPIK_REPO_PATH/deployment/docker-compose/docker-compose.yaml" logs --tail=20
            else
                echo "No Opik services are currently running."
                echo "Current Opik service status:"
                $DOCKER_COMPOSE_CMD -f "$OPIK_REPO_PATH/deployment/docker-compose/docker-compose.yaml" ps 2>/dev/null || echo "  Could not get service status"
            fi
        else
            echo "Opik repository not found. Run './manage.sh init' first."
        fi
        ;;
    "deploy"|"config"|"production")
        project_name=${2:-"knva-nifty"}
        
        # Check if config_project.sh exists
        if [ ! -f "$CONFIG_PROJECT_SCRIPT" ]; then
            error "config_project.sh not found at: $CONFIG_PROJECT_SCRIPT"
            error "Please ensure config_project.sh exists in the parent directory of knva-nifty"
            exit 1
        fi
        
        # Make config_project.sh executable
        chmod +x "$CONFIG_PROJECT_SCRIPT"
        
        log "Starting production deployment using config_project.sh..."
        info "Project: $project_name"
        info "Config script: $CONFIG_PROJECT_SCRIPT"
        
        if [ "$PWD" != "$HOME" ]; then
            warn "config_project.sh requires running from home directory"
            info "Changing to home directory and running config_project.sh"
            OLD_PWD="$PWD"
            
            cd "$HOME"
            "$CONFIG_PROJECT_SCRIPT" "$project_name"
            exit_code=$?
            cd "$OLD_PWD"
        else
            "$CONFIG_PROJECT_SCRIPT" "$project_name"
            exit_code=$?
        fi
        
        if [ $exit_code -eq 0 ]; then
            log "Production deployment completed successfully!"
        else
            error "Production deployment failed with exit code: $exit_code"
            exit $exit_code
        fi
        ;;
    "status")
        info "System Status Overview"
        echo "========================"
        
        echo "Docker Services:"
        if command -v docker &> /dev/null; then
            $DOCKER_COMPOSE_CMD ps 2>/dev/null || echo "  No Docker services running"
            if [ -d "$OPIK_REPO_PATH" ]; then
                echo "Opik Services:"
                $DOCKER_COMPOSE_CMD -f "$OPIK_REPO_PATH/deployment/docker-compose/docker-compose.yaml" ps 2>/dev/null || echo "  No Opik services running"
            fi
        else
            echo "  Docker not available"
        fi
        
        echo -e "\nProduction Services:"
        if command -v supervisorctl &> /dev/null; then
            sudo supervisorctl status 2>/dev/null || echo "  No supervisor services found"
        else
            echo "  Supervisor not available"
        fi
        
        echo -e "\nListening Ports:"
        sudo lsof -i -P -n | grep LISTEN | head -5 2>/dev/null || echo "  Could not check ports"
        ;;
    "config-path")
        info "Configuration Paths:"
        echo "Config Project Script: $CONFIG_PROJECT_SCRIPT"
        echo "Opik Repository: $OPIK_REPO_PATH"
        echo "Current Directory: $PWD"
        echo "Script Directory: $SCRIPT_DIR"
        
        if [ -f "$CONFIG_PROJECT_SCRIPT" ]; then
            log "config_project.sh found and accessible"
        else
            error "config_project.sh NOT found at expected path"
        fi
        ;;
    *)
        echo "Usage: $0 [COMMAND] [OPTIONS]"
        echo ""
        echo "DOCKER COMMANDS:"
        echo "  init   - Initialize all services (first time setup by cloning Opik)"
        echo "  start  - Start/restart all services (default)"
        echo "  stop   - Stop all services"
        echo "  update - Update Opik repository"
        echo "  clean  - Remove all data (WARNING)"
        echo "  logs   - Show service logs"
        echo ""
        echo "PRODUCTION COMMANDS:"
        echo "  deploy [project]     - Deploy project using config_project.sh"
        echo "  config [project]     - Alias for deploy"
        echo "  production [project] - Alias for deploy"
        echo ""
        echo "UTILITY COMMANDS:"
        echo "  status      - Show system status overview"
        echo "  config-path - Show configuration file paths"
        echo ""
        echo "EXAMPLES:"
        echo "  ./manage.sh                    # Start Docker services"
        echo "  ./manage.sh deploy             # Deploy using config_project.sh"
        echo "  ./manage.sh deploy knva-nifty  # Deploy specific project"
        echo "  ./manage.sh status             # Show all service status"
        echo "  ./manage.sh config-path        # Show config paths"
        ;;
esac

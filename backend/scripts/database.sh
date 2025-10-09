#!/bin/bash

# Load environment variables from .env file
if [ -f "../.env" ]; then
    set -a  # automatically export all variables
    source ../.env
    set +a
elif [ -f ".env" ]; then
    set -a  # automatically export all variables
    source .env
    set +a
fi

# Configuration - use environment variables with fallback defaults
CONTAINER_NAME="mariadb-backend"
MARIADB_ROOT_PASSWORD="${DEV_PASSWORD}"
MARIADB_DATABASE="${DEV_DB}"
MARIADB_USER="${DEV_USER}"
MARIADB_PASSWORD="${DEV_PASSWORD}"
MARIADB_PORT="3306"
DOCKER_IMAGE="mariadb:10.11"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

# Function to check if container exists
container_exists() {
    docker ps -a --format "table {{.Names}}" | grep -q "^${CONTAINER_NAME}$"
}

# Function to check if container is running
container_running() {
    docker ps --format "table {{.Names}}" | grep -q "^${CONTAINER_NAME}$"
}

# Function to start existing container
start_container() {
    print_status "Starting existing container: ${CONTAINER_NAME}"
    docker start ${CONTAINER_NAME}
    if [ $? -eq 0 ]; then
        print_status "Container ${CONTAINER_NAME} started successfully!"
    else
        print_error "Failed to start container ${CONTAINER_NAME}"
        exit 1
    fi
}

# Function to create and run new container
create_container() {
    print_status "Creating new MariaDB container: ${CONTAINER_NAME}"
    docker run -d \
        --name ${CONTAINER_NAME} \
        -e MARIADB_ROOT_PASSWORD=${MARIADB_ROOT_PASSWORD} \
        -e MARIADB_DATABASE=${MARIADB_DATABASE} \
        -e MARIADB_USER=${MARIADB_USER} \
        -e MARIADB_PASSWORD=${MARIADB_PASSWORD} \
        -p ${MARIADB_PORT}:3306 \
        --restart unless-stopped \
        ${DOCKER_IMAGE}
    
    if [ $? -eq 0 ]; then
        print_status "Container ${CONTAINER_NAME} created and started successfully!"
        print_status "Waiting for MariaDB to be ready..."
        sleep 10
        print_status "MariaDB connection details:"
        echo "  Host: localhost"
        echo "  Port: ${MARIADB_PORT}"
        echo "  Database: ${MARIADB_DATABASE}"
        echo "  Username: ${MARIADB_USER}"
        echo "  Password: ${MARIADB_PASSWORD}"
        echo "  Root Password: ${MARIADB_ROOT_PASSWORD}"
    else
        print_error "Failed to create container ${CONTAINER_NAME}"
        exit 1
    fi
}

# Function to stop container
stop_container() {
    if container_running; then
        print_status "Stopping container: ${CONTAINER_NAME}"
        docker stop ${CONTAINER_NAME}
        print_status "Container ${CONTAINER_NAME} stopped successfully!"
    else
        print_warning "Container ${CONTAINER_NAME} is not running"
    fi
}

# Function to remove container
remove_container() {
    if container_exists; then
        if container_running; then
            print_status "Stopping container before removal..."
            docker stop ${CONTAINER_NAME}
        fi
        print_status "Removing container: ${CONTAINER_NAME}"
        docker rm ${CONTAINER_NAME}
        print_status "Container ${CONTAINER_NAME} removed successfully!"
    else
        print_warning "Container ${CONTAINER_NAME} does not exist"
    fi
}

# Function to show container status
show_status() {
    if container_exists; then
        if container_running; then
            print_status "Container ${CONTAINER_NAME} is running"
            docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        else
            print_warning "Container ${CONTAINER_NAME} exists but is not running"
            docker ps -a --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        fi
    else
        print_warning "Container ${CONTAINER_NAME} does not exist"
    fi
}

# Function to show logs
show_logs() {
    if container_exists; then
        print_status "Showing logs for container: ${CONTAINER_NAME}"
        docker logs --tail 50 ${CONTAINER_NAME}
    else
        print_error "Container ${CONTAINER_NAME} does not exist"
    fi
}

# Function to connect to MariaDB
connect_mariadb() {
    if container_running; then
        print_status "Connecting to MariaDB..."
        docker exec -it ${CONTAINER_NAME} mariadb -u${MARIADB_USER} -p${MARIADB_PASSWORD} ${MARIADB_DATABASE}
    else
        print_error "Container ${CONTAINER_NAME} is not running"
    fi
}

# Main logic
case "${1:-start}" in
    "start")
        check_docker
        if container_running; then
            print_warning "Container ${CONTAINER_NAME} is already running"
            show_status
        elif container_exists; then
            start_container
        else
            create_container
        fi
        ;;
    "stop")
        check_docker
        stop_container
        ;;
    "restart")
        check_docker
        stop_container
        sleep 2
        if container_exists; then
            start_container
        else
            create_container
        fi
        ;;
    "remove")
        check_docker
        remove_container
        ;;
    "status")
        check_docker
        show_status
        ;;
    "logs")
        check_docker
        show_logs
        ;;
    "connect")
        check_docker
        connect_mariadb
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  start    Start MariaDB container (default)"
        echo "  stop     Stop MariaDB container"
        echo "  restart  Restart MariaDB container"
        echo "  remove   Remove MariaDB container"
        echo "  status   Show container status"
        echo "  logs     Show container logs"
        echo "  connect  Connect to MariaDB shell"
        echo "  help     Show this help message"
        echo ""
        echo "MariaDB Configuration:"
        echo "  Container: ${CONTAINER_NAME}"
        echo "  Database: ${MARIADB_DATABASE}"
        echo "  Username: ${MARIADB_USER}"
        echo "  Password: ${MARIADB_PASSWORD}"
        echo "  Port: ${MARIADB_PORT}"
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
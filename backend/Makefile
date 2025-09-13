# Datab# PHONY targets (targets that don't create files)
.PHONY: help db-start db-stop db-restart db-remove db-status db-logs db-connect db-setup clean install dev-install test lint format check-format type-check django-check django-migrate django-createsuperuser django-setup django-runserver django-lint all-checks env-setup info quick-starte Management Makefile db-seeding
# This Makefile provides convenient commands to manage the MySQL Docker container

# Configuration
CONTAINER_NAME := mariadb-backend
DATABASE_SCRIPT := bash ./scripts/database.sh

# Default target
help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Database Management Targets
db-start: ## Start MariaDB Docker container (creates if doesn't exist)
	@echo "Starting MariaDB container..."
	@$(DATABASE_SCRIPT) start

db-stop: ## Stop MariaDB Docker container
	@echo "Stopping MariaDB container..."
	@$(DATABASE_SCRIPT) stop

db-restart: ## Restart MariaDB Docker container
	@echo "Restarting MariaDB container..."
	@$(DATABASE_SCRIPT) restart

db-remove: ## Remove MariaDB Docker container completely
	@echo "Removing MariaDB container..."
	@$(DATABASE_SCRIPT) remove

db-status: ## Show MariaDB container status
	@echo "Checking MariaDB container status..."
	@$(DATABASE_SCRIPT) status

db-logs: ## Show MariaDB container logs
	@echo "Showing MariaDB container logs..."
	@$(DATABASE_SCRIPT) logs

db-connect: ## Connect to MariaDB shell
	@echo "Connecting to MariaDB..."
	@$(DATABASE_SCRIPT) connect

db-setup: db-start ## Setup database (alias for db-start)
	@echo "Database setup completed!"

# Python Development Targets
install: ## Install project dependencies
	@echo "Installing dependencies..."
	@uv sync

dev-install: ## Install development dependencies
	@echo "Installing development dependencies..."
	@uv sync --dev

# Testing and Quality Targets
test: ## Run tests
	@echo "Running tests..."
	@uv run pytest

test-cov: ## Run tests with coverage
	@echo "Running tests with coverage..."
	@uv run pytest --cov=src --cov-report=html --cov-report=term

# Environment setup
env-setup: ## Copy sample.env to .env for initial setup
	@if [ ! -f .env ]; then \
		echo "Copying sample.env to .env..."; \
		cp sample.env .env; \
		echo "✅ .env file created from sample.env"; \
		echo "⚠️  Please edit .env and fill in your actual values"; \
	else \
		echo "⚠️  .env file already exists"; \
	fi

# Code Quality Targets
lint: ## Run linting (flake8, isort check, black check, mypy)
	@echo "Running comprehensive linting..."
	@echo "  - Running flake8..."
	@uv run flake8 web_tutors/ --extend-ignore=E501,W503 --exclude=migrations,settings.py,manage.py || true
	@echo "  - Checking import formatting with isort..."
	@uv run isort --check-only --diff web_tutors/ --skip-glob="*/migrations/*" --skip="settings.py" --skip="manage.py" || true
	@echo "  - Checking code formatting with black..."
	@uv run black --check --diff web_tutors/ --exclude="migrations/|settings\.py|manage\.py" || true
	@echo "  - Running type checking with mypy..."
	@uv run mypy web_tutors/ --ignore-missing-imports --exclude="migrations/|settings\.py|manage\.py" --disable-error-code=no-untyped-def || true
	@echo "Linting completed!"

lint-fix: ## Run linting with auto-fix (applies formatting and import fixes)
	@echo "Running linting with auto-fix..."
	@echo "  - Auto-fixing import formatting with isort..."
	@uv run isort web_tutors/ --skip-glob="*/migrations/*" --skip="settings.py" --skip="manage.py"
	@echo "  - Auto-formatting code with black..."
	@uv run black web_tutors/ --exclude="migrations/|settings\.py|manage\.py"
	@echo "  - Running flake8 (no auto-fix available)..."
	@uv run flake8 web_tutors/ --extend-ignore=E501,W503 --exclude=migrations,settings.py,manage.py || true
	@echo "  - Running type checking with mypy..."
	@uv run mypy web_tutors/ --ignore-missing-imports --exclude="migrations/|settings\.py|manage\.py" --disable-error-code=no-untyped-def || true
	@echo "Auto-fix linting completed!"

format: ## Format code with black and isort
	@echo "Formatting code..."
	@echo "  - Sorting imports with isort..."
	@uv run isort web_tutors/ --skip-glob="*/migrations/*" --skip="settings.py" --skip="manage.py"
	@echo "  - Formatting code with black..."
	@uv run black web_tutors/ --exclude="migrations/|settings\.py|manage\.py"
	@echo "Code formatting completed!"

check-format: ## Check if code is formatted correctly
	@echo "Checking code formatting..."
	@echo "  - Checking import order with isort..."
	@uv run isort --check-only web_tutors/ --skip-glob="*/migrations/*" --skip="settings.py" --skip="manage.py"
	@echo "  - Checking code format with black..."
	@uv run black --check web_tutors/ --exclude="migrations/|settings\.py|manage\.py"
	@echo "Format check completed!"

type-check: ## Run type checking with mypy
	@echo "Running type checking..."
	@uv run mypy web_tutors/ --ignore-missing-imports --exclude="migrations/|settings\.py|manage\.py" --disable-error-code=no-untyped-def
	@echo "Type checking completed!"

django-check: ## Run Django system checks
	@echo "Running Django system checks..."
	@uv run python manage.py check
	@echo "Django checks completed!"

django-migrate: ## Run Django migrations
	@echo "Running Django migrations..."
	@uv run python manage.py migrate
	@echo "Django migrations completed!"

django-createsuperuser: ## Create Django superuser from environment variables
	@echo "Creating Django superuser..."
	@uv run python scripts/create_superuser.py
	@echo "Django superuser creation completed!"

django-setup: django-migrate django-createsuperuser ## Setup Django (migrate + create superuser)
	@echo "Django setup completed!"

django-runserver: ## Start Django development server
	@echo "Starting Django development server..."
	@echo "Access the application at: http://localhost:8000/"
	@echo "Access admin panel at: http://localhost:8000/admin/"
	@echo "Press Ctrl+C to stop the server"
	@uv run python manage.py runserver

django-lint: lint django-check ## Run comprehensive linting including Django checks
	@echo "Comprehensive Django linting completed!"

# Combined targets
all-checks: lint check-format type-check ## Run all code quality checks
	@echo "All checks completed!"

# Development workflow targets
dev-setup: dev-install db-setup ## Setup development environment
	@echo "Development environment setup completed!"

dev-reset: db-remove db-setup ## Reset development database
	@echo "Development database reset completed!"

# Cleanup targets
clean: ## Clean up temporary files and caches
	@echo "Cleaning up..."
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@find . -type d -name "*.egg-info" -exec rm -rf {} +
	@find . -type d -name ".pytest_cache" -exec rm -rf {} +
	@find . -type d -name ".coverage" -delete
	@find . -type d -name "htmlcov" -exec rm -rf {} +

clean-all: clean db-remove ## Clean everything including database
	@echo "Complete cleanup completed!"

# Docker-related targets
docker-ps: ## Show all Docker containers
	@echo "Showing Docker containers..."
	@docker ps -a

docker-images: ## Show Docker images
	@echo "Showing Docker images..."
	@docker images

docker-clean: ## Clean up Docker resources
	@echo "Cleaning up Docker resources..."
	@docker system prune -f

# Quick development commands
run-dev: db-start ## Start development environment (database + Django server)
	@echo "Starting development environment..."
	@echo "Database started, now starting Django server..."
	@echo ""
	@echo "🌐 Access URLs:"
	@echo "  - API Info: http://localhost:8000/"
	@echo "  - Admin Panel: http://localhost:8000/admin/"
	@echo "  - OAuth2: http://localhost:8000/o/"
	@echo ""
	@echo "🔐 Admin Login: $DEV_ADMIN_USER / $DEV_ADMIN_USER_PASSWORD"
	@echo ""
	@echo "Press Ctrl+C to stop the server"
	@uv run python manage.py runserver

stop-dev: db-stop ## Stop development environment
	@echo "Stopping development environment..."

# Backup and restore (future implementation)
db-backup: ## Backup database (placeholder)
	@echo "Database backup functionality - to be implemented"

db-restore: ## Restore database (placeholder)
	@echo "Database restore functionality - to be implemented"

# Information targets
info: ## Show project information
	@echo "Project: Backend"
info: ## Show project information
	@echo ""
	@echo "📚 Web Tutors Backend - Project Information"
	@echo "=============================================="
	@echo "Project: Web Tutors"
	@echo "Description: Online Learning Platform Backend"
	@echo "Version: 1.0.0"
	@echo ""
	@echo "🔧 Configuration:"
	@echo "Database Container: $(CONTAINER_NAME)"
	@echo "Database Script: $(DATABASE_SCRIPT)"
	@echo "Python Version: 3.11+"
	@echo "Package Manager: uv"
	@echo "Environment: .env (copy from sample.env)"
	@echo ""
	@echo "🌐 Endpoints:"
	@echo "API Info: http://localhost:8000/"
	@echo "Admin Panel: http://localhost:8000/admin/"
	@echo "OAuth2: http://localhost:8000/o/"
	@echo ""
	@echo "🔐 Admin Credentials:"
	@echo "Username: $DEV_ADMIN_USER"
	@echo "Password: $DEV_ADMIN_USER_PASSWORD"

# Quick reference
quick-start: env-setup dev-setup ## Quick start for new developers
	@echo ""
	@echo "🚀 Quick Start Complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Edit .env file with your actual values"
	@echo "  2. Run 'make run-dev' to start the development server"
	@echo "  3. Run 'make test' to run tests"
	@echo "  2. Run 'make db-connect' to connect to database"
	@echo "  3. Run 'make help' to see all available commands"
	@echo ""
# Seed initial data
db-seeding: ## Seed initial data into the database (placeholder)
	@echo "Database seeding functionality - to be implemented"
	@echo "Seeding initial data into the database... (to be implemented)"
	@uv run python manage.py seed_campus
	@uv run python manage.py seed_permission
	
	@uv run python manage.py seed_skills
	@uv run python manage.py seed_courses
	@uv run python manage.py seed_units_courses
	@echo "Database seeding completed!"
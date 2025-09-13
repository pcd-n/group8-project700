# Web Tutors - Online Learning Platform Backend

A comprehensive Django-based backend system for managing tutor allocation, course scheduling, and educational administration at the University of Tasmania.

## 🏗️ Project Overview

The Web Tutors system is a sophisticated tutor allocation platform designed to streamline the process of assigning tutors to university units across multiple campuses. The system supports role-based access control, expression of interest (EOI) management, automated scheduling, and comprehensive reporting.

## 🎯 Key Features

- **User Management**: Custom user authentication with role-based permissions
- **Tutor Allocation**: Automated and manual tutor assignment to courses
- **EOI Management**: Expression of Interest application processing
- **Timetable Management**: Course scheduling and conflict resolution
- **Multi-Campus Support**: Hobart, Launceston, and Online delivery modes
- **Audit Logging**: Comprehensive activity tracking
- **RESTful API**: Complete API for frontend integration
- **Admin Dashboard**: Django admin interface for system management

## 📁 Project Structure

```
web_tutors/
├── web_tutors/                 # Main Django project configuration
│   ├── settings.py            # Django settings and configuration
│   ├── urls.py                # Main URL routing
│   ├── wsgi.py                # WSGI configuration
│   └── asgi.py                # ASGI configuration
├── users/                      # User management and authentication
├── units/                      # Academic units and courses
├── eoi/                        # Expression of Interest applications
├── timetable/                  # Class scheduling and timetable
├── dashboard/                  # Administrative dashboard
├── scripts/                    # Utility scripts and database setup
├── docs/                       # Documentation and specifications
├── frontend/                   # Basic frontend interface
├── manage.py                   # Django management script
├── Makefile                    # Development automation
├── pyproject.toml             # Project dependencies and configuration
└── README.md                   # This file
```

## 🗃️ Database Models & Architecture

### Users App (`users/`)

The users app provides comprehensive user management with role-based access control.

#### Core Models:

**User Model**

```python
class User(AbstractBaseUser):
    email = models.EmailField(unique=True)          # Primary identifier
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150) 
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

**Role Management**

```python
class Role(models.Model):
    role_name = models.CharField(max_length=50, unique=True)
    description = models.TextField()
  
class UserRoles(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
```

**Campus Model**

```python
class Campus(models.Model):
    CAMPUS_CHOICES = [
        ('SB', 'Sandy Bay'),
        ('IR', 'Inveresk'),
        ('ON', 'Online'),
    ]
    campus_name = models.CharField(max_length=2, choices=CAMPUS_CHOICES)
```

**Supervisor Model**

```python
class Supervisor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    campus = models.ForeignKey(Campus, on_delete=models.SET_NULL)
    department = models.CharField(max_length=100)
```

**Key Functions:**

- Single active role per user management
- JWT token-based authentication
- OAuth integration with Google
- Comprehensive user management API
- Role assignment and permission checking

### Units App (`units/`)

Manages academic units, courses, and their relationships.

#### Core Models:

**Unit Model**

```python
class Unit(models.Model):
    unit_code = models.CharField(max_length=20, unique=True)  # e.g., "MATH101"
    unit_name = models.CharField(max_length=255)
    credits = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

**Course Model**

```python
class Course(models.Model):
    course_code = models.CharField(max_length=20, unique=True)  # e.g., "BSC-DS"
    course_name = models.CharField(max_length=255)
    faculty = models.CharField(max_length=100)
    degree_level = models.CharField(max_length=20)
```

**UnitCourse Model**

```python
class UnitCourse(models.Model):
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE)
    term = models.CharField(max_length=20)  # e.g., "SEM1", "SEM2"
    year = models.IntegerField()
    status = models.CharField(max_length=20, default='Draft')
```

**Skill Model**

```python
class Skill(models.Model):
    skill_name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    category = models.CharField(max_length=50)
```

**Key Functions:**

- Unit and course catalog management
- Skill tracking for tutors
- Campus-specific course offerings
- Term and year-based scheduling

### EOI App (`eoi/`)

Handles Expression of Interest applications from potential tutors.

#### Core Models:

**EoiApp Model (SCD Type II)**

```python
class EoiApp(models.Model):
    scd_id = models.AutoField(primary_key=True)        # Technical key
    eoi_app_id = models.UUIDField(default=uuid.uuid4)  # Business key
    applicant_user = models.ForeignKey(User, on_delete=models.CASCADE)
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL)
    campus = models.ForeignKey(Campus, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20)           # Submitted/Reviewed/Accepted/Rejected
    is_current = models.BooleanField(default=True)     # SCD Type II flag
    version = models.PositiveIntegerField(default=1)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField(null=True, blank=True)
```

**MasterEoi Model**

```python
class MasterEoi(models.Model):
    master_eoi_id = models.AutoField(primary_key=True)
    applicant_user = models.ForeignKey(User, on_delete=models.CASCADE)
    application_period = models.CharField(max_length=50)
    overall_status = models.CharField(max_length=20)
    submitted_at = models.DateTimeField()
```

**TutorSkills Model**

```python
class TutorSkills(models.Model):
    tutor_user = models.ForeignKey(User, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    proficiency_level = models.CharField(max_length=20)
    years_experience = models.PositiveIntegerField()
```

**Key Functions:**

- Slowly Changing Dimension (SCD) Type II implementation
- Application workflow management
- Skill-based tutor matching
- Bulk EOI import from CSV
- Application status tracking

### Timetable App (`timetable/`)

Manages class schedules, tutor assignments, and timetable generation.

#### Core Models:

**MasterClassTime Model**

```python
class MasterClassTime(models.Model):
    subject_code = models.CharField(max_length=50)
    subject_description = models.CharField(max_length=255)
    activity_group_code = models.CharField(max_length=50)  # Tut-A, Lec-A, Wks-A
    activity_code = models.CharField(max_length=50)        # TutA-01, LecA-01
    campus = models.CharField(max_length=20)
    day_of_week = models.CharField(max_length=10)
    start_time = models.TimeField()
    end_time = models.TimeField()
    location = models.CharField(max_length=100)
```

**Timetable Model**

```python
class Timetable(models.Model):
    unit_course = models.ForeignKey(UnitCourse, on_delete=models.CASCADE)
    tutor_user = models.ForeignKey(User, on_delete=models.SET_NULL)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE)
    day_of_week = models.CharField(max_length=10)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=50)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
```

**TimetableImportLog Model**

```python
class TimetableImportLog(models.Model):
    import_id = models.UUIDField(default=uuid.uuid4)
    filename = models.CharField(max_length=255)
    imported_by = models.ForeignKey(User, on_delete=models.SET_NULL)
    import_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20)
    records_processed = models.PositiveIntegerField()
    records_imported = models.PositiveIntegerField()
    error_log = models.TextField()
```

**Key Functions:**

- CSV timetable import processing
- Conflict detection and resolution
- Automated tutor assignment
- Schedule optimization
- Room and resource management

### Dashboard App (`dashboard/`)

Provides administrative dashboard and reporting functionality.

## 🚀 Setup Instructions

### Prerequisites

- **Python**: 3.11 or higher
- **Database**: MariaDB 10.11+
- **Package Manager**: UV (recommended) or pip
- **Development Tools**: Make (optional but recommended)

### 0. Install UV Package Manager (Recommended)

UV is a fast Python package installer and resolver, written in Rust. It's highly recommended for this project.

#### Install UV

**macOS and Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Using pip (if you already have Python):**
```bash
pip install uv
```

**Using Homebrew (macOS):**
```bash
brew install uv
```

**Using Cargo (if you have Rust installed):**
```bash
cargo install uv
```

**Verify installation:**
```bash
uv --version
```

For more installation options, visit: https://docs.astral.sh/uv/getting-started/installation/

### 1. Environment Setup

#### Using UV (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd backend

# Install dependencies with UV
uv sync

# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows
```

#### Using pip

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Setup

#### Using Docker (Recommended)

```bash
# Start MariaDB container
make db-start

# Check container status
make db-status

# View logs
make db-logs
```

#### Manual MariaDB Setup

```bash
# Install MariaDB (Ubuntu/Debian)
sudo apt-get install mariadb-server mariadb-client

# Secure installation
sudo mysql_secure_installation

# Create database
mysql -u root -p
CREATE DATABASE web_tutors_mariadb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'webtutors'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON web_tutors_mariadb.* TO 'webtutors'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 3. Environment Configuration

```bash
# Copy sample environment file
cp sample.env .env

# Edit .env file with your settings
nano .env
```

Required environment variables:

```bash
# Project Configuration
PROJECT_TITLE=Web Tutors

# Database Configuration
DEV_DB=web_tutors_mariadb
DEV_USER=webtutors
DEV_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=3306

# Admin User Configuration
DEV_ADMIN_USER=admin@webtutors.com
DEV_ADMIN_USER_PASSWORD=admin_password
```

### 4. Database Migration

```bash
# Run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
# or use the script
python scripts/create_superuser.py
```

### 5. Development Server

```bash
# Start development server
python manage.py runserver

# Or use Make
make run-dev
```

Visit `http://127.0.0.1:8000/` to access the application.

### 6. Testing

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test users

# Run with coverage
make test-cov

# Quick test for users app (183 tests)
make test
```

## 🔧 Development Workflow

### Using Make Commands

The project includes a comprehensive Makefile for development automation:

```bash
# Database management
make db-start          # Start MariaDB container
make db-stop           # Stop MariaDB container
make db-restart        # Restart MariaDB container
make db-status         # Check container status
make db-logs           # View database logs
make db-connect        # Connect to database

# Development
make install           # Install dependencies
make dev-install       # Install with dev dependencies
make run-dev           # Start development server
make test              # Run tests
make test-cov          # Run tests with coverage
make lint              # Run linting
make format            # Format code
make clean             # Clean temporary files

# Quick start
make quick-start       # Complete setup and start
```

### Code Quality

```bash
# Format code with Black
make format

# Run linting
make lint

# Type checking with mypy
make type-check

# Run all quality checks
make all-checks
```

## 🔑 Authentication & Authorization

### Role-Based Access Control

The system implements a sophisticated role-based access control system:

- **Admin**: Full system access, user management, EOI import
- **Unit Coordinator**: Unit-specific management, tutor allocation
- **Tutor**: View assigned schedules, update availability
- **Supervisor**: Oversight and reporting functions
- **Member**: Basic authenticated user access

### API Authentication

- **JWT Tokens**: Primary authentication method
- **OAuth2**: Google integration for external authentication
- **Session-based**: Django admin interface

### Key Security Features

- Single active role per user (prevents privilege escalation)
- Token-based API authentication
- Comprehensive audit logging
- Role-based view permissions
- CSRF protection
- Secure password hashing

## 📊 API Documentation

### Key Endpoints

#### Authentication

- `POST /api/users/login/` - User login
- `POST /api/users/register/` - User registration
- `POST /api/auth/token/` - JWT token obtain
- `POST /api/auth/token/refresh/` - JWT token refresh

#### User Management

- `GET /api/users/profile/` - User profile
- `PUT /api/users/profile/` - Update profile
- `GET /api/users/roles/` - List roles
- `POST /api/users/user-roles/` - Assign roles

#### Units & Courses

- `GET /api/units/` - List units
- `POST /api/units/` - Create unit
- `GET /api/units/{id}/courses/` - Unit courses
- `GET /api/skills/` - List skills

#### EOI Management

- `GET /api/eoi/applications/` - List applications
- `POST /api/eoi/applications/` - Submit application
- `PUT /api/eoi/applications/{id}/` - Update application
- `POST /api/eoi/bulk-import/` - Bulk import EOIs

#### Timetable

- `GET /api/timetable/` - List schedules
- `POST /api/timetable/allocate/` - Assign tutor
- `POST /api/timetable/import/` - Import timetable CSV
- `GET /api/timetable/conflicts/` - Check conflicts

## 🧪 Testing

### Test Coverage

The project maintains comprehensive test coverage across all applications:

- **Users App**: 183 tests covering authentication, roles, permissions
- **Units App**: Model validation, relationship integrity
- **EOI App**: Application workflow, SCD Type II functionality
- **Timetable App**: Schedule conflict detection, import validation

### Running Tests

```bash
# All tests
python manage.py test

# Specific app
python manage.py test users

# With verbosity
python manage.py test users -v 2

# Coverage report
coverage run --source='.' manage.py test
coverage report
coverage html
```

### Test Categories

- **Unit Tests**: Model validation, business logic
- **Integration Tests**: API endpoints, workflow testing
- **Performance Tests**: Factory optimization, bulk operations
- **Security Tests**: Authentication, authorization, input validation

## 📈 Performance & Scalability

### Database Optimization

- Optimized indexes on frequently queried fields
- Connection pooling with MariaDB
- Query optimization for large datasets
- Efficient pagination for list views

### Caching Strategy

- Django cache framework ready
- Session-based caching for user data
- Query result caching for static data

### File Processing

- Asynchronous CSV import processing
- Bulk database operations for large datasets
- Memory-efficient file handling

## 🔒 Security Considerations

### Data Protection

- Personal information encryption
- Secure file upload handling
- SQL injection prevention
- XSS protection

### Access Control

- Role-based permissions
- API rate limiting ready
- Audit trail for all operations
- Secure password policies

## 🚀 Deployment

### Production Setup

1. **Environment Configuration**

   ```bash
   # Production settings
   DEBUG=False
   ALLOWED_HOSTS=yourdomain.com
   SECRET_KEY=your-secret-key
   ```
2. **Database Configuration**

   ```bash
   # Production database
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.mysql',
           'NAME': 'web_tutors_prod',
           'USER': 'prod_user',
           'PASSWORD': 'secure_password',
           'HOST': 'db-server',
           'PORT': '3306',
       }
   }
   ```
3. **Static Files**

   ```bash
   python manage.py collectstatic
   ```

### Docker Deployment

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["gunicorn", "web_tutors.wsgi:application"]
```

## 🤝 Contributing

### Development Guidelines

1. **Code Style**: Follow PEP 8, use Black for formatting
2. **Testing**: Maintain test coverage above 90%
3. **Documentation**: Update README for new features
4. **Git Workflow**: Feature branches, pull requests

### Commit Convention

```bash
feat: add new EOI import functionality
fix: resolve role assignment bug
docs: update API documentation
test: add unit tests for timetable conflicts
```

## 📋 Troubleshooting

### Common Issues

#### Database Connection

```bash
# Check MariaDB status
make db-status

# Restart database
make db-restart

# Check logs
make db-logs
```

#### Migration Issues

```bash
# Reset migrations (development only)
python manage.py migrate --fake-initial

# Show migration status
python manage.py showmigrations
```

#### Test Failures

```bash
# Run specific test with debugging
python manage.py test users.tests.test_models.UserModelTestCase.test_user_creation -v 2

# Check test database
python manage.py test --debug-mode
```

## 📚 Additional Resources

- **Django Documentation**: https://docs.djangoproject.com/
- **Django REST Framework**: https://www.django-rest-framework.org/
- **MariaDB Documentation**: https://mariadb.org/documentation/
- **JWT Authentication**: https://django-rest-framework-simplejwt.readthedocs.io/

## 📞 Support

For technical support or questions:

- **Project Repository**: 
- **Issue Tracker**: Use GitHub Issues for bug reports
- **Documentation**: Check `/docs/` folder for additional documentation

## 📄 License

This project is licensed under the MIT License. See the LICENSE file for details.

---

**Web Tutors Team**
University of Tasmania
Project 700 - Group 8

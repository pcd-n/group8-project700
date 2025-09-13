# User Management & RBAC API Documentation

## Overview
This document outlines the essential APIs for user management and Role-Based Access Control (RBAC). All redundant and unnecessary endpoints have been removed.

## API Endpoints

### 🔐 Authentication Endpoints

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| `POST` | `/api/users/login/` | User login with email/password | Public |
| `POST` | `/api/users/register/` | User registration | Public |
| `POST` | `/api/users/token/` | JWT token authentication | Public |
| `POST` | `/api/users/token/refresh/` | Refresh JWT token | Public |

### 👤 User Profile Endpoints

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| `GET` | `/api/users/profile/` | Get own profile | Authenticated |
| `GET` | `/api/users/profile/{user_id}/` | View specific user profile | Admin/Coordinator/Tutor/Support |

### 👥 User Management Endpoints

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| `PUT` | `/api/users/users/update/` | Update own user details or bulk update | Admin/Coordinator only |
| `PUT` | `/api/users/users/update/{user_id}/` | Update specific user details | Admin/Coordinator only |

### 🎭 RBAC - Role Management Endpoints

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| `GET` | `/api/users/roles/` | List all roles | Admin only |
| `POST` | `/api/users/roles/` | Create new role | Admin only |
| `GET` | `/api/users/roles/{id}/` | Get specific role | Admin only |
| `PUT` | `/api/users/roles/{id}/` | Update role | Admin only |
| `DELETE` | `/api/users/roles/{id}/` | Delete role | Admin only |

### 🔑 RBAC - Permission Management Endpoints

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| `GET` | `/api/users/permissions/` | List all permissions | Admin only |
| `POST` | `/api/users/permissions/` | Create new permission | Admin only |
| `GET` | `/api/users/permissions/{id}/` | Get specific permission | Admin only |
| `PUT` | `/api/users/permissions/{id}/` | Update permission | Admin only |
| `DELETE` | `/api/users/permissions/{id}/` | Delete permission | Admin only |

### 🔗 RBAC - User Role Assignment Endpoints

| Method | Endpoint | Description | Permissions |
|--------|----------|-------------|-------------|
| `GET` | `/api/users/user-roles/` | List all user-role assignments | Admin/Coordinator |
| `POST` | `/api/users/user-roles/` | Assign roles to users (bulk) | Admin/Coordinator |
| `GET` | `/api/users/user-roles/{user_id}/` | Get user's roles | Admin/Coordinator |
| `PUT` | `/api/users/user-roles/{user_id}/` | Update user's roles | Admin/Coordinator |
| `DELETE` | `/api/users/user-roles/{user_id}/role/{role_id}/` | Remove specific role from user | Admin/Coordinator |

## Role Hierarchy & Permissions

### Roles in System
1. **Admin** - Full system access
2. **Coordinator** - User and allocation management for their units
3. **Tutor** - Session management and student interaction  
4. **Support** - Data import/export and technical support
5. **Member** - Basic access (default role)

### Permission Restrictions

#### User Management
- **Bulk Updates**: Admin and Coordinator only
- **User Listing**: Admin and Coordinator only
- **Profile Viewing**: Hierarchical (Admin > Coordinator > Tutor > Support > Member)

#### RBAC Management
- **Role Management**: Admin only
- **Permission Management**: Admin only
- **Role Assignment**: 
  - Admin: Can assign any role
  - Coordinator: Can only assign Tutor and Member roles

## Key Features

### Authentication
- Custom login/register with JWT tokens
- Standard JWT token obtain/refresh endpoints
- Role-based permission checking

### User Management
- Self-profile viewing for all users
- Hierarchical profile viewing permissions
- Bulk user updates (Admin/Coordinator only)

### RBAC System
- Complete role management (Admin only)
- Permission system with granular controls
- User-role assignment with restrictions
- Single active role per user system

## Removed Redundant Endpoints

The following redundant endpoints were removed:
- `PATCH` methods (replaced with `PUT` for consistency)
- Duplicate user-role management paths (`/assign/`, `/update/` merged into base endpoint)
- Multiple profile endpoints consolidated
- Unnecessary HTTP methods for certain resources

## Request/Response Examples

### Login Request
```json
POST /api/users/login/
{
    "email": "user@example.com",
    "password": "password123"
}
```

### Bulk User Update Request
```json
PUT /api/users/users/update/
[
    {
        "id": 1,
        "first_name": "John",
        "email": "john@example.com"
    },
    {
        "id": 2,
        "last_name": "Doe"
    }
]
```

### Role Assignment Request
```json
POST /api/users/user-roles/
{
    "user_id": 5,
    "role_id": 2
}
```

### Role Update Request
```json
PUT /api/users/user-roles/3/
{
    "role_ids": [2, 4]
}
```

This streamlined API provides all necessary functionality while eliminating redundancy and maintaining clear permission boundaries.
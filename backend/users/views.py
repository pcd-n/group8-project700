from django.shortcuts import render
from rest_framework import status, generics, serializers
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiExample
from .models import User, Role, Permission, UserRoles, Supervisor, Campus
from .serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    RoleSerializer, PermissionSerializer, UserRolesSerializer,
    SupervisorSerializer
)
from .permission import CanManageRoles, CanAssignRoles
from rich.console import Console
import logging

# Configure rich console
console = Console()
logger = logging.getLogger(__name__)


class LoginSerializer(serializers.Serializer):
    """Serializer for login request."""
    email = serializers.EmailField(help_text="User's email address")
    password = serializers.CharField(write_only=True, help_text="User's password")


class LoginResponseSerializer(serializers.Serializer):
    """Serializer for login response."""
    user = UserSerializer()
    tokens = serializers.DictField(help_text="JWT access and refresh tokens")


class LoginView(generics.CreateAPIView):
    """Login user with email and password."""
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer
    
    @extend_schema(
        request=LoginSerializer,
        responses={200: LoginResponseSerializer},
        description="Login user with email and password",
        examples=[
            OpenApiExample(
                'Login Example',
                value={
                    'email': 'user@example.com',
                    'password': 'password123'
                },
                request_only=True,
            ),
        ]
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        
        try:
            result = User.objects.login_user(email=email, password=password)
            
            if result['success']:
                user_serializer = UserSerializer(result['user'])
                return Response({
                    'user': user_serializer.data,
                    'tokens': result['tokens']
                }, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'error': result['message']},
                    status=status.HTTP_401_UNAUTHORIZED
                )
        
        except Exception as e:
            console.print(f"[red]Login error:[/red] {str(e)}")
            return Response(
                {'error': 'Login failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RegisterView(generics.CreateAPIView):
    """Register a new user with optional role assignment and supervisor creation."""
    permission_classes = [AllowAny]
    serializer_class = UserCreateSerializer
    
    @extend_schema(
        request=UserCreateSerializer,
        responses={201: UserSerializer},
        description="Register a new user with optional role assignment and supervisor creation",
        examples=[
            OpenApiExample(
                'User Registration Example',
                value={
                    'email': 'newuser@example.com',
                    'password': 'password123',
                    'first_name': 'John',
                    'last_name': 'Doe',
                    'roles': ['Member'],
                    'is_supervisor': False
                },
                request_only=True,
            ),
        ]
    )
    def create(self, request, *args, **kwargs):
        try:
            data = request.data
            return self._single_register(data)
        
        except Exception as e:
            console.print(f"[red]Registration error:[/red] {str(e)}")
            return Response(
                {'error': 'Registration failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _single_register(self, data):
        """Register a single user."""
        serializer = UserCreateSerializer(data=data)
        
        if not serializer.is_valid():
            return Response(
                {'error': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # Create user
            user_data = serializer.validated_data.copy()
            roles = user_data.pop('roles', [])
            is_supervisor = user_data.pop('is_supervisor', False)
            campus_id = user_data.pop('campus_id', None)
            
            result = User.objects.register_user(**user_data)
            
            if not result['success']:
                return Response(
                    {'error': result['message']},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user = result['user']
            
            # Assign roles
            if roles:
                self._assign_roles(user, roles)
            
            # Create supervisor instance if needed
            if is_supervisor:
                campus = None
                if campus_id:
                    try:
                        campus = Campus.objects.get(id=campus_id)
                    except Campus.DoesNotExist:
                        pass
                
                Supervisor.objects.create(user=user, campus=campus)
            
            user_serializer = UserSerializer(user)
            return Response({
                'user': user_serializer.data,
                'tokens': result['tokens'],
                'is_supervisor': is_supervisor
            }, status=status.HTTP_201_CREATED)
    
    def _assign_roles(self, user, role_names):
        """Assign roles to a user (single active role only) - always create new instances for auditing."""
        # If no roles provided, assign default Member role
        if not role_names:
            role_names = ['Member']
            console.print(f"[yellow]No roles specified for user {user.email}, assigning default Member role[/yellow]")
        
        # Take only the first role since system enforces single active role
        role_name = role_names[0] if isinstance(role_names, list) else role_names
        
        if len(role_names) > 1:
            console.print(f"[yellow]Warning: Multiple roles provided for {user.email}, using only first role: {role_name}[/yellow]")
        
        try:
            role = Role.objects.get(role_name=role_name)
            
            # Disable ALL existing active role assignments for this user (single active role system)
            existing_assignments = UserRoles.objects.filter(user=user, is_active=True)
            disabled_roles = []
            
            for assignment in existing_assignments:
                assignment.disable()
                disabled_roles.append(assignment.role.role_name)
            
            if disabled_roles:
                console.print(f"[yellow]• Disabled previous roles for {user.email}: {', '.join(disabled_roles)}[/yellow]")
            
            # ALWAYS create a new UserRole instance for proper auditing trail
            user_role = UserRoles.objects.create(
                user=user,
                role=role,
                is_active=True
            )
            console.print(f"[green]✓ Created new role assignment {role_name} for user {user.email}[/green]")
                
        except Role.DoesNotExist:
            # Fall back to Member role if specified role doesn't exist
            console.print(f"[red]Warning: Role '{role_name}' does not exist, assigning Member role instead[/red]")
            try:
                member_role = Role.objects.get(role_name='Member')
                UserRoles.objects.create(user=user, role=member_role, is_active=True)
                console.print(f"[green]✓ Created new Member role assignment for user {user.email}[/green]")
            except Role.DoesNotExist:
                console.print(f"[red]Error: Member role does not exist! User {user.email} has no role assigned[/red]")


class UserUpdatePermission(BasePermission):
    """Custom permission for user updates - Admin/Coordinator can update any user, users can update themselves."""
    
    def has_permission(self, request, view):
        """Check basic authentication."""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if user can update the target user."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin and staff can update anyone
        if request.user.is_staff or request.user.has_role('Admin'):
            return True
        
        # Coordinators can update anyone
        if request.user.has_role('Coordinator'):
            return True
        
        # Users can update themselves
        if isinstance(obj, User) and obj == request.user:
            return True
        
        return False


class UserUpdateView(APIView):
    """Update user information."""
    permission_classes = [UserUpdatePermission]
    
    @extend_schema(
        request=UserUpdateSerializer,
        responses={200: UserUpdateSerializer},
        description="Update user information",
        operation_id="user_update_self" if not "user_id" else "user_update_by_id",
        examples=[
            OpenApiExample(
                'User Update Example',
                value={
                    'first_name': 'Jane',
                    'last_name': 'Smith'
                },
                request_only=True,
            ),
        ]
    )
    def put(self, request, user_id=None):
        """Handle single user update."""
        # Allow users to update their own profile or staff to update any user
        if user_id:
            if not request.user.is_staff and request.user.id != user_id:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            user = request.user
        
        serializer = UserUpdateSerializer(user, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RoleListCreateView(generics.ListCreateAPIView):
    """List all roles or create new ones."""
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [CanManageRoles]
    
    @extend_schema(
        request=RoleSerializer,
        responses={201: RoleSerializer},
        description="Create a new role",
        examples=[
            OpenApiExample(
                'Role Creation Example',
                value={
                    'role_name': 'TestRole',
                    'description': 'A test role for demonstration'
                },
                request_only=True,
            ),
        ]
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class RoleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific role."""
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [CanManageRoles]
    
    @extend_schema(
        responses={200: RoleSerializer},
        description="Retrieve a specific role"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        request=RoleSerializer,
        responses={200: RoleSerializer},
        description="Update a specific role"
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)
    
    @extend_schema(
        responses={204: None},
        description="Delete a specific role"
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class PermissionListCreateView(generics.ListCreateAPIView):
    """List all permissions or create new ones."""
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [CanManageRoles]
    
    @extend_schema(
        request=PermissionSerializer,
        responses={201: PermissionSerializer},
        description="Create a new permission",
        examples=[
            OpenApiExample(
                'Permission Creation Example',
                value={
                    'permission_key': 'create_user',
                    'description': 'Permission to create new users'
                },
                request_only=True,
            ),
        ]
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class PermissionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific permission."""
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [CanManageRoles]
    
    @extend_schema(
        responses={200: PermissionSerializer},
        description="Retrieve a specific permission"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        request=PermissionSerializer,
        responses={200: PermissionSerializer},
        description="Update a specific permission"
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)
    
    @extend_schema(
        responses={204: None},
        description="Delete a specific permission"
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class UserRoleAssignSerializer(serializers.Serializer):
    """Serializer for user role assignment request."""
    user_id = serializers.IntegerField(help_text="ID of the user to assign role to")
    role_id = serializers.IntegerField(help_text="ID of the role to assign")


class UserRoleUpdateSerializer(serializers.Serializer):
    """Serializer for user role update request."""
    role_id = serializers.IntegerField(help_text="ID of the role to assign to the user")
    
    
class UserRolesByNameSerializer(serializers.Serializer):
    """Serializer for user role assignment by role name."""
    role_name = serializers.CharField(help_text="Name of the role to assign")


class UserRolesListView(APIView):
    """List all user-role assignments or assign roles generally."""
    permission_classes = [CanAssignRoles]
    
    @extend_schema(
        responses={200: UserRolesSerializer(many=True)},
        description="Get all user-role assignments",
        operation_id="user_roles_list_all"
    )
    def get(self, request):
        """Get all active user-role assignments."""
        roles = UserRoles.objects.filter(is_active=True)
        serializer = UserRolesSerializer(roles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @extend_schema(
        request=UserRoleAssignSerializer,
        responses={201: UserRolesSerializer},
        description="Assign a role to a user using user_id and role_id",
        operation_id="user_roles_assign_general",
        examples=[
            OpenApiExample(
                'Role Assignment Example',
                value={
                    'user_id': 1,
                    'role_id': 2
                },
                request_only=True,
            ),
        ]
    )
    def post(self, request):
        """Assign a role to a user using user_id and role_id."""
        return self._single_assign_role(request.data)
    
    def _single_assign_role(self, data):
        """Assign a role to a single user (single active role system) - always create new instances."""
        user_id = data.get('user_id')
        role_id = data.get('role_id')
        
        if not user_id or not role_id:
            return Response(
                {'error': 'user_id and role_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(id=user_id)
            role = Role.objects.get(id=role_id)
            
            with transaction.atomic():
                # Disable ALL current active roles for this user (single active role system)
                current_assignments = UserRoles.objects.filter(user=user, is_active=True)
                disabled_roles = []
                
                for assignment in current_assignments:
                    assignment.disable()
                    disabled_roles.append(assignment.role.role_name)
                
                if disabled_roles:
                    console.print(f"[yellow]• Disabled previous roles for {user.email}: {', '.join(disabled_roles)}[/yellow]")
                
                # ALWAYS create a new UserRole instance for proper auditing trail
                user_role = UserRoles.objects.create(
                    user=user,
                    role=role,
                    is_active=True
                )
                console.print(f"[green]✓ Created new role assignment {role.role_name} for user {user.email}[/green]")
            
            serializer = UserRolesSerializer(user_role)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        except (User.DoesNotExist, Role.DoesNotExist) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )


class UserRolesView(APIView):
    """Manage roles for a specific user."""
    permission_classes = [CanAssignRoles]
    
    @extend_schema(
        responses={200: UserRolesSerializer(many=True)},
        description="Get roles for a specific user",
        operation_id="user_roles_list_by_user"
    )
    def get(self, request, user_id):
        """Get roles for a specific user."""
        try:
            user = User.objects.get(id=user_id)
            roles = UserRoles.objects.filter(user=user, is_active=True)
            serializer = UserRolesSerializer(roles, many=True)
            return Response({
                'user': UserSerializer(user).data,
                'roles': serializer.data
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @extend_schema(
        request=UserRolesByNameSerializer,
        responses={201: UserRolesSerializer},
        description="Assign a role to a specific user using role name",
        operation_id="user_roles_assign_to_user",
        examples=[
            OpenApiExample(
                'Role Assignment by Name Example',
                value={
                    'role_name': 'Member'
                },
                request_only=True,
            ),
        ]
    )
    def post(self, request, user_id):
        """Assign a role to a specific user using role name."""
        role_name = request.data.get('role_name')
        if not role_name:
            return Response(
                {'error': 'role_name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            role = Role.objects.get(role_name=role_name)
            data = {'user_id': user_id, 'role_id': role.id}
            return self._single_assign_role(data)
        except Role.DoesNotExist:
            return Response(
                {'error': f'Role {role_name} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def _single_assign_role(self, data):
        """Assign a role to a single user (single active role system) - always create new instances."""
        user_id = data.get('user_id')
        role_id = data.get('role_id')
        
        try:
            user = User.objects.get(id=user_id)
            role = Role.objects.get(id=role_id)
            
            with transaction.atomic():
                # Disable ALL current active roles for this user (single active role system)
                current_assignments = UserRoles.objects.filter(user=user, is_active=True)
                disabled_roles = []
                
                for assignment in current_assignments:
                    assignment.disable()
                    disabled_roles.append(assignment.role.role_name)
                
                if disabled_roles:
                    console.print(f"[yellow]• Disabled previous roles for {user.email}: {', '.join(disabled_roles)}[/yellow]")
                
                # ALWAYS create a new UserRole instance for proper auditing trail
                user_role = UserRoles.objects.create(
                    user=user,
                    role=role,
                    is_active=True
                )
                console.print(f"[green]✓ Created new role assignment {role.role_name} for user {user.email}[/green]")
            
            serializer = UserRolesSerializer(user_role)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        except (User.DoesNotExist, Role.DoesNotExist) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @extend_schema(
        request=UserRoleUpdateSerializer,
        responses={200: UserRolesSerializer},
        description="Update the role for a specific user",
        operation_id="user_roles_update_for_user",
        examples=[
            OpenApiExample(
                'Role Update Example',
                value={
                    'role_id': 1
                },
                request_only=True,
            ),
        ]
    )
    def put(self, request, user_id):
        """Update the role for a specific user (single active role system) - always create new instances."""
        try:
            user = User.objects.get(id=user_id)
            role_id = request.data.get('role_id')
            
            if not role_id:
                return Response(
                    {'error': 'role_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                role = Role.objects.get(id=role_id)
            except Role.DoesNotExist:
                return Response(
                    {'error': f'Role with id {role_id} does not exist'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            with transaction.atomic():
                # Disable ALL current active roles for this user (single active role system)
                current_assignments = UserRoles.objects.filter(user=user, is_active=True)
                disabled_roles = []
                
                for assignment in current_assignments:
                    assignment.disable()
                    disabled_roles.append(assignment.role.role_name)
                
                if disabled_roles:
                    console.print(f"[yellow]• Disabled previous roles for {user.email}: {', '.join(disabled_roles)}[/yellow]")
                
                # ALWAYS create a new UserRole instance for proper auditing trail
                user_role = UserRoles.objects.create(
                    user=user,
                    role=role,
                    is_active=True
                )
                console.print(f"[green]✓ Created new role assignment {role.role_name} for user {user.email}[/green]")
                
                serializer = UserRolesSerializer(user_role)
                return Response(serializer.data, status=status.HTTP_200_OK)
        
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @extend_schema(
        responses={200: UserRolesSerializer},
        description="Remove/disable the active role for a specific user and assign Member role as fallback",
        operation_id="user_roles_delete_for_user"
    )
    def delete(self, request, user_id):
        """Remove/disable the active role for a specific user and assign Member role as fallback."""
        try:
            user = User.objects.get(id=user_id)
            
            with transaction.atomic():
                # Get current active roles
                current_assignments = UserRoles.objects.filter(user=user, is_active=True)
                
                if not current_assignments.exists():
                    return Response(
                        {'error': 'User has no active roles to remove'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Disable all current active roles (for auditing)
                disabled_roles = []
                for assignment in current_assignments:
                    assignment.disable()
                    disabled_roles.append(assignment.role.role_name)
                
                console.print(f"[yellow]• Disabled roles for {user.email}: {', '.join(disabled_roles)}[/yellow]")
                
                # Assign Member role as fallback (required for all users) - always create new instance
                try:
                    member_role = Role.objects.get(role_name='Member')
                    
                    # ALWAYS create a new Member role instance for proper auditing trail
                    member_assignment = UserRoles.objects.create(
                        user=user,
                        role=member_role,
                        is_active=True
                    )
                    console.print(f"[green]✓ Created new Member role assignment for user {user.email}[/green]")
                    
                    serializer = UserRolesSerializer(member_assignment)
                    return Response({
                        'message': 'Previous roles disabled. User assigned Member role as fallback.',
                        'disabled_roles': disabled_roles,
                        'current_role': serializer.data
                    }, status=status.HTTP_200_OK)
                    
                except Role.DoesNotExist:
                    return Response(
                        {'error': 'Member role does not exist. Cannot assign fallback role.'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
        
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class UserProfileView(APIView):
    """Get user profile with roles and permissions."""
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={200: dict},
        description="Get user profile with roles, permissions, and supervisor details",
        operation_id="user_profile_self" if not "user_id" else "user_profile_by_id"
    )
    def get(self, request, user_id=None):
        if user_id:
            if not request.user.is_staff and request.user.id != user_id:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            user = request.user
        
        roles = user.get_user_roles()
        permissions = user.get_user_permissions()
        
        # Check if user is a supervisor
        is_supervisor = hasattr(user, 'supervisor')
        supervisor_data = None
        if is_supervisor:
            supervisor_data = SupervisorSerializer(user.supervisor).data
        
        return Response({
            'user': UserSerializer(user).data,
            'roles': [{'id': role.id, 'name': role.role_name} for role in roles],
            'permissions': [{'id': perm.id, 'key': perm.permission_key} for perm in permissions],
            'is_supervisor': is_supervisor,
            'supervisor_details': supervisor_data
        }, status=status.HTTP_200_OK)
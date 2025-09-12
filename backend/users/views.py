from django.shortcuts import render
from rest_framework import status, generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from django.db import transaction
from .models import User, Role, Permission, UserRoles, Supervisor, Campus
from .serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    RoleSerializer, PermissionSerializer, UserRolesSerializer,
    SupervisorSerializer
)
from rich.console import Console
import logging

# Configure rich console
console = Console()
logger = logging.getLogger(__name__)


class LoginView(APIView):
    """Login user with email and password."""
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            email = request.data.get('email')
            password = request.data.get('password')
            
            if not email or not password:
                return Response(
                    {'error': 'Email and password are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
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


class RegisterView(APIView):
    """Register a new user with optional role assignment and supervisor creation."""
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            data = request.data
            
            # Handle single user or bulk registration
            if isinstance(data, list):
                return self._bulk_register(data)
            else:
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
    
    def _bulk_register(self, data_list):
        """Register multiple users."""
        results = []
        errors = []
        
        with transaction.atomic():
            for i, data in enumerate(data_list):
                try:
                    response = self._single_register(data)
                    if response.status_code == status.HTTP_201_CREATED:
                        results.append(response.data)
                    else:
                        errors.append({'index': i, 'error': response.data})
                except Exception as e:
                    errors.append({'index': i, 'error': str(e)})
        
        return Response({
            'success_count': len(results),
            'error_count': len(errors),
            'results': results,
            'errors': errors
        }, status=status.HTTP_201_CREATED if results else status.HTTP_400_BAD_REQUEST)
    
    def _assign_roles(self, user, role_names):
        """Assign roles to a user."""
        for role_name in role_names:
            try:
                role = Role.objects.get(role_name=role_name)
                # Disable any existing active role assignments for this role
                existing_assignments = UserRoles.objects.filter(
                    user=user, role=role, is_active=True
                )
                for assignment in existing_assignments:
                    assignment.disable()
                
                # Create new assignment
                UserRoles.objects.create(user=user, role=role)
            except Role.DoesNotExist:
                console.print(f"[yellow]Warning: Role '{role_name}' does not exist[/yellow]")


class UserUpdateView(APIView):
    """Update user information."""
    permission_classes = [IsAuthenticated]
    
    def put(self, request, user_id=None):
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
    
    def patch(self, request, user_id=None):
        """Handle bulk user updates."""
        data = request.data
        
        if isinstance(data, list):
            results = []
            errors = []
            
            for item in data:
                user_id = item.get('id')
                if not user_id:
                    errors.append({'error': 'User ID is required', 'data': item})
                    continue
                
                try:
                    user = User.objects.get(id=user_id)
                    if not request.user.is_staff and request.user.id != user_id:
                        errors.append({'error': 'Permission denied', 'user_id': user_id})
                        continue
                    
                    serializer = UserUpdateSerializer(user, data=item, partial=True)
                    if serializer.is_valid():
                        serializer.save()
                        results.append(serializer.data)
                    else:
                        errors.append({'user_id': user_id, 'errors': serializer.errors})
                
                except User.DoesNotExist:
                    errors.append({'error': 'User not found', 'user_id': user_id})
            
            return Response({
                'success_count': len(results),
                'error_count': len(errors),
                'results': results,
                'errors': errors
            }, status=status.HTTP_200_OK)
        
        return self.put(request, user_id)


class RoleListCreateView(generics.ListCreateAPIView):
    """List all roles or create new ones."""
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        data = request.data
        
        # Handle bulk creation
        if isinstance(data, list):
            results = []
            errors = []
            
            for item in data:
                serializer = RoleSerializer(data=item)
                if serializer.is_valid():
                    serializer.save()
                    results.append(serializer.data)
                else:
                    errors.append({'data': item, 'errors': serializer.errors})
            
            return Response({
                'success_count': len(results),
                'error_count': len(errors),
                'results': results,
                'errors': errors
            }, status=status.HTTP_201_CREATED)
        
        return super().post(request)


class RoleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific role."""
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAuthenticated]


class PermissionListCreateView(generics.ListCreateAPIView):
    """List all permissions or create new ones."""
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        data = request.data
        
        # Handle bulk creation
        if isinstance(data, list):
            results = []
            errors = []
            
            for item in data:
                serializer = PermissionSerializer(data=item)
                if serializer.is_valid():
                    serializer.save()
                    results.append(serializer.data)
                else:
                    errors.append({'data': item, 'errors': serializer.errors})
            
            return Response({
                'success_count': len(results),
                'error_count': len(errors),
                'results': results,
                'errors': errors
            }, status=status.HTTP_201_CREATED)
        
        return super().post(request)


class PermissionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific permission."""
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated]


class UserRolesView(APIView):
    """Assign, update, or list user roles."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, user_id=None):
        """Get roles for a specific user or all user-role assignments."""
        if user_id:
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
        else:
            # Return all active user-role assignments
            roles = UserRoles.objects.filter(is_active=True)
            serializer = UserRolesSerializer(roles, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request):
        """Assign roles to users (single or bulk)."""
        data = request.data
        
        if isinstance(data, list):
            return self._bulk_assign_roles(data)
        else:
            return self._single_assign_role(data)
    
    def _single_assign_role(self, data):
        """Assign a role to a single user."""
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
                # Disable all current active roles for this user (single active role system)
                current_assignments = UserRoles.objects.filter(user=user, is_active=True)
                for assignment in current_assignments:
                    assignment.disable()
                
                # Create or reactivate the role assignment
                user_role, created = UserRoles.objects.get_or_create(
                    user=user,
                    role=role,
                    defaults={'is_active': True}
                )
                if not created and not user_role.is_active:
                    # Reactivate existing inactive role
                    user_role.is_active = True
                    user_role.disabled_at = None
                    user_role.save()
            
            serializer = UserRolesSerializer(user_role)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        except (User.DoesNotExist, Role.DoesNotExist) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def _bulk_assign_roles(self, data_list):
        """Assign roles to multiple users."""
        results = []
        errors = []
        
        with transaction.atomic():
            for item in data_list:
                try:
                    response = self._single_assign_role(item)
                    if response.status_code == status.HTTP_201_CREATED:
                        results.append(response.data)
                    else:
                        errors.append({'data': item, 'error': response.data})
                except Exception as e:
                    errors.append({'data': item, 'error': str(e)})
        
        return Response({
            'success_count': len(results),
            'error_count': len(errors),
            'results': results,
            'errors': errors
        }, status=status.HTTP_201_CREATED if results else status.HTTP_400_BAD_REQUEST)
    
    def put(self, request, user_id):
        """Update all roles for a specific user."""
        try:
            user = User.objects.get(id=user_id)
            # Handle both JSON and form data properly
            if hasattr(request.data, 'getlist'):
                # Form data (QueryDict)
                role_ids = request.data.getlist('role_ids')
            else:
                # JSON data
                role_ids = request.data.get('role_ids', [])
            
            # Ensure role_ids is a list and convert to integers
            if not isinstance(role_ids, list):
                role_ids = [role_ids] if role_ids is not None else []
            role_ids = [int(rid) for rid in role_ids if rid]
            
            with transaction.atomic():
                # First, disable all current active roles
                current_assignments = UserRoles.objects.filter(user=user, is_active=True)
                for assignment in current_assignments:
                    assignment.disable()
                
                # Now assign new roles
                new_assignments = []
                for role_id in role_ids:
                    try:
                        role = Role.objects.get(id=role_id)
                        # Create new active role assignment
                        user_role, created = UserRoles.objects.get_or_create(
                            user=user,
                            role=role,
                            defaults={'is_active': True}
                        )
                        if not created and not user_role.is_active:
                            # Reactivate existing inactive role
                            user_role.is_active = True
                            user_role.disabled_at = None
                            user_role.save()
                        new_assignments.append(user_role)
                    except Role.DoesNotExist:
                        console.print(f"[yellow]Warning: Role with id {role_id} does not exist[/yellow]")
                
                serializer = UserRolesSerializer(new_assignments, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
        
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def delete(self, request, user_id, role_id):
        """Disable a specific user role assignment."""
        try:
            user = User.objects.get(id=user_id)
            role = Role.objects.get(id=role_id)
            
            assignment = UserRoles.objects.filter(
                user=user, role=role, is_active=True
            ).first()
            
            if assignment:
                assignment.disable()
                return Response(
                    {'message': 'Role assignment disabled'},
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {'error': 'Active role assignment not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        except (User.DoesNotExist, Role.DoesNotExist):
            return Response(
                {'error': 'User or role not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class UserProfileView(APIView):
    """Get user profile with roles and permissions."""
    permission_classes = [IsAuthenticated]
    
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


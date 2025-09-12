from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
import logging
from rich.console import Console
from rich.logging import RichHandler

# Configure rich logging
console = Console()
logger = logging.getLogger(__name__)

# Add Rich handler if not already configured
if not logger.handlers:
    logger.addHandler(RichHandler(console=console))
    logger.setLevel(logging.INFO)


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication with OAuth support."""
    
    def create_user(self, email, password=None, role_name=None, **extra_fields):
        """Create and return a regular user with an email, password and role assignment."""
        if not email:
            raise ValueError('The Email field must be set')
        
        # Import here to avoid circular imports
        from django.db import transaction
        
        email = self.normalize_email(email)
        extra_fields.setdefault('is_active', True)
        
        # Ensure default role is always Member if not specified
        if not role_name:
            role_name = 'Member'
            console.print(f"[yellow]No role specified for user {email}, assigning default role: {role_name}[/yellow]")
        
        with transaction.atomic():
            user = self.model(email=email, **extra_fields)
            if password:
                user.set_password(password)
            user.save(using=self._db)
            
            # Assign role to user - create role if it doesn't exist
            self._assign_role_to_user(user, role_name)
            
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and return a superuser with an email, password and Admin role."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        
        # Superusers always get Admin role
        return self.create_user(email, password, role_name='Admin', **extra_fields)
    
    def update_user(self, user_id, **extra_fields):
        """Update user details."""
        try:
            user = self.get(pk=user_id)
            for field, value in extra_fields.items():
                setattr(user, field, value)
            user.save(using=self._db)
            return user
        except self.model.DoesNotExist:
            return None
    
    def delete_user(self, user_id):
        """Delete a user by ID."""
        try:
            user = self.get(pk=user_id)
            user.delete()
            return True
        except self.model.DoesNotExist:
            return False
    
    def create_user_with_oauth(self, email, role_name=None, **extra_fields):
        """Create a user authenticated via an external OAuth provider with role assignment."""
        # OAuth users get Member role by default
        if not role_name:
            role_name = 'Member'
        
        # OAuth users should not have usable passwords
        extra_fields.setdefault('is_active', True)
        user = self.create_user(email, password=None, role_name=role_name, **extra_fields)
        # Ensure OAuth users don't have usable passwords
        user.set_unusable_password()
        user.save(using=self._db)
        return user
    
    def login_user(self, email, password):
        """Authenticate and return user with tokens."""
        try:
            user = authenticate(username=email, password=password)
            if user and user.is_active:
                tokens = self.get_tokens_for_user(user)
                return {
                    'user': user,
                    'tokens': tokens,
                    'success': True
                }
            return {'success': False, 'message': 'Invalid credentials'}
        except Exception as e:
            console.print(f"[red]Login error:[/red] {str(e)}")
            return {'success': False, 'message': 'Login failed'}
    
    def register_user(self, email, password, role_name=None, **extra_fields):
        """Register a new user with role assignment."""
        try:
            if self.filter(email=email).exists():
                return {'success': False, 'message': 'User already exists'}
            
            # Default to Member role if not specified
            if not role_name:
                role_name = 'Member'
            
            user = self.create_user(email=email, password=password, role_name=role_name, **extra_fields)
            tokens = self.get_tokens_for_user(user)
            return {
                'user': user,
                'tokens': tokens,
                'success': True
            }
        except Exception as e:
            console.print(f"[red]Registration error:[/red] {str(e)}")
            return {'success': False, 'message': f'Registration failed: {str(e)}'}
    
    def oauth_login_or_create(self, email, role_name=None, **extra_fields):
        """OAuth login or create user with role assignment."""
        try:
            user, created = self.get_or_create(
                email=email,
                defaults=extra_fields
            )
            
            # If user was created, assign role
            if created:
                if not role_name:
                    role_name = 'Member'  # Default role for OAuth users
                self._assign_role_to_user(user, role_name)
                # Ensure OAuth users don't have usable passwords
                user.set_unusable_password()
                user.save(using=self._db)
                console.print(f"[green]✓ New OAuth user created with role:[/green] {email} -> {role_name}")
            
            tokens = self.get_tokens_for_user(user)
            return {
                'user': user,
                'tokens': tokens,
                'success': True,
                'created': created
            }
        except Exception as e:
            console.print(f"[red]OAuth login error:[/red] {str(e)}")
            return {'success': False, 'message': 'OAuth authentication failed'}
    
    def get_tokens_for_user(self, user):
        """Generate JWT tokens for user."""
        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
    
    def refresh_token(self, refresh_token):
        """Refresh access token."""
        try:
            refresh = RefreshToken(refresh_token)
            return {
                'access': str(refresh.access_token),
                'success': True
            }
        except Exception as e:
            console.print(f"[red]Token refresh error:[/red] {str(e)}")
            return {'success': False, 'message': 'Invalid refresh token'}
    
    def _assign_role_to_user(self, user, role_name):
        """Helper method to assign a role to a user (single active role only)."""
        from django.db import transaction
        
        try:
            # Get the Role model class dynamically to avoid circular imports
            Role = self.model._meta.apps.get_model('users', 'Role')
            UserRoles = self.model._meta.apps.get_model('users', 'UserRoles')
            
            # Define essential roles that can be auto-created
            essential_roles = ['Admin', 'Member', 'Student', 'Lecturer']
            
            # Get or create the role (only for essential roles)
            try:
                role = Role.objects.get(role_name=role_name)
            except Role.DoesNotExist:
                if role_name in essential_roles:
                    role, created = Role.objects.get_or_create(
                        role_name=role_name,
                        defaults={'description': f'{role_name} role'}
                    )
                    if created:
                        console.print(f"[green]✓ Created essential role:[/green] {role_name}")
                else:
                    raise ValueError(f"Role '{role_name}' does not exist and is not an essential role")
            
            with transaction.atomic():
                # First, disable all currently active roles for this user
                previous_roles = UserRoles.objects.filter(user=user, is_active=True)
                disabled_roles = []
                
                for user_role in previous_roles:
                    if user_role.role.role_name != role_name:  # Don't disable if it's the same role
                        user_role.disable()
                        disabled_roles.append(user_role.role.role_name)
                
                if disabled_roles:
                    console.print(f"[yellow]• Disabled previous roles for {user.email}: {', '.join(disabled_roles)}[/yellow]")
                
                # Check if user already has this role (might be inactive)
                existing_role, created = UserRoles.objects.get_or_create(
                    user=user,
                    role=role,
                    defaults={'is_active': True}
                )
                
                if not created:
                    if not existing_role.is_active:
                        # Reactivate the role
                        existing_role.is_active = True
                        existing_role.disabled_at = None
                        existing_role.save()
                        console.print(f"[green]✓ Reactivated role {role_name} for user {user.email}[/green]")
                    else:
                        console.print(f"[yellow]• User {user.email} already has active role {role_name}[/yellow]")
                else:
                    console.print(f"[green]✓ Assigned role {role_name} to user {user.email}[/green]")
            
        except Exception as e:
            console.print(f"[red]✗ Error assigning role to user:[/red] {str(e)}")
            raise
    


class User(AbstractBaseUser):
    """
    Custom User model with email as the unique identifier.
    Matches the database schema requirements exactly.
    No built-in Django permissions - you'll implement your own permission system.
    """
    email = models.EmailField(unique=True, null=False, blank=False)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Required for admin access
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Email is already required as USERNAME_FIELD
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        full_name = f'{self.first_name} {self.last_name}'
        return full_name.strip()
    
    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name
    
    # Required methods for Django admin compatibility without PermissionsMixin
    def has_perm(self, perm, obj=None):
        """
        Return True if user has the specified permission.
        You'll implement your custom permission logic here.
        """
        return self.is_staff  # For now, staff users have all permissions
    
    def has_module_perms(self, app_label):
        """
        Return True if user has permissions to view the app `app_label`.
        You'll implement your custom permission logic here.
        """
        return self.is_staff  # For now, staff users can access all apps
    
    def has_custom_permission(self, permission_key):
        """Check if user has a specific custom permission."""
        return UserRoles.objects.filter(
            user=self,
            is_active=True,
            role__rolepermission__permission__permission_key=permission_key
        ).exists()
    
    def get_user_roles(self):
        """Get all active roles assigned to this user (should be only one)."""
        return Role.objects.filter(userroles__user=self, userroles__is_active=True)
    
    def get_active_role(self):
        """Get the user's active role (single role system)."""
        user_role = UserRoles.objects.filter(user=self, is_active=True).select_related('role').first()
        return user_role.role if user_role else None
    
    def get_active_role_name(self):
        """Get the user's active role name."""
        role = self.get_active_role()
        return role.role_name if role else None
    
    def get_user_permissions(self):
        """Get all permissions assigned to this user through active roles."""
        return Permission.objects.filter(
            rolepermission__role__userroles__user=self,
            rolepermission__role__userroles__is_active=True
        ).distinct()
    
    def assign_role(self, role_name):
        """Assign a role to this user (single active role only)."""
        # Use the manager method which handles single active role logic
        User.objects._assign_role_to_user(self, role_name)
    
    def remove_role(self, role_name):
        """Remove/disable a role from this user."""
        try:
            role = Role.objects.get(role_name=role_name)
            user_role = UserRoles.objects.get(user=self, role=role, is_active=True)
            user_role.disable()
            console.print(f"[yellow]• Removed role {role_name} from user {self.email}[/yellow]")
            return True
        except (Role.DoesNotExist, UserRoles.DoesNotExist):
            console.print(f"[red]✗ User {self.email} does not have active role {role_name}[/red]")
            return False
    
    def has_role(self, role_name):
        """Check if user has a specific active role."""
        return UserRoles.objects.filter(
            user=self,
            role__role_name=role_name,
            is_active=True
        ).exists()
    
    def get_primary_role(self):
        """Get the user's active role (same as get_active_role since single role system)."""
        return self.get_active_role()


class Role(models.Model):
    """Role model for custom permission system."""
    role_name = models.CharField(max_length=100, unique=True, null=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
    
    def __str__(self):
        return self.role_name


class Permission(models.Model):
    """Permission model for custom permission system."""
    permission_key = models.CharField(max_length=200, unique=True, null=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Permission'
        verbose_name_plural = 'Permissions'
    
    def __str__(self):
        return self.permission_key


class RolePermission(models.Model):
    """Many-to-many relationship between roles and permissions."""
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ('role', 'permission')
        verbose_name = 'Role Permission'
        verbose_name_plural = 'Role Permissions'
    
    def __str__(self):
        return f"{self.role.role_name} - {self.permission.permission_key}"


class UserRoles(models.Model):
    """Many-to-many relationship between users and roles with auditing support."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)  # For auditing purposes
    disabled_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'User Role'
        verbose_name_plural = 'User Roles'
        # Remove unique_together to allow multiple records for auditing
    
    def __str__(self):
        status = "Active" if self.is_active else "Disabled"
        return f"{self.user.email} - {self.role.role_name} ({status})"
    
    def disable(self):
        """Disable this user role assignment."""
        self.is_active = False
        self.disabled_at = timezone.now()
        self.save()


# Campus Enum Choices
class CampusName(models.TextChoices):
    SB = 'SB', 'Hobart'
    IR = 'IR', 'Launceston'
    ONLINE = 'ONLINE', 'Online'


class Campus(models.Model):
    """Campus model."""
    campus_name = models.CharField(
        max_length=20,
        choices=CampusName.choices,
        unique=True,
        null=False
    )
    campus_location = models.CharField(max_length=255, null=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Campus'
        verbose_name_plural = 'Campuses'
    
    def __str__(self):
        return f"{self.campus_name} - {self.campus_location}"


class Supervisor(models.Model):
    """Supervisor model - specific users who supervise tutors."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, unique=True)
    campus = models.ForeignKey(Campus, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Supervisor'
        verbose_name_plural = 'Supervisors'
    
    def __str__(self):
        return f"Supervisor: {self.user.get_full_name() or self.user.email}"


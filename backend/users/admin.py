from django.contrib import admin
from django import forms
from django.db import transaction
from .models import User, Role, Permission, RolePermission, UserRoles, Campus, Supervisor


class UserRoleInlineForm(forms.ModelForm):
    """Custom form for UserRole inline to handle single active role constraint."""
    
    class Meta:
        model = UserRoles
        fields = ['role', 'is_active']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].queryset = Role.objects.all().order_by('role_name')


class UserRoleInline(admin.TabularInline):
    """Inline for managing user roles with proper auditing."""
    model = UserRoles
    form = UserRoleInlineForm
    extra = 0
    fields = ['role', 'is_active', 'assigned_at', 'disabled_at']
    readonly_fields = ['assigned_at', 'disabled_at']
    
    def get_queryset(self, request):
        """Show all roles (both active and inactive) for auditing purposes."""
        return super().get_queryset(request).select_related('role').order_by('-assigned_at')


class UserAdminForm(forms.ModelForm):
    """Custom form for User admin with role selection."""
    role = forms.ModelChoiceField(
        queryset=Role.objects.all().order_by('role_name'),
        required=False,
        help_text="Select a role for this user. If not specified, Member role will be assigned.",
        empty_label="-- Select Role (defaults to Member) --"
    )
    
    class Meta:
        model = User
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If editing existing user, show their current active role
        if self.instance and self.instance.pk:
            current_role = self.instance.get_active_role()
            if current_role:
                self.fields['role'].initial = current_role


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Custom admin for User model with role management."""
    form = UserAdminForm
    inlines = [UserRoleInline]
    list_display = ['email', 'first_name', 'last_name', 'is_active', 'is_staff', 'created_at', 'get_roles']
    list_filter = ['is_active', 'is_staff', 'created_at']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Authentication', {
            'fields': ('email', 'password')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name')
        }),
        ('Role Assignment', {
            'fields': ('role',),
            'description': 'Select the primary role for this user. Role changes are audited.'
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff'),
        }),
        ('Important Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        ('Create User', {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2', 'role'),
        }),
    )
    
    def get_roles(self, obj):
        """Display user roles."""
        roles = obj.userroles_set.filter(is_active=True)
        if roles:
            role_names = [role.role.role_name for role in roles]
            return ', '.join(role_names)
        return 'No roles assigned'
    get_roles.short_description = 'Active Roles'
    
    def save_model(self, request, obj, form, change):
        """Save user and handle role assignment with proper auditing."""
        # Save user first
        super().save_model(request, obj, form, change)
        
        # Handle role assignment
        selected_role = form.cleaned_data.get('role')
        
        with transaction.atomic():
            if selected_role:
                # Disable all current active roles
                current_assignments = UserRoles.objects.filter(user=obj, is_active=True)
                for assignment in current_assignments:
                    assignment.disable()
                
                # Create new role assignment
                UserRoles.objects.create(
                    user=obj,
                    role=selected_role,
                    is_active=True
                )
                self.message_user(request, f"User {obj.email} assigned role: {selected_role.role_name}")
            
            elif not change:  # New user without role selected
                # Assign default Member role
                try:
                    member_role = Role.objects.get(role_name='Member')
                    UserRoles.objects.create(
                        user=obj,
                        role=member_role,
                        is_active=True
                    )
                    self.message_user(request, f"User {obj.email} assigned default Member role")
                except Role.DoesNotExist:
                    self.message_user(request, f"Warning: Member role not found for user {obj.email}", level='WARNING')


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Admin for Role model."""
    list_display = ['role_name', 'description', 'get_permissions_count', 'get_users_count', 'created_at']
    search_fields = ['role_name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['role_name']
    
    def get_permissions_count(self, obj):
        """Count of permissions for this role."""
        return obj.rolepermission_set.count()
    get_permissions_count.short_description = 'Permissions'
    
    def get_users_count(self, obj):
        """Count of users with this role."""
        return obj.userroles_set.filter(is_active=True).count()
    get_users_count.short_description = 'Users'


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """Admin for Permission model."""
    list_display = ['permission_key', 'description', 'get_roles_count', 'created_at']
    search_fields = ['permission_key', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['permission_key']
    
    def get_roles_count(self, obj):
        """Count of roles with this permission."""
        return obj.rolepermission_set.count()
    get_roles_count.short_description = 'Roles'


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    """Admin for RolePermission model."""
    list_display = ['role', 'permission']
    list_filter = ['role']
    search_fields = ['role__role_name', 'permission__permission_key']
    ordering = ['role__role_name', 'permission__permission_key']
    
    fieldsets = (
        ('Assignment', {
            'fields': ('role', 'permission')
        }),
    )


class UserRolesAdminForm(forms.ModelForm):
    """Custom form for UserRoles admin to handle single active role constraint."""
    
    class Meta:
        model = UserRoles
        fields = '__all__'
    
    def clean(self):
        """Validate single active role constraint."""
        cleaned_data = super().clean()
        user = cleaned_data.get('user')
        role = cleaned_data.get('role')
        is_active = cleaned_data.get('is_active')
        
        if user and role and is_active:
            # Check if user already has another active role
            existing_active = UserRoles.objects.filter(
                user=user,
                is_active=True
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing_active.exists():
                # We'll handle this in save_model instead of raising an error
                # to allow proper auditing by disabling previous roles
                pass
        
        return cleaned_data


@admin.register(UserRoles)
class UserRolesAdmin(admin.ModelAdmin):
    """Admin for UserRoles model with proper auditing."""
    form = UserRolesAdminForm
    list_display = ['user', 'role', 'assigned_at', 'is_active', 'disabled_at']
    list_filter = ['role', 'is_active', 'assigned_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'role__role_name']
    readonly_fields = ['assigned_at', 'disabled_at']
    ordering = ['-assigned_at']
    
    fieldsets = (
        ('Assignment', {
            'fields': ('user', 'role', 'is_active'),
            'description': 'User can only have one active role. Previous active roles will be automatically disabled.'
        }),
        ('Metadata', {
            'fields': ('assigned_at', 'disabled_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Save UserRole with proper auditing for single active role constraint."""
        with transaction.atomic():
            if obj.is_active:
                # If this role is being set as active, disable all other active roles for this user
                other_active_roles = UserRoles.objects.filter(
                    user=obj.user,
                    is_active=True
                ).exclude(pk=obj.pk if obj.pk else None)
                
                disabled_roles = []
                for role_assignment in other_active_roles:
                    role_assignment.disable()
                    disabled_roles.append(role_assignment.role.role_name)
                
                if disabled_roles:
                    self.message_user(
                        request,
                        f"Disabled previous active roles for {obj.user.email}: {', '.join(disabled_roles)}"
                    )
            
            # Always create a new instance for proper auditing (except for the initial save)
            if change and obj.is_active:
                # For updates to active roles, create new instance and disable old one
                if obj.pk:
                    old_instance = UserRoles.objects.get(pk=obj.pk)
                    if old_instance.is_active:
                        old_instance.disable()
                        # Create new instance
                        UserRoles.objects.create(
                            user=obj.user,
                            role=obj.role,
                            is_active=True
                        )
                        self.message_user(
                            request,
                            f"Created new role assignment for {obj.user.email}: {obj.role.role_name} (auditing)"
                        )
                        return
            
            # Save normally for new instances or inactive role changes
            super().save_model(request, obj, form, change)
            
            # Check if user has any active roles, if not assign Member role
            if not change or not obj.is_active:
                active_roles = UserRoles.objects.filter(user=obj.user, is_active=True)
                if not active_roles.exists():
                    try:
                        member_role = Role.objects.get(role_name='Member')
                        UserRoles.objects.create(
                            user=obj.user,
                            role=member_role,
                            is_active=True
                        )
                        self.message_user(
                            request,
                            f"Assigned fallback Member role to {obj.user.email}"
                        )
                    except Role.DoesNotExist:
                        self.message_user(
                            request,
                            f"Warning: Member role not found for fallback assignment to {obj.user.email}",
                            level='WARNING'
                        )


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    """Admin for Campus model."""
    list_display = ['campus_name', 'campus_location', 'get_users_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['campus_name', 'campus_location']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['campus_name']
    
    fieldsets = (
        ('Campus Information', {
            'fields': ('campus_name', 'campus_location')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_users_count(self, obj):
        """Count of supervisors in this campus."""
        return obj.supervisor_set.count()
    get_users_count.short_description = 'Supervisors'


@admin.register(Supervisor)
class SupervisorAdmin(admin.ModelAdmin):
    """Admin for Supervisor model."""
    list_display = ['user', 'campus', 'created_at']
    list_filter = ['campus', 'created_at']
    search_fields = [
        'user__email', 'user__first_name', 'user__last_name'
    ]
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Relationship', {
            'fields': ('user', 'campus')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Customize foreign key fields."""
        if db_field.name == 'user':
            kwargs["queryset"] = User.objects.filter(is_active=True).order_by('email')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
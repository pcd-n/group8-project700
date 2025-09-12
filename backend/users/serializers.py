from rest_framework import serializers
from .models import User, Role, Permission, UserRoles, Supervisor, Campus


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name', 
                 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_full_name(self, obj):
        return obj.get_full_name()


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating users with role assignment and supervisor creation."""
    password = serializers.CharField(write_only=True, min_length=8)
    roles = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        allow_empty=True,
        help_text="List of role names to assign to the user"
    )
    is_supervisor = serializers.BooleanField(
        required=False, 
        default=False,
        help_text="Whether to create a supervisor instance for this user"
    )
    campus_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Campus ID if user is a supervisor"
    )
    
    class Meta:
        model = User
        fields = ['email', 'password', 'first_name', 'last_name', 
                 'roles', 'is_supervisor', 'campus_id']
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return value
    
    def validate_campus_id(self, value):
        if value is not None:
            try:
                Campus.objects.get(id=value)
            except Campus.DoesNotExist:
                raise serializers.ValidationError("Campus with this ID does not exist.")
        return value


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user information."""
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'is_active']


class RoleSerializer(serializers.ModelSerializer):
    """Serializer for Role model."""
    
    class Meta:
        model = Role
        fields = ['id', 'role_name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_role_name(self, value):
        # For updates, exclude the current instance from uniqueness check
        if self.instance:
            existing = Role.objects.filter(role_name=value).exclude(id=self.instance.id)
        else:
            existing = Role.objects.filter(role_name=value)
        
        if existing.exists():
            raise serializers.ValidationError("Role with this name already exists.")
        return value


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for Permission model."""
    
    class Meta:
        model = Permission
        fields = ['id', 'permission_key', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_permission_key(self, value):
        # For updates, exclude the current instance from uniqueness check
        if self.instance:
            existing = Permission.objects.filter(permission_key=value).exclude(id=self.instance.id)
        else:
            existing = Permission.objects.filter(permission_key=value)
        
        if existing.exists():
            raise serializers.ValidationError("Permission with this key already exists.")
        return value


class UserRolesSerializer(serializers.ModelSerializer):
    """Serializer for UserRoles model."""
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    role_name = serializers.CharField(source='role.role_name', read_only=True)
    
    class Meta:
        model = UserRoles
        fields = ['id', 'user', 'role', 'user_email', 'user_name', 'role_name',
                 'assigned_at', 'is_active', 'disabled_at']
        read_only_fields = ['id', 'assigned_at', 'disabled_at']


class CampusSerializer(serializers.ModelSerializer):
    """Serializer for Campus model."""
    
    class Meta:
        model = Campus
        fields = ['id', 'campus_name', 'campus_location', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class SupervisorSerializer(serializers.ModelSerializer):
    """Serializer for Supervisor model."""
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    campus_name = serializers.CharField(source='campus.campus_name', read_only=True)
    
    class Meta:
        model = Supervisor
        fields = ['id', 'user', 'campus', 'user_email', 'user_name', 
                 'campus_name', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class RolePermissionSerializer(serializers.Serializer):
    """Serializer for assigning permissions to roles."""
    role_id = serializers.IntegerField()
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True
    )
    
    def validate_role_id(self, value):
        try:
            Role.objects.get(id=value)
        except Role.DoesNotExist:
            raise serializers.ValidationError("Role with this ID does not exist.")
        return value
    
    def validate_permission_ids(self, value):
        for perm_id in value:
            try:
                Permission.objects.get(id=perm_id)
            except Permission.DoesNotExist:
                raise serializers.ValidationError(f"Permission with ID {perm_id} does not exist.")
        return value


class UserBulkRoleAssignmentSerializer(serializers.Serializer):
    """Serializer for bulk user role assignments."""
    user_id = serializers.IntegerField()
    role_id = serializers.IntegerField()
    
    def validate_user_id(self, value):
        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this ID does not exist.")
        return value
    
    def validate_role_id(self, value):
        try:
            Role.objects.get(id=value)
        except Role.DoesNotExist:
            raise serializers.ValidationError("Role with this ID does not exist.")
        return value

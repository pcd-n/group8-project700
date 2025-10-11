#backend/users/serializers.py
from rest_framework import serializers
from .models import (
    User, Role, Permission, UserRoles, Supervisor, Campus
)

DEFAULT_DB = "default"

class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model (read)."""
    full_name = serializers.SerializerMethodField()
    role_name = serializers.SerializerMethodField()
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username', 'email',
            'first_name', 'last_name', 'full_name', 'role_name',
            'is_active', 'note', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'role_name', 'full_name']

    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_role_name(self, obj):
        # Uses default DB through the model helper.
        return obj.get_active_role_name()


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating users with an INITIAL role assignment.
    Admin-only usage per your policy.
    """
    password = serializers.CharField(write_only=True, min_length=8)
    note = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    # one active role at a time; "Admin", "Coordinator", "Tutor"
    role_name = serializers.ChoiceField(
        choices=[('Admin', 'Admin'), ('Coordinator', 'Coordinator'), ('Tutor', 'Tutor')],
        required=True
    )

    # Optional supervisor toggle (keep if you still need Supervisor instances)
    is_supervisor = serializers.BooleanField(required=False, default=False)
    campus_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            'username', 'password',
            'email', 'first_name', 'last_name',
            'role_name',
            'is_supervisor', 'campus_id', 'note'
        ]

    # --- Validation ---
    def validate_email(self, value):
        if self.context.get('allow_existing_email'):
            return value
        if value and User.objects.using(DEFAULT_DB).filter(email__iexact=value).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return value
    
    def validate_username(self, value):
        if User.objects.using(DEFAULT_DB).filter(username=value).exists():
            raise serializers.ValidationError("User with this username already exists.")
        return value

    def validate_campus_id(self, value):
        if value is not None:
            if not Campus.objects.using(DEFAULT_DB).filter(id=value).exists():
                raise serializers.ValidationError("Campus with this ID does not exist.")
        return value

    def validate(self, attrs):
        # if supervisor requested, campus must be provided
        if attrs.get('is_supervisor') and not attrs.get('campus_id'):
            raise serializers.ValidationError({"campus_id": "Campus is required when is_supervisor is true."})
        return attrs

    # --- Create ---

    def create(self, validated_data):
        role_name = validated_data.pop('role_name')
        is_supervisor = validated_data.pop('is_supervisor', False)
        campus_id = validated_data.pop('campus_id', None)
        password = validated_data.pop('password')

        # Create the user on DEFAULT_DB (manager enforces that too)
        user = User.objects.create_user(
            password=password,
            role_name=role_name,
            **validated_data
        )

        # Optionally create Supervisor record on DEFAULT_DB
        if is_supervisor:
            campus = Campus.objects.using(DEFAULT_DB).get(id=campus_id)
            Supervisor.objects.using(DEFAULT_DB).create(user=user, campus=campus)

        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user information (no role or password here)."""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'is_active', 'note']


# --- RBAC + objects on DEFAULT_DB --------------------------------------------

class RoleSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='role_name', read_only=True)
    class Meta:
        model = Role
        fields = ['id', 'role_name', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_role_name(self, value):
        qs = Role.objects.using(DEFAULT_DB).filter(role_name=value)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("Role with this name already exists.")
        return value


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'permission_key', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_permission_key(self, value):
        qs = Permission.objects.using(DEFAULT_DB).filter(permission_key=value)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError("Permission with this key already exists.")
        return value


class UserRolesSerializer(serializers.ModelSerializer):
    """Serializer for UserRoles model (read)."""
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_note = serializers.CharField(source='user.note', read_only=True)
    role_name = serializers.CharField(source='role.role_name', read_only=True)

    class Meta:
        model = UserRoles
        fields = ['id', 'user', 'role', 'user_username', 'user_email', 'user_name',
                  'user_note', 'role_name', 'assigned_at', 'is_active', 'disabled_at']
        read_only_fields = ['id', 'assigned_at', 'disabled_at']

class CampusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campus
        fields = ['id', 'campus_name', 'campus_location', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class SupervisorSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    campus_name = serializers.CharField(source='campus.campus_name', read_only=True)

    class Meta:
        model = Supervisor
        fields = [
            'id', 'user', 'campus',
            'user_username', 'user_name', 'campus_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# --- Admin helpers (optional but handy) --------------------------------------

class RolePermissionSerializer(serializers.Serializer):
    """Assign a set of permission IDs to a role (Admin only)."""
    role_id = serializers.IntegerField()
    permission_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)

    def validate_role_id(self, value):
        if not Role.objects.using(DEFAULT_DB).filter(id=value).exists():
            raise serializers.ValidationError("Role with this ID does not exist.")
        return value

    def validate_permission_ids(self, value):
        missing = [
            pid for pid in value
            if not Permission.objects.using(DEFAULT_DB).filter(id=pid).exists()
        ]
        if missing:
            raise serializers.ValidationError(f"Permissions not found: {missing}")
        return value


class UserBulkRoleAssignmentSerializer(serializers.Serializer):
    """Bulk (re)assignment helper: set a specific role for a specific user."""
    user_id = serializers.IntegerField()
    role_id = serializers.IntegerField()

    def validate_user_id(self, value):
        if not User.objects.using(DEFAULT_DB).filter(id=value).exists():
            raise serializers.ValidationError("User with this ID does not exist.")
        return value

    def validate_role_id(self, value):
        if not Role.objects.using(DEFAULT_DB).filter(id=value).exists():
            raise serializers.ValidationError("Role with this ID does not exist.")
        return value

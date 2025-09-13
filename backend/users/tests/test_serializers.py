"""
Test serializers for the users app.
"""
from django.test import TestCase
from rest_framework import serializers
from users.models import User, Role, Permission, UserRoles, Campus, CampusName, Supervisor
from users.serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    RoleSerializer, PermissionSerializer, UserRolesSerializer,
    CampusSerializer, SupervisorSerializer, RolePermissionSerializer,
    UserBulkRoleAssignmentSerializer
)


class UserSerializerTestCase(TestCase):
    """Test cases for UserSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
    
    def test_serializer_fields(self):
        """Test that serializer includes correct fields."""
        serializer = UserSerializer(self.user)
        expected_fields = {
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'is_active', 'created_at', 'updated_at'
        }
        self.assertEqual(set(serializer.data.keys()), expected_fields)
    
    def test_full_name_method(self):
        """Test get_full_name method."""
        serializer = UserSerializer(self.user)
        self.assertEqual(serializer.data['full_name'], 'Test User')
    
    def test_read_only_fields(self):
        """Test that certain fields are read-only."""
        serializer = UserSerializer()
        read_only_fields = serializer.Meta.read_only_fields
        expected_read_only = ['id', 'created_at', 'updated_at']
        self.assertEqual(list(read_only_fields), expected_read_only)


class UserCreateSerializerTestCase(TestCase):
    """Test cases for UserCreateSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.campus = Campus.objects.create(
            campus_name=CampusName.SB,
            campus_location='Hobart'
        )
        Role.objects.create(role_name='TestRole', description='Test role')
    
    def test_valid_user_creation_data(self):
        """Test serializer with valid user creation data."""
        data = {
            'email': 'newuser@example.com',
            'password': 'newpass123',
            'first_name': 'New',
            'last_name': 'User',
            'roles': ['TestRole'],
            'is_supervisor': True,
            'campus_id': self.campus.id
        }
        
        serializer = UserCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_password_required(self):
        """Test that password is required."""
        data = {
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        serializer = UserCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)
    
    def test_password_min_length(self):
        """Test password minimum length validation."""
        data = {
            'email': 'newuser@example.com',
            'password': 'short',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        serializer = UserCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)
    
    def test_email_uniqueness_validation(self):
        """Test email uniqueness validation."""
        User.objects.create_user(email='existing@example.com')
        
        data = {
            'email': 'existing@example.com',
            'password': 'newpass123'
        }
        
        serializer = UserCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)
    
    def test_campus_id_validation(self):
        """Test campus ID validation."""
        data = {
            'email': 'newuser@example.com',
            'password': 'newpass123',
            'campus_id': 999  # Non-existent campus
        }
        
        serializer = UserCreateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('campus_id', serializer.errors)
    
    def test_campus_id_null_validation(self):
        """Test that campus_id can be null."""
        data = {
            'email': 'newuser@example.com',
            'password': 'newpass123',
            'campus_id': None
        }
        
        serializer = UserCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_optional_fields(self):
        """Test that roles, is_supervisor, and campus_id are optional."""
        data = {
            'email': 'newuser@example.com',
            'password': 'newpass123'
        }
        
        serializer = UserCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class UserUpdateSerializerTestCase(TestCase):
    """Test cases for UserUpdateSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
    
    def test_valid_update_data(self):
        """Test serializer with valid update data."""
        data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            'is_active': False
        }
        
        serializer = UserUpdateSerializer(self.user, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
    
    def test_partial_update(self):
        """Test partial update functionality."""
        data = {'first_name': 'Updated'}
        
        serializer = UserUpdateSerializer(self.user, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        
        updated_user = serializer.save()
        self.assertEqual(updated_user.first_name, 'Updated')
        self.assertEqual(updated_user.last_name, 'User')  # Unchanged
    
    def test_serializer_fields(self):
        """Test that serializer includes correct fields."""
        serializer = UserUpdateSerializer()
        expected_fields = ['first_name', 'last_name', 'is_active']
        self.assertEqual(serializer.Meta.fields, expected_fields)


class RoleSerializerTestCase(TestCase):
    """Test cases for RoleSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.role = Role.objects.create(
            role_name='TestRole',
            description='Test role description'
        )
    
    def test_serializer_fields(self):
        """Test that serializer includes correct fields."""
        serializer = RoleSerializer(self.role)
        expected_fields = {
            'id', 'role_name', 'description', 'created_at', 'updated_at'
        }
        self.assertEqual(set(serializer.data.keys()), expected_fields)
    
    def test_role_name_uniqueness_validation_create(self):
        """Test role name uniqueness validation for creation."""
        data = {
            'role_name': 'TestRole',  # Already exists
            'description': 'Another test role'
        }
        
        serializer = RoleSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('role_name', serializer.errors)
    
    def test_role_name_uniqueness_validation_update(self):
        """Test role name uniqueness validation for updates."""
        another_role = Role.objects.create(role_name='AnotherRole')
        
        data = {
            'role_name': 'TestRole',  # Trying to use existing name
            'description': 'Updated description'
        }
        
        serializer = RoleSerializer(another_role, data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('role_name', serializer.errors)
    
    def test_role_name_same_value_update(self):
        """Test that updating with same role name is allowed."""
        data = {
            'role_name': 'TestRole',  # Same name
            'description': 'Updated description'
        }
        
        serializer = RoleSerializer(self.role, data=data)
        self.assertTrue(serializer.is_valid())


class PermissionSerializerTestCase(TestCase):
    """Test cases for PermissionSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.permission = Permission.objects.create(
            permission_key='test.permission',
            description='Test permission description'
        )
    
    def test_serializer_fields(self):
        """Test that serializer includes correct fields."""
        serializer = PermissionSerializer(self.permission)
        expected_fields = {
            'id', 'permission_key', 'description', 'created_at', 'updated_at'
        }
        self.assertEqual(set(serializer.data.keys()), expected_fields)
    
    def test_permission_key_uniqueness_validation_create(self):
        """Test permission key uniqueness validation for creation."""
        data = {
            'permission_key': 'test.permission',  # Already exists
            'description': 'Another test permission'
        }
        
        serializer = PermissionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('permission_key', serializer.errors)
    
    def test_permission_key_uniqueness_validation_update(self):
        """Test permission key uniqueness validation for updates."""
        another_permission = Permission.objects.create(permission_key='another.permission')
        
        data = {
            'permission_key': 'test.permission',  # Trying to use existing key
            'description': 'Updated description'
        }
        
        serializer = PermissionSerializer(another_permission, data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('permission_key', serializer.errors)
    
    def test_permission_key_same_value_update(self):
        """Test that updating with same permission key is allowed."""
        data = {
            'permission_key': 'test.permission',  # Same key
            'description': 'Updated description'
        }
        
        serializer = PermissionSerializer(self.permission, data=data)
        self.assertTrue(serializer.is_valid())


class UserRolesSerializerTestCase(TestCase):
    """Test cases for UserRolesSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.role = Role.objects.create(role_name='TestRole')
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.user_role = UserRoles.objects.create(user=self.user, role=self.role)
    
    def test_serializer_fields(self):
        """Test that serializer includes correct fields."""
        serializer = UserRolesSerializer(self.user_role)
        expected_fields = {
            'id', 'user', 'role', 'user_email', 'user_name', 'role_name',
            'assigned_at', 'is_active', 'disabled_at'
        }
        self.assertEqual(set(serializer.data.keys()), expected_fields)
    
    def test_user_email_field(self):
        """Test user_email read-only field."""
        serializer = UserRolesSerializer(self.user_role)
        self.assertEqual(serializer.data['user_email'], 'test@example.com')
    
    def test_user_name_field(self):
        """Test user_name read-only field."""
        serializer = UserRolesSerializer(self.user_role)
        self.assertEqual(serializer.data['user_name'], 'Test User')
    
    def test_role_name_field(self):
        """Test role_name read-only field."""
        serializer = UserRolesSerializer(self.user_role)
        self.assertEqual(serializer.data['role_name'], 'TestRole')


class CampusSerializerTestCase(TestCase):
    """Test cases for CampusSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.campus = Campus.objects.create(
            campus_name=CampusName.SB,
            campus_location='Hobart'
        )
    
    def test_serializer_fields(self):
        """Test that serializer includes correct fields."""
        serializer = CampusSerializer(self.campus)
        expected_fields = {
            'id', 'campus_name', 'campus_location', 'created_at', 'updated_at'
        }
        self.assertEqual(set(serializer.data.keys()), expected_fields)
    
    def test_valid_campus_data(self):
        """Test serializer with valid campus data."""
        data = {
            'campus_name': CampusName.IR,
            'campus_location': 'Launceston'
        }
        
        serializer = CampusSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class SupervisorSerializerTestCase(TestCase):
    """Test cases for SupervisorSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='supervisor@example.com',
            password='testpass123',
            first_name='Super',
            last_name='Visor'
        )
        self.campus = Campus.objects.create(
            campus_name=CampusName.SB,
            campus_location='Hobart'
        )
        self.supervisor = Supervisor.objects.create(
            user=self.user,
            campus=self.campus
        )
    
    def test_serializer_fields(self):
        """Test that serializer includes correct fields."""
        serializer = SupervisorSerializer(self.supervisor)
        expected_fields = {
            'id', 'user', 'campus', 'user_email', 'user_name',
            'campus_name', 'created_at', 'updated_at'
        }
        self.assertEqual(set(serializer.data.keys()), expected_fields)
    
    def test_user_email_field(self):
        """Test user_email read-only field."""
        serializer = SupervisorSerializer(self.supervisor)
        self.assertEqual(serializer.data['user_email'], 'supervisor@example.com')
    
    def test_user_name_field(self):
        """Test user_name read-only field."""
        serializer = SupervisorSerializer(self.supervisor)
        self.assertEqual(serializer.data['user_name'], 'Super Visor')
    
    def test_campus_name_field(self):
        """Test campus_name read-only field."""
        serializer = SupervisorSerializer(self.supervisor)
        self.assertEqual(serializer.data['campus_name'], CampusName.SB)


class RolePermissionSerializerTestCase(TestCase):
    """Test cases for RolePermissionSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.role = Role.objects.create(role_name='TestRole')
        self.permission1 = Permission.objects.create(permission_key='test.permission1')
        self.permission2 = Permission.objects.create(permission_key='test.permission2')
    
    def test_valid_data(self):
        """Test serializer with valid data."""
        data = {
            'role_id': self.role.id,
            'permission_ids': [self.permission1.id, self.permission2.id]
        }
        
        serializer = RolePermissionSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_invalid_role_id(self):
        """Test validation with invalid role ID."""
        data = {
            'role_id': 999,  # Non-existent role
            'permission_ids': [self.permission1.id]
        }
        
        serializer = RolePermissionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('role_id', serializer.errors)
    
    def test_invalid_permission_id(self):
        """Test validation with invalid permission ID."""
        data = {
            'role_id': self.role.id,
            'permission_ids': [999]  # Non-existent permission
        }
        
        serializer = RolePermissionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('permission_ids', serializer.errors)
    
    def test_empty_permission_ids(self):
        """Test that empty permission_ids list is allowed."""
        data = {
            'role_id': self.role.id,
            'permission_ids': []
        }
        
        serializer = RolePermissionSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class UserBulkRoleAssignmentSerializerTestCase(TestCase):
    """Test cases for UserBulkRoleAssignmentSerializer."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(email='test@example.com')
        self.role = Role.objects.create(role_name='TestRole')
    
    def test_valid_data(self):
        """Test serializer with valid data."""
        data = {
            'user_id': self.user.id,
            'role_id': self.role.id
        }
        
        serializer = UserBulkRoleAssignmentSerializer(data=data)
        self.assertTrue(serializer.is_valid())
    
    def test_invalid_user_id(self):
        """Test validation with invalid user ID."""
        data = {
            'user_id': 999,  # Non-existent user
            'role_id': self.role.id
        }
        
        serializer = UserBulkRoleAssignmentSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('user_id', serializer.errors)
    
    def test_invalid_role_id(self):
        """Test validation with invalid role ID."""
        data = {
            'user_id': self.user.id,
            'role_id': 999  # Non-existent role
        }
        
        serializer = UserBulkRoleAssignmentSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('role_id', serializer.errors)

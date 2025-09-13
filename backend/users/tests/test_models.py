"""
Test models for the users app.
"""
from django.test import TestCase
from django.db import IntegrityError
from unittest.mock import patch, MagicMock
from users.models import (
    User, Role, Permission, RolePermission, 
    UserRoles, Campus, CampusName, Supervisor
)
from users.factory import (
    UserFactory, RoleFactory, PermissionFactory, CampusFactory,
    SupervisorFactory, UserRolesFactory, AdminUserFactory,
    MemberUserFactory, TutorUserFactory, SupervisorUserFactory,
    CompleteUserScenarioFactory, create_test_permissions
)


class UserManagerTestCase(TestCase):
    """Test cases for UserManager."""
    
    def setUp(self):
        """Set up test data."""
        self.role = RoleFactory(
            role_name='TestRole',
            description='Test role for testing'
        )
        self.campus = CampusFactory(
            campus_name=CampusName.SB,
            campus_location='Hobart'
        )
    
    def test_create_user_with_email_and_password(self):
        """Test creating a user with email and password."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'User')
        self.assertTrue(user.check_password('testpass123'))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
    
    def test_create_user_without_email_raises_error(self):
        """Test that creating user without email raises ValueError."""
        with self.assertRaises(ValueError) as cm:
            User.objects.create_user(email='', password='testpass123')
        self.assertEqual(str(cm.exception), 'The Email field must be set')
    
    def test_create_user_normalizes_email(self):
        """Test that email is normalized."""
        user = User.objects.create_user(
            email='Test@EXAMPLE.COM',
            password='testpass123'
        )
        self.assertEqual(user.email, 'Test@example.com')
    
    def test_create_user_assigns_default_member_role(self):
        """Test that default Member role is assigned when no role specified."""
        # Create Member role
        Role.objects.create(role_name='Member', description='Default member role')
        
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        # Check that user has Member role
        self.assertTrue(user.has_role('Member'))
        self.assertEqual(user.get_active_role_name(), 'Member')
    
    def test_create_user_with_specific_role(self):
        """Test creating user with specific role."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            role_name='TestRole'
        )
        
        self.assertTrue(user.has_role('TestRole'))
        self.assertEqual(user.get_active_role_name(), 'TestRole')
    
    def test_create_superuser(self):
        """Test creating superuser."""
        # Create Admin role
        Role.objects.create(role_name='Admin', description='Admin role')
        
        user = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_active)
        self.assertTrue(user.has_role('Admin'))
    
    def test_create_superuser_without_is_staff_raises_error(self):
        """Test that creating superuser with is_staff=False raises ValueError."""
        with self.assertRaises(ValueError) as cm:
            User.objects.create_superuser(
                email='admin@example.com',
                password='adminpass123',
                is_staff=False
            )
        self.assertEqual(str(cm.exception), 'Superuser must have is_staff=True.')
    
    def test_update_user(self):
        """Test updating user details."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        updated_user = User.objects.update_user(
            user.id,
            first_name='Updated',
            last_name='Name'
        )
        
        self.assertEqual(updated_user.first_name, 'Updated')
        self.assertEqual(updated_user.last_name, 'Name')
    
    def test_update_nonexistent_user(self):
        """Test updating non-existent user returns None."""
        result = User.objects.update_user(999, first_name='Test')
        self.assertIsNone(result)
    
    def test_delete_user(self):
        """Test deleting user."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        user_id = user.id
        
        result = User.objects.delete_user(user_id)
        self.assertTrue(result)
        self.assertFalse(User.objects.filter(id=user_id).exists())
    
    def test_delete_nonexistent_user(self):
        """Test deleting non-existent user returns False."""
        result = User.objects.delete_user(999)
        self.assertFalse(result)
    
    def test_create_user_with_oauth(self):
        """Test creating user with OAuth."""
        # Create Member role for OAuth users
        Role.objects.create(role_name='Member', description='Default member role')
        
        user = User.objects.create_user_with_oauth(
            email='oauth@example.com',
            first_name='OAuth',
            last_name='User'
        )
        
        self.assertEqual(user.email, 'oauth@example.com')
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.has_role('Member'))
    
    def test_login_user_success(self):
        """Test successful user login."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        result = User.objects.login_user('test@example.com', 'testpass123')
        
        self.assertTrue(result['success'])
        self.assertEqual(result['user'], user)
        self.assertIn('tokens', result)
        self.assertIn('access', result['tokens'])
        self.assertIn('refresh', result['tokens'])
    
    def test_login_user_invalid_credentials(self):
        """Test login with invalid credentials."""
        User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        result = User.objects.login_user('test@example.com', 'wrongpass')
        
        self.assertFalse(result['success'])
        self.assertEqual(result['message'], 'Invalid credentials')
    
    def test_login_inactive_user(self):
        """Test login with inactive user."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        user.is_active = False
        user.save()
        
        result = User.objects.login_user('test@example.com', 'testpass123')
        
        self.assertFalse(result['success'])
        self.assertEqual(result['message'], 'Invalid credentials')
    
    def test_register_user_success(self):
        """Test successful user registration."""
        # Create Member role
        Role.objects.create(role_name='Member', description='Default member role')
        
        result = User.objects.register_user(
            email='newuser@example.com',
            password='newpass123',
            first_name='New',
            last_name='User'
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['user'].email, 'newuser@example.com')
        self.assertIn('tokens', result)
    
    def test_register_existing_user(self):
        """Test registering existing user."""
        User.objects.create_user(
            email='existing@example.com',
            password='testpass123'
        )
        
        result = User.objects.register_user(
            email='existing@example.com',
            password='newpass123'
        )
        
        self.assertFalse(result['success'])
        self.assertEqual(result['message'], 'User already exists')
    
    def test_oauth_login_or_create_new_user(self):
        """Test OAuth login for new user."""
        # Create Member role
        Role.objects.create(role_name='Member', description='Default member role')
        
        result = User.objects.oauth_login_or_create(
            email='oauth@example.com',
            first_name='OAuth',
            last_name='User'
        )
        
        self.assertTrue(result['success'])
        self.assertTrue(result['created'])
        self.assertEqual(result['user'].email, 'oauth@example.com')
        self.assertTrue(result['user'].has_role('Member'))
    
    def test_oauth_login_or_create_existing_user(self):
        """Test OAuth login for existing user."""
        user = User.objects.create_user(
            email='existing@example.com',
            password='testpass123'
        )
        
        result = User.objects.oauth_login_or_create(
            email='existing@example.com'
        )
        
        self.assertTrue(result['success'])
        self.assertFalse(result['created'])
        self.assertEqual(result['user'], user)
    
    @patch('users.models.RefreshToken.for_user')
    def test_get_tokens_for_user(self, mock_refresh_token):
        """Test generating JWT tokens for user."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        mock_refresh = MagicMock()
        mock_refresh.access_token = 'mock_access_token'
        mock_refresh.__str__ = MagicMock(return_value='mock_refresh_token')
        mock_refresh_token.return_value = mock_refresh
        
        tokens = User.objects.get_tokens_for_user(user)
        
        self.assertEqual(tokens['access'], 'mock_access_token')
        self.assertEqual(tokens['refresh'], 'mock_refresh_token')
    
    def test_assign_role_to_user_replaces_existing_role(self):
        """Test that assigning new role disables previous active role."""
        # Create roles
        role1 = Role.objects.create(role_name='Role1', description='First role')
        role2 = Role.objects.create(role_name='Role2', description='Second role')
        
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            role_name='Role1'
        )
        
        # Verify initial role
        self.assertTrue(user.has_role('Role1'))
        
        # Assign new role
        User.objects._assign_role_to_user(user, 'Role2')
        
        # Verify role change
        self.assertFalse(user.has_role('Role1'))
        self.assertTrue(user.has_role('Role2'))
        
        # Verify Role1 assignment is disabled
        role1_assignment = UserRoles.objects.get(user=user, role=role1)
        self.assertFalse(role1_assignment.is_active)
        self.assertIsNotNone(role1_assignment.disabled_at)
    
    def test_assign_nonexistent_role_raises_error(self):
        """Test that assigning non-existent role raises ValueError."""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        with self.assertRaises(ValueError) as cm:
            User.objects._assign_role_to_user(user, 'NonExistentRole')
        
        self.assertIn("Role 'NonExistentRole' does not exist", str(cm.exception))


class UserModelTestCase(TestCase):
    """Test cases for User model."""
    
    def setUp(self):
        """Set up test data."""
        self.role = Role.objects.create(
            role_name='TestRole',
            description='Test role'
        )
        self.permission = Permission.objects.create(
            permission_key='test.permission',
            description='Test permission'
        )
        RolePermission.objects.create(role=self.role, permission=self.permission)
        
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            role_name='TestRole'
        )
    
    def test_str_method(self):
        """Test string representation of user."""
        self.assertEqual(str(self.user), 'test@example.com')
    
    def test_get_full_name(self):
        """Test get_full_name method."""
        self.assertEqual(self.user.get_full_name(), 'Test User')
        
        # Test with empty names
        user = User.objects.create_user(email='empty@example.com')
        self.assertEqual(user.get_full_name(), '')
    
    def test_get_short_name(self):
        """Test get_short_name method."""
        self.assertEqual(self.user.get_short_name(), 'Test')
    
    def test_has_perm_staff_user(self):
        """Test has_perm for staff user."""
        self.user.is_staff = True
        self.user.save()
        
        self.assertTrue(self.user.has_perm('any.permission'))
    
    def test_has_perm_non_staff_user(self):
        """Test has_perm for non-staff user."""
        self.assertFalse(self.user.has_perm('any.permission'))
    
    def test_has_module_perms_staff_user(self):
        """Test has_module_perms for staff user."""
        self.user.is_staff = True
        self.user.save()
        
        self.assertTrue(self.user.has_module_perms('any_app'))
    
    def test_has_module_perms_non_staff_user(self):
        """Test has_module_perms for non-staff user."""
        self.assertFalse(self.user.has_module_perms('any_app'))
    
    def test_has_custom_permission(self):
        """Test has_custom_permission method."""
        self.assertTrue(self.user.has_custom_permission('test.permission'))
        self.assertFalse(self.user.has_custom_permission('nonexistent.permission'))
    
    def test_get_user_roles(self):
        """Test get_user_roles method."""
        roles = self.user.get_user_roles()
        self.assertEqual(roles.count(), 1)
        self.assertEqual(roles.first(), self.role)
    
    def test_get_active_role(self):
        """Test get_active_role method."""
        active_role = self.user.get_active_role()
        self.assertEqual(active_role, self.role)
    
    def test_get_active_role_name(self):
        """Test get_active_role_name method."""
        role_name = self.user.get_active_role_name()
        self.assertEqual(role_name, 'TestRole')
    
    def test_get_user_permissions(self):
        """Test get_user_permissions method."""
        permissions = self.user.get_user_permissions()
        self.assertEqual(permissions.count(), 1)
        self.assertEqual(permissions.first(), self.permission)
    
    def test_assign_role(self):
        """Test assign_role method."""
        new_role = Role.objects.create(role_name='NewRole', description='New role')
        self.user.assign_role('NewRole')
        
        self.assertTrue(self.user.has_role('NewRole'))
        self.assertFalse(self.user.has_role('TestRole'))
    
    def test_remove_role(self):
        """Test remove_role method."""
        result = self.user.remove_role('TestRole')
        self.assertTrue(result)
        self.assertFalse(self.user.has_role('TestRole'))
    
    def test_remove_nonexistent_role(self):
        """Test removing non-existent role."""
        result = self.user.remove_role('NonExistentRole')
        self.assertFalse(result)
    
    def test_has_role(self):
        """Test has_role method."""
        self.assertTrue(self.user.has_role('TestRole'))
        self.assertFalse(self.user.has_role('NonExistentRole'))
    
    def test_get_primary_role(self):
        """Test get_primary_role method."""
        primary_role = self.user.get_primary_role()
        self.assertEqual(primary_role, self.role)


class RoleModelTestCase(TestCase):
    """Test cases for Role model."""
    
    def test_role_creation(self):
        """Test role creation."""
        role = Role.objects.create(
            role_name='TestRole',
            description='Test role description'
        )
        
        self.assertEqual(role.role_name, 'TestRole')
        self.assertEqual(role.description, 'Test role description')
        self.assertIsNotNone(role.created_at)
        self.assertIsNotNone(role.updated_at)
    
    def test_str_method(self):
        """Test string representation of role."""
        role = Role.objects.create(role_name='TestRole')
        self.assertEqual(str(role), 'TestRole')
    
    def test_role_name_unique(self):
        """Test that role name must be unique."""
        Role.objects.create(role_name='UniqueRole')
        
        with self.assertRaises(IntegrityError):
            Role.objects.create(role_name='UniqueRole')


class PermissionModelTestCase(TestCase):
    """Test cases for Permission model."""
    
    def test_permission_creation(self):
        """Test permission creation."""
        permission = Permission.objects.create(
            permission_key='test.permission',
            description='Test permission description'
        )
        
        self.assertEqual(permission.permission_key, 'test.permission')
        self.assertEqual(permission.description, 'Test permission description')
        self.assertIsNotNone(permission.created_at)
        self.assertIsNotNone(permission.updated_at)
    
    def test_str_method(self):
        """Test string representation of permission."""
        permission = Permission.objects.create(permission_key='test.permission')
        self.assertEqual(str(permission), 'test.permission')
    
    def test_permission_key_unique(self):
        """Test that permission key must be unique."""
        Permission.objects.create(permission_key='unique.permission')
        
        with self.assertRaises(IntegrityError):
            Permission.objects.create(permission_key='unique.permission')


class RolePermissionModelTestCase(TestCase):
    """Test cases for RolePermission model."""
    
    def setUp(self):
        """Set up test data."""
        self.role = Role.objects.create(role_name='TestRole')
        self.permission = Permission.objects.create(permission_key='test.permission')
    
    def test_role_permission_creation(self):
        """Test role permission relationship creation."""
        role_permission = RolePermission.objects.create(
            role=self.role,
            permission=self.permission
        )
        
        self.assertEqual(role_permission.role, self.role)
        self.assertEqual(role_permission.permission, self.permission)
    
    def test_str_method(self):
        """Test string representation of role permission."""
        role_permission = RolePermission.objects.create(
            role=self.role,
            permission=self.permission
        )
        
        expected = f"{self.role.role_name} - {self.permission.permission_key}"
        self.assertEqual(str(role_permission), expected)
    
    def test_unique_together_constraint(self):
        """Test that role-permission combination must be unique."""
        RolePermission.objects.create(role=self.role, permission=self.permission)
        
        with self.assertRaises(IntegrityError):
            RolePermission.objects.create(role=self.role, permission=self.permission)


class UserRolesModelTestCase(TestCase):
    """Test cases for UserRoles model."""
    
    def setUp(self):
        """Set up test data."""
        self.role = Role.objects.create(role_name='TestRole')
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_user_roles_creation(self):
        """Test user roles relationship creation."""
        user_role = UserRoles.objects.create(user=self.user, role=self.role)
        
        self.assertEqual(user_role.user, self.user)
        self.assertEqual(user_role.role, self.role)
        self.assertTrue(user_role.is_active)
        self.assertIsNotNone(user_role.assigned_at)
        self.assertIsNone(user_role.disabled_at)
    
    def test_str_method(self):
        """Test string representation of user roles."""
        user_role = UserRoles.objects.create(user=self.user, role=self.role)
        
        expected = f"{self.user.email} - {self.role.role_name} (Active)"
        self.assertEqual(str(user_role), expected)
    
    def test_disable_method(self):
        """Test disable method."""
        user_role = UserRoles.objects.create(user=self.user, role=self.role)
        
        user_role.disable()
        
        self.assertFalse(user_role.is_active)
        self.assertIsNotNone(user_role.disabled_at)
        
        # Test string representation after disable
        expected = f"{self.user.email} - {self.role.role_name} (Disabled)"
        self.assertEqual(str(user_role), expected)


class CampusModelTestCase(TestCase):
    """Test cases for Campus model."""
    
    def test_campus_creation(self):
        """Test campus creation."""
        campus = Campus.objects.create(
            campus_name=CampusName.SB,
            campus_location='Hobart'
        )
        
        self.assertEqual(campus.campus_name, CampusName.SB)
        self.assertEqual(campus.campus_location, 'Hobart')
        self.assertIsNotNone(campus.created_at)
        self.assertIsNotNone(campus.updated_at)
    
    def test_str_method(self):
        """Test string representation of campus."""
        campus = Campus.objects.create(
            campus_name=CampusName.SB,
            campus_location='Hobart'
        )
        
        expected = f"{CampusName.SB} - Hobart"
        self.assertEqual(str(campus), expected)
    
    def test_campus_name_choices(self):
        """Test campus name choices."""
        self.assertEqual(CampusName.SB, 'SB')
        self.assertEqual(CampusName.IR, 'IR')
        self.assertEqual(CampusName.ONLINE, 'ONLINE')
    
    def test_campus_name_unique(self):
        """Test that campus name must be unique."""
        Campus.objects.create(
            campus_name=CampusName.SB,
            campus_location='Hobart'
        )
        
        with self.assertRaises(IntegrityError):
            Campus.objects.create(
                campus_name=CampusName.SB,
                campus_location='Different Location'
            )


class SupervisorModelTestCase(TestCase):
    """Test cases for Supervisor model."""
    
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
    
    def test_supervisor_creation(self):
        """Test supervisor creation."""
        supervisor = Supervisor.objects.create(
            user=self.user,
            campus=self.campus
        )
        
        self.assertEqual(supervisor.user, self.user)
        self.assertEqual(supervisor.campus, self.campus)
        self.assertIsNotNone(supervisor.created_at)
        self.assertIsNotNone(supervisor.updated_at)
    
    def test_str_method(self):
        """Test string representation of supervisor."""
        supervisor = Supervisor.objects.create(
            user=self.user,
            campus=self.campus
        )
        
        expected = f"Supervisor: {self.user.get_full_name()}"
        self.assertEqual(str(supervisor), expected)
    
    def test_str_method_without_full_name(self):
        """Test string representation when user has no full name."""
        user = User.objects.create_user(email='noname@example.com')
        supervisor = Supervisor.objects.create(user=user, campus=self.campus)
        
        expected = f"Supervisor: {user.email}"
        self.assertEqual(str(supervisor), expected)
    
    def test_one_to_one_user_relationship(self):
        """Test that user can only have one supervisor instance."""
        Supervisor.objects.create(user=self.user, campus=self.campus)
        
        with self.assertRaises(IntegrityError):
            Supervisor.objects.create(user=self.user, campus=self.campus)
    
    def test_supervisor_without_campus(self):
        """Test supervisor creation without campus."""
        supervisor = Supervisor.objects.create(user=self.user)
        
        self.assertEqual(supervisor.user, self.user)
        self.assertIsNone(supervisor.campus)

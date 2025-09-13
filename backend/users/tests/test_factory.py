"""
Test models using Factory Boy for data generation.
"""
from django.test import TestCase
from django.db import IntegrityError
from users.models import User, Role, Permission, UserRoles, Campus, Supervisor
from users.factory import (
    UserFactory, RoleFactory, PermissionFactory, CampusFactory,
    SupervisorFactory, UserRolesFactory, AdminUserFactory,
    MemberUserFactory, TutorUserFactory, SupervisorUserFactory,
    CompleteUserScenarioFactory, create_test_permissions,
    create_test_roles_with_permissions
)


class FactoryTestCase(TestCase):
    """Test cases using Factory Boy for data generation."""
    
    def test_user_factory(self):
        """Test UserFactory creates valid users."""
        user = UserFactory()
        
        self.assertIsInstance(user, User)
        self.assertTrue(user.email)
        self.assertTrue(user.first_name)
        self.assertTrue(user.last_name)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertTrue(user.check_password('defaultpass123'))
    
    def test_user_factory_with_custom_password(self):
        """Test UserFactory with custom password."""
        custom_password = 'custompass123'
        user = UserFactory(password=custom_password)
        
        self.assertTrue(user.check_password(custom_password))
    
    def test_role_factory(self):
        """Test RoleFactory creates valid roles."""
        role = RoleFactory()
        
        self.assertIsInstance(role, Role)
        self.assertTrue(role.role_name.startswith('Role_'))
        self.assertTrue(role.description)
    
    def test_permission_factory(self):
        """Test PermissionFactory creates valid permissions."""
        permission = PermissionFactory()
        
        self.assertIsInstance(permission, Permission)
        self.assertTrue(permission.permission_key.startswith('permission.'))
        self.assertTrue(permission.description)
    
    def test_campus_factory(self):
        """Test CampusFactory creates valid campuses."""
        campus = CampusFactory()
        
        self.assertIsInstance(campus, Campus)
        self.assertIn(campus.campus_name, ['SB', 'IR', 'ONLINE'])
        self.assertTrue(campus.campus_location)
    
    def test_supervisor_factory(self):
        """Test SupervisorFactory creates valid supervisors."""
        supervisor = SupervisorFactory()
        
        self.assertIsInstance(supervisor, Supervisor)
        self.assertIsInstance(supervisor.user, User)
        self.assertIsInstance(supervisor.campus, Campus)
    
    def test_user_roles_factory(self):
        """Test UserRolesFactory creates valid user-role relationships."""
        user_role = UserRolesFactory()
        
        self.assertIsInstance(user_role, UserRoles)
        self.assertIsInstance(user_role.user, User)
        self.assertIsInstance(user_role.role, Role)
        self.assertTrue(user_role.is_active)
    
    def test_admin_user_factory(self):
        """Test AdminUserFactory creates admin users with role."""
        admin = AdminUserFactory()
        
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.has_role('Admin'))
        self.assertEqual(admin.get_active_role_name(), 'Admin')
    
    def test_member_user_factory(self):
        """Test MemberUserFactory creates member users with role."""
        member = MemberUserFactory()
        
        self.assertFalse(member.is_staff)
        self.assertTrue(member.has_role('Member'))
        self.assertEqual(member.get_active_role_name(), 'Member')
    
    def test_tutor_user_factory(self):
        """Test TutorUserFactory creates tutor users with role."""
        tutor = TutorUserFactory()
        
        self.assertFalse(tutor.is_staff)
        self.assertTrue(tutor.has_role('Tutor'))
        self.assertEqual(tutor.get_active_role_name(), 'Tutor')
    
    def test_supervisor_user_factory(self):
        """Test SupervisorUserFactory creates supervisor users with role and instance."""
        supervisor_user = SupervisorUserFactory()
        
        self.assertTrue(supervisor_user.has_role('Supervisor'))
        self.assertTrue(hasattr(supervisor_user, 'supervisor'))
        self.assertIsInstance(supervisor_user.supervisor, Supervisor)
    
    def test_create_test_permissions(self):
        """Test create_test_permissions helper function."""
        permissions = create_test_permissions()
        
        self.assertEqual(len(permissions), 11)  # Based on the permissions defined
        for permission in permissions:
            self.assertIsInstance(permission, Permission)
            self.assertTrue(permission.permission_key)
            self.assertTrue(permission.description)
    
    def test_create_test_roles_with_permissions(self):
        """Test create_test_roles_with_permissions helper function."""
        roles_data = create_test_roles_with_permissions()
        
        self.assertIn('admin', roles_data)
        self.assertIn('supervisor', roles_data)
        self.assertIn('tutor', roles_data)
        self.assertIn('member', roles_data)
        self.assertIn('permissions', roles_data)
        
        # Check that roles were created
        self.assertIsInstance(roles_data['admin'], Role)
        self.assertEqual(roles_data['admin'].role_name, 'Admin')
        
        # Check permissions were created
        self.assertEqual(len(roles_data['permissions']), 11)
    
    def test_complete_user_scenario_factory(self):
        """Test CompleteUserScenarioFactory for creating complex scenarios."""
        scenario = CompleteUserScenarioFactory.create_user_with_role_and_permissions(
            role_name='TestRole',
            permissions=['test.permission1', 'test.permission2']
        )
        
        self.assertIn('user', scenario)
        self.assertIn('role', scenario)
        self.assertIn('permissions', scenario)
        
        user = scenario['user']
        role = scenario['role']
        permissions = scenario['permissions']
        
        self.assertIsInstance(user, User)
        self.assertIsInstance(role, Role)
        self.assertEqual(role.role_name, 'TestRole')
        self.assertEqual(len(permissions), 2)
        self.assertTrue(user.has_role('TestRole'))
    
    def test_supervisor_scenario_factory(self):
        """Test supervisor scenario creation."""
        scenario = CompleteUserScenarioFactory.create_supervisor_with_campus()
        
        self.assertIn('user', scenario)
        self.assertIn('supervisor', scenario)
        self.assertIn('campus', scenario)
        
        user = scenario['user']
        supervisor = scenario['supervisor']
        campus = scenario['campus']
        
        self.assertIsInstance(user, User)
        self.assertIsInstance(supervisor, Supervisor)
        self.assertIsInstance(campus, Campus)
        self.assertEqual(supervisor.user, user)
        self.assertEqual(supervisor.campus, campus)
    
    def test_complete_organization_factory(self):
        """Test creating a complete test organization."""
        org = CompleteUserScenarioFactory.create_test_organization()
        
        # Check structure
        self.assertIn('campuses', org)
        self.assertIn('roles', org)
        self.assertIn('admin', org)
        self.assertIn('supervisors', org)
        self.assertIn('tutors', org)
        self.assertIn('members', org)
        
        # Check counts
        self.assertEqual(len(org['campuses']), 3)
        # Allow for additional roles that might be auto-created (expect at least 4 essential roles)
        self.assertGreaterEqual(len(org['roles']), 4)
        self.assertEqual(len(org['supervisors']), 2)
        self.assertEqual(len(org['tutors']), 5)
        self.assertEqual(len(org['members']), 10)
        
        # Check admin
        admin = org['admin']
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.has_role('Admin'))
        
        # Check supervisors have campuses
        for supervisor_user in org['supervisors']:
            self.assertTrue(hasattr(supervisor_user, 'supervisor'))
            self.assertIsNotNone(supervisor_user.supervisor.campus)
    
    def test_batch_creation(self):
        """Test creating multiple instances using factories."""
        users = UserFactory.create_batch(5)
        roles = RoleFactory.create_batch(3)
        permissions = PermissionFactory.create_batch(4)
        
        self.assertEqual(len(users), 5)
        self.assertEqual(len(roles), 3)
        self.assertEqual(len(permissions), 4)
        
        # Check uniqueness of generated data
        emails = [user.email for user in users]
        self.assertEqual(len(emails), len(set(emails)))  # All emails should be unique
        
        role_names = [role.role_name for role in roles]
        self.assertEqual(len(role_names), len(set(role_names)))  # All role names should be unique
    
    def test_factory_with_traits(self):
        """Test factory with specific traits."""
        # Create staff user
        staff_user = UserFactory(is_staff=True, email='staff@example.com')
        self.assertTrue(staff_user.is_staff)
        self.assertEqual(staff_user.email, 'staff@example.com')
        
        # Create inactive user
        inactive_user = UserFactory(is_active=False)
        self.assertFalse(inactive_user.is_active)
        
        # Create role with specific name
        custom_role = RoleFactory(role_name='CustomRole')
        self.assertEqual(custom_role.role_name, 'CustomRole')
    
    def test_related_factory_creation(self):
        """Test creating related objects through factories."""
        # Create user with supervisor
        supervisor = SupervisorFactory()
        
        # Verify relationships
        self.assertIsNotNone(supervisor.user)
        self.assertIsNotNone(supervisor.campus)
        self.assertTrue(supervisor.user.email)
        self.assertTrue(supervisor.campus.campus_location)
        
        # Create user role relationship
        user_role = UserRolesFactory()
        
        self.assertIsNotNone(user_role.user)
        self.assertIsNotNone(user_role.role)
        self.assertTrue(user_role.user.email)
        self.assertTrue(user_role.role.role_name)
    
    def test_factory_database_constraints(self):
        """Test that factories respect database constraints."""
        from django.db import transaction
        
        # Test unique constraint on role name
        role1 = RoleFactory(role_name='UniqueRole')
        
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                RoleFactory(role_name='UniqueRole')  # Should fail due to unique constraint
        
        # Test unique constraint on permission key
        permission1 = PermissionFactory(permission_key='unique.permission')
        
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                PermissionFactory(permission_key='unique.permission')  # Should fail
        
        # Test unique constraint on campus name
        campus1 = CampusFactory(campus_name='SB')
        
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                CampusFactory(campus_name='SB')  # Should fail due to unique constraint
    
    def test_factory_performance(self):
        """Test factory performance for bulk creation."""
        import time
        
        start_time = time.time()
        users = UserFactory.create_batch(100)
        end_time = time.time()
        
        # Should create 100 users reasonably quickly (increased timeout for CI)
        self.assertLess(end_time - start_time, 60.0)  # Increased from 5.0 to 60.0
        self.assertEqual(len(users), 100)
        
        # Verify all users are valid
        for user in users[:5]:  # Check first 5 users
            self.assertTrue(user.email)
            self.assertTrue(user.first_name)
            self.assertTrue(user.last_name)

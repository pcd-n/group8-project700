#backend/users/urls.py
from django.urls import path
from . import views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

app_name = 'accounts'

urlpatterns = [
    # =====================================================
    # AUTHENTICATION ENDPOINTS (Essential)
    # =====================================================
    path('login/', views.LoginView.as_view(), name='login'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('logout/', views.logout_view, name='accounts_logout'),
    
    # JWT token endpoints (alternative to custom login)
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # =====================================================
    # USER PROFILE ENDPOINTS (Essential)
    # =====================================================
    path('profile/', views.UserProfileView.as_view(), name='profile_self'),
    path('profile/<int:user_id>/', views.UserProfileView.as_view(), name='profile_view'),
    
    # =====================================================
    # USER MANAGEMENT
    # =====================================================
    path('users/update/', views.UserUpdateView.as_view(), name='user_update_self'),
    path('users/update/<int:user_id>/', views.UserUpdateView.as_view(), name='user_update_specific'),
    path('users/reset-password/', views.ResetPasswordView.as_view(), name='reset_password'),

    # =====================================================
    # RBAC - ROLE MANAGEMENT ENDPOINTS (Admin only)
    # =====================================================
    path('roles/', views.RoleListCreateView.as_view(), name='roles_list_create'),
    path('roles/<int:pk>/', views.RoleDetailView.as_view(), name='role_detail'),
    
    # =====================================================
    # RBAC - PERMISSION MANAGEMENT ENDPOINTS (Admin only)
    # =====================================================
    path('permissions/', views.PermissionListCreateView.as_view(), name='permissions_list_create'),
    path('permissions/<int:pk>/', views.PermissionDetailView.as_view(), name='permission_detail'),
    
    # =====================================================
    # RBAC - USER ROLE ASSIGNMENT ENDPOINTS (Admin only)
    # =====================================================
    path('user-roles/', views.UserRolesListView.as_view(), name='user_roles_list'),
    path('user-roles/<int:user_id>/', views.UserRolesView.as_view(), name='user_roles_manage'),
    path('search/', views.UserSearchView.as_view(), name='user_search'),
]

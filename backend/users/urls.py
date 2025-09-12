from django.urls import path
from . import views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

app_name = 'accounts'

urlpatterns = [
    # Authentication endpoints
    path('login/', views.LoginView.as_view(), name='login'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    path('profile/<int:user_id>/', views.UserProfileView.as_view(), name='user_profile'),
    
    # User management
    path('users/update/', views.UserUpdateView.as_view(), name='user_update_self'),
    path('users/update/<int:user_id>/', views.UserUpdateView.as_view(), name='user_update'),
    path('users/bulk-update/', views.UserUpdateView.as_view(), name='bulk_user_update'),
    
    # Role management
    path('roles/', views.RoleListCreateView.as_view(), name='roles_list_create'),
    path('roles/<int:pk>/', views.RoleDetailView.as_view(), name='role_detail'),
    
    # Permission management
    path('permissions/', views.PermissionListCreateView.as_view(), name='permissions_list_create'),
    path('permissions/<int:pk>/', views.PermissionDetailView.as_view(), name='permission_detail'),
    
    # User Role assignment
    path('user-roles/', views.UserRolesView.as_view(), name='user_roles_list'),
    path('user-roles/<int:user_id>/', views.UserRolesView.as_view(), name='user_roles_detail'),
    path('user-roles/<int:user_id>/assign/', views.UserRolesView.as_view(), name='user_roles_assign'),
    path('user-roles/<int:user_id>/update/', views.UserRolesView.as_view(), name='user_roles_update'),
    path('user-roles/<int:user_id>/role/<int:role_id>/disable/', views.UserRolesView.as_view(), name='user_role_disable'),
    
    # JWT token endpoints (alternative to custom login)
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

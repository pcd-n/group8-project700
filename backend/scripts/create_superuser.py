#!/usr/bin/env python
import os
import sys
import django
from dotenv import load_dotenv

# Add parent directory to Python path for Django imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from parent directory
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_tutors.settings')
django.setup()

from django.contrib.auth import get_user_model

def create_superuser():
    User = get_user_model()
    admin_username = os.getenv('DEV_ADMIN_USER', 'devadmin')
    password = os.getenv('DEV_ADMIN_USER_PASSWORD', 'admin123!')
    email = f"{admin_username}@example.com"
    first_name = os.getenv('DEV_ADMIN_FIRST_NAME', 'Admin')
    last_name = os.getenv('DEV_ADMIN_LAST_NAME', 'User')
    
    if User.objects.filter(email=email).exists():
        print(f"Superuser with email '{email}' already exists!")
        return
    
    user = User.objects.create_superuser(
        email=email, 
        password=password,
        first_name=first_name,
        last_name=last_name
    )
    print(f"Superuser created successfully!")
    print(f"Email: {email}")
    print(f"Name: {first_name} {last_name}")
    print(f"Password: {password}")

if __name__ == "__main__":
    create_superuser()

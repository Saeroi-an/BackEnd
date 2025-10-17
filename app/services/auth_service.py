# app/services/auth_service.py
from supabase import create_client
from app.core.config import settings

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def sign_in(email, password):
    user = supabase.auth.sign_in_with_password({"email": email, "password": password})
    return user

def sign_up(email, password):
    user = supabase.auth.sign_up({"email": email, "password": password})
    return user

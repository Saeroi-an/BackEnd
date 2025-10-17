# app/api/auth_router.py
from fastapi import APIRouter, Form
from app.services.auth_service import sign_in, sign_up

router = APIRouter()

@router.post("/signup")
def signup(email: str = Form(...), password: str = Form(...)):
    return sign_up(email, password)

@router.post("/signin")
def signin(email: str = Form(...), password: str = Form(...)):
    return sign_in(email, password)

from pydantic import BaseModel, EmailStr

# 사용자 생성 시 받을 데이터
class UserCreate(BaseModel):
    name: str
    email: str
    age: int

# 사용자 정보 응답 시 보낼 데이터
class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    age: int
    
    class Config:
        from_attributes = True  # ORM 모델을 Pydantic 모델로 변환 허용
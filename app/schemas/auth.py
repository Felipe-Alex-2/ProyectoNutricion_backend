from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from app.schemas.user import UserResponse


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters long")
    full_name: str = Field(..., min_length=2, max_length=100)
    client_platform: Optional[str] = Field("web", description="Origin platform: 'web' or 'mobile'")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # in seconds
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: str  # user id or email
    email: Optional[str] = None
    type: str = "access"  # "access", "refresh", or "password_reset"
    exp: int
    iat: int


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="10-minute reset token received by email")
    new_password: str = Field(..., min_length=8, description="New password with minimum 8 characters")


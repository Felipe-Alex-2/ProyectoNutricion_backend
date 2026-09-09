from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
from app.schemas.user import UserResponse


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="Correo electrónico válido para registro")
    password: str = Field(..., min_length=8, max_length=128, description="Contraseña de acceso (mínimo 8 caracteres)")
    full_name: str = Field(..., min_length=2, max_length=100, description="Nombre completo")
    client_platform: Optional[str] = Field("web", description="Plataforma de origen: 'web' o 'mobile'")

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres")
        return v


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Correo electrónico registrado")
    password: str = Field(..., min_length=1, description="Contraseña de acceso")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # in seconds
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=10, description="Token JWT de refresco")


class TokenPayload(BaseModel):
    sub: str  # user id or email
    email: Optional[str] = None
    type: str = "access"  # "access", "refresh", or "password_reset"
    exp: int
    iat: int


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., description="Correo electrónico registrado")


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=10, description="Token de restablecimiento de contraseña")
    new_password: str = Field(..., min_length=8, max_length=128, description="Nueva contraseña con mínimo 8 caracteres")



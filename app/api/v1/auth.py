from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.services.activity_log_service import ActivityLogService
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.schemas.user import UserResponse
from app.schemas.common import MessageResponse
from app.services.auth_service import AuthService
from app.api.deps import get_current_user, security_bearer


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Creates a new user account with unique email address and secure password.",
)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    user = AuthService.register(db, request)
    return user


from fastapi import APIRouter, Depends, Request, status
from app.models.activity_log import ActivityLog

@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and get JWT tokens",
    description="Validates email and password, returning access and refresh JWT tokens.",
)
def login(request: LoginRequest, req: Request, db: Session = Depends(get_db)):
    user = AuthService.authenticate(db, request)
    tokens = AuthService.create_tokens_for_user(user)
    try:
        ip = req.client.host if req.client else None
        db.add(ActivityLog(
            user_id=user.id,
            user_email=user.email,
            user_name=user.full_name,
            action="LOGIN",
            description=f"Inicio de sesión exitoso en la plataforma web",
            category="AUTH",
            ip_address=ip
        ))
        db.commit()
    except Exception:
        pass
    return tokens


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Takes a valid refresh token and issues a new access token.",
)
def refresh(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    return AuthService.refresh_access_token(db, request)


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout user and revoke access token",
    description="Adds the provided Bearer token to the blacklist so it cannot be used again.",
)
def logout(
    clear_logs: bool = Query(False),
    client_platform: Optional[str] = Query(None),
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if clear_logs or (client_platform and client_platform.lower() == "mobile"):
        ActivityLogService.clear_user_logs(db, current_user)
    AuthService.blacklist_token(db, credentials.credentials)
    return MessageResponse(message="Successfully logged out")


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Request password reset token",
    description="Generates a 10-minute password reset token and sends it via email.",
)
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    AuthService.request_password_reset(db, request)
    return MessageResponse(
        message="Si tu correo electrónico está registrado, recibirás un mensaje con el enlace para restablecer tu contraseña (válido por 10 minutos)."
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset password with token",
    description="Validates the 10-minute token and sets a new password for the user.",
)
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    AuthService.reset_password(db, request)
    return MessageResponse(
        message="Tu contraseña ha sido restablecida exitosamente. Ya puedes iniciar sesión con tu nueva contraseña."
    )


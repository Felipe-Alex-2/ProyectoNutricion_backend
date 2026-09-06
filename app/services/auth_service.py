from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.token_blacklist import TokenBlacklist
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.schemas.user import UserResponse
from app.services.user_service import UserService
from app.services.email_service import EmailService
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    create_password_reset_token,
    decode_token,
)
from app.core.exceptions import (
    AuthException,
    ConflictException,
    BadRequestException,
    NotFoundException,
)
from app.config import settings



class AuthService:
    @staticmethod
    def register(db: Session, request: RegisterRequest) -> User:
        """Register a new user account."""
        existing = UserService.get_by_email(db, request.email)
        if existing:
            raise ConflictException(detail="Email is already registered")

        # Rol según plataforma de registro: Web -> ADMIN_SAAS, Móvil -> CLIENTE
        platform = getattr(request, "client_platform", "web")
        assigned_role = "CLIENTE" if (platform and platform.lower() == "mobile") else "ADMIN_SAAS"

        user = UserService.create(
            db,
            obj_in=request,  # matches email, password, full_name
            role_id=assigned_role,
        )
        return user

    @staticmethod
    def authenticate(db: Session, request: LoginRequest) -> User:
        """Verify user credentials."""
        user = UserService.get_by_email(db, request.email)
        if not user:
            raise AuthException(detail="Invalid email or password")

        if not verify_password(request.password, user.hashed_password):
            raise AuthException(detail="Invalid email or password")

        if not user.is_active:
            raise AuthException(detail="Inactive user account")

        return user

    @classmethod
    def create_tokens_for_user(cls, user: User) -> TokenResponse:
        """Generate access and refresh tokens for user."""
        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user),
        )

    @classmethod
    def refresh_access_token(cls, db: Session, request: RefreshTokenRequest) -> TokenResponse:
        """Generate a new access token using a valid refresh token."""
        # Check if token is blacklisted
        if cls.is_token_blacklisted(db, request.refresh_token):
            raise AuthException(detail="Refresh token has been revoked")

        payload = decode_token(request.refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise AuthException(detail="Invalid or expired refresh token")

        user_id = payload.get("sub")
        if not user_id:
            raise AuthException(detail="Invalid token payload")

        user = UserService.get_by_id(db, user_id)
        if not user or not user.is_active:
            raise AuthException(detail="User not found or inactive")

        # Create new tokens
        return cls.create_tokens_for_user(user)

    @staticmethod
    def blacklist_token(db: Session, token: str) -> None:
        """Add a token to the revocation blacklist."""
        payload = decode_token(token)
        expires_at = None
        if payload and "exp" in payload:
            expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

        # Check if already in blacklist
        existing = db.query(TokenBlacklist).filter(TokenBlacklist.token == token).first()
        if not existing:
            blacklisted = TokenBlacklist(token=token, expires_at=expires_at)
            db.add(blacklisted)
            db.commit()

    @staticmethod
    def is_token_blacklisted(db: Session, token: str) -> bool:
        """Check if a token exists in the blacklist."""
        return db.query(TokenBlacklist).filter(TokenBlacklist.token == token).first() is not None

    @classmethod
    def request_password_reset(cls, db: Session, request: ForgotPasswordRequest) -> str | None:
        """Process password reset request, create 10-minute token and dispatch email."""
        user = UserService.get_by_email(db, request.email)
        if not user or not user.is_active:
            # Avoid leaking user existence, but log it
            return None

        # Generate 10-minute password reset token
        reset_token = create_password_reset_token(
            email=user.email,
            expires_minutes=settings.RESET_TOKEN_EXPIRE_MINUTES,
        )

        # Send formatted email with token and link
        EmailService.send_password_reset_email(to_email=user.email, reset_token=reset_token)
        return reset_token

    @classmethod
    def reset_password(cls, db: Session, request: ResetPasswordRequest) -> None:
        """Validate 10-minute reset token, update user password and revoke token."""
        # 1. Check if token was already revoked
        if cls.is_token_blacklisted(db, request.token):
            raise BadRequestException(detail="Este enlace de recuperación ya ha sido utilizado o no es válido.")

        # 2. Decode and validate token signature & expiration (10 min)
        payload = decode_token(request.token)
        if not payload or payload.get("type") != "password_reset":
            raise BadRequestException(
                detail="El enlace de recuperación ha expirado o es inválido. Recuerda que solo es válido por 10 minutos."
            )

        email = payload.get("sub")
        if not email:
            raise BadRequestException(detail="Token de recuperación con formato incorrecto.")

        # 3. Find user
        user = UserService.get_by_email(db, email)
        if not user or not user.is_active:
            raise NotFoundException(detail="Usuario no encontrado o cuenta inactiva.")

        # 4. Hash and save new password
        user.hashed_password = get_password_hash(request.new_password)
        db.add(user)
        db.commit()

        # 5. Blacklist reset token to prevent reuse
        cls.blacklist_token(db, request.token)


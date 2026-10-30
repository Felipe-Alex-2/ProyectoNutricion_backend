from typing import Optional
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.services.user_service import UserService
from app.services.auth_service import AuthService
from app.core.security import decode_token
from app.core.exceptions import AuthException

security_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate before binding the request's validated workspace."""
    db.info.pop('workspace', None)
    token = credentials.credentials if credentials else None
    if not token:
        raise AuthException(detail="Authentication credentials were not provided")

    # Verify if token is blacklisted
    if AuthService.is_token_blacklisted(db, token):
        raise AuthException(detail="Token has been revoked")

    payload = decode_token(token)
    if not payload:
        raise AuthException(detail="Invalid or expired token")

    if payload.get("type") != "access":
        raise AuthException(detail="Invalid token type")

    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise AuthException(detail="Could not validate credentials")

    user = UserService.get_by_id(db, user_id)
    if not user:
        raise AuthException(detail="User not found")

    if payload.get("sv", 0) != (user.session_version or 0):
        raise AuthException(detail="Session has been revoked")
    if not user.is_active:
        raise AuthException(detail="User account is inactive")

    user._workspace_company_id = None
    user._workspace_branch_id = None
    db.info['audit_actor'] = user
    from app.core.workspace import selection
    administrative = ('/api/v1/tenants', '/api/v1/branches', '/api/v1/roles')
    context_path = request.url.path in {'/api/v1/users/me', '/api/v1/users/me/workspace', '/api/v1/users/me/workspace-options', '/api/v1/auth/logout'}
    try:
        if not context_path and not any(request.url.path.startswith(p) for p in administrative):
            explicit = 'x-workspace-company' in request.headers or 'x-workspace-branch' in request.headers
            company = request.headers.get('x-workspace-company')
            branch = request.headers.get('x-workspace-branch')
            scope = selection(db, user, None if company == 'all' else company, None if branch == 'all' else branch, explicit=explicit)
            db.info['workspace'] = scope
            user._workspace_company_id = scope.tenant_id
            user._workspace_branch_id = scope.branch_id
        yield user
    finally:
        db.info.pop('workspace', None)
        db.info.pop('audit_actor', None)


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Optional dependency to retrieve authenticated user if token is provided."""
    token = credentials.credentials if credentials else None
    if not token:
        return None

    if AuthService.is_token_blacklisted(db, token):
        return None

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None

    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        return None

    user = UserService.get_by_id(db, user_id)
    if not user or not user.is_active or payload.get("sv", 0) != (user.session_version or 0):
        return None

    return user

"""Stable operation IDs and serialization for offline retries (no new tables)."""
import uuid
from fastapi import HTTPException
from app.models.user import User


def operation_id(db, actor_id: str, kind: str, key: str | None) -> str | None:
    if not key:
        return None
    if len(key) > 128 or not key.strip():
        raise HTTPException(422, 'Identificador de operación inválido.')
    # Serialize concurrent retries for this actor until the transaction commits.
    db.query(User).filter(User.id == actor_id).with_for_update(of=User).first()
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'offline:{kind}:{actor_id}:{key}'))

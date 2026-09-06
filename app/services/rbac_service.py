from typing import List
from sqlalchemy.orm import Session
from app.models.rbac import Role, Permission, RolePermission
from app.schemas.rbac import RoleResponse, PermissionResponse


class RBACService:
    @staticmethod
    def get_all_roles(db: Session) -> List[RoleResponse]:
        roles = db.query(Role).all()
        result = []
        for role in roles:
            # Query mapped permissions
            perm_ids = [
                rp.permission_id
                for rp in db.query(RolePermission).filter(RolePermission.role_id == role.id).all()
            ]
            permissions = (
                db.query(Permission).filter(Permission.id.in_(perm_ids)).all() if perm_ids else []
            )
            result.append(
                RoleResponse(
                    id=role.id,
                    name=role.name,
                    description=role.description,
                    platform=role.platform,
                    permissions=[
                        PermissionResponse(
                            id=p.id,
                            name=p.name,
                            description=p.description,
                            module=p.module,
                        )
                        for p in permissions
                    ],
                )
            )
        return result

    @staticmethod
    def get_all_permissions(db: Session) -> List[PermissionResponse]:
        permissions = db.query(Permission).order_by(Permission.module, Permission.name).all()
        return [
            PermissionResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                module=p.module,
            )
            for p in permissions
        ]

    @staticmethod
    def update_role_permissions(db: Session, role_id: str, permission_ids: List[str]) -> RoleResponse:
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            from app.core.exceptions import NotFoundException
            raise NotFoundException("Rol no encontrado")

        # Delete existing permissions for this role
        db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()

        # Insert new permission associations
        for pid in permission_ids:
            perm = db.query(Permission).filter(Permission.id == pid).first()
            if perm:
                db.add(RolePermission(role_id=role_id, permission_id=pid))

        db.commit()

        # Return updated role
        mapped_perms = (
            db.query(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .filter(RolePermission.role_id == role_id)
            .all()
        )

        return RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            platform=role.platform,
            permissions=[
                PermissionResponse(
                    id=p.id,
                    name=p.name,
                    description=p.description,
                    module=p.module,
                )
                for p in mapped_perms
            ],
        )

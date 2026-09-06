from typing import List
from pydantic import BaseModel, ConfigDict


class PermissionResponse(BaseModel):
    id: str
    name: str
    description: str
    module: str

    model_config = ConfigDict(from_attributes=True)


class RoleResponse(BaseModel):
    id: str
    name: str
    description: str
    platform: str
    permissions: List[PermissionResponse] = []

    model_config = ConfigDict(from_attributes=True)


class UpdateRolePermissionsRequest(BaseModel):
    permission_ids: List[str]

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


UserRole = Literal["user", "admin"]
UserStatus = Literal["active", "disabled"]


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr | None = Field(default=None, max_length=100)


class UserCreate(UserBase):
    model_config = ConfigDict(extra="ignore")

    password: str = Field(..., min_length=6, max_length=128)


class UserAdminCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=128)
    role: UserRole = "user"
    status: UserStatus = "active"


class UserUpdate(BaseModel):
    role: UserRole | None = None
    status: UserStatus | None = None


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: UserRole
    status: UserStatus
    created_at: datetime
    updated_at: datetime


class UserResponse(UserOut):
    pass


class UserSimpleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: UserRole


class AdminUserRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: UserRole


class AdminUserOut(BaseModel):
    id: int
    username: str
    email: EmailStr | None = None
    role: UserRole
    status: UserStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime
    detection_count: int = Field(..., ge=0)


class AdminUserListData(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AdminUserOut]


class AdminUserItemApiResponse(BaseModel):
    code: int
    message: str
    data: AdminUserOut


class AdminUserListApiResponse(BaseModel):
    code: int
    message: str
    data: AdminUserListData

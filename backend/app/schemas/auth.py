from pydantic import BaseModel, Field

from app.schemas.user import UserOut, UserRole, UserSimpleResponse


class UserLogin(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)


class TokenData(BaseModel):
    user_id: int | None = None
    username: str | None = None
    role: UserRole | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserSimpleResponse


class RegisterApiResponse(BaseModel):
    code: int = 200
    message: str = "注册成功"
    data: UserSimpleResponse


class LoginApiResponse(BaseModel):
    code: int = 200
    message: str = "登录成功"
    data: TokenResponse


class CurrentUserApiResponse(BaseModel):
    code: int = 200
    message: str = "success"
    data: UserOut

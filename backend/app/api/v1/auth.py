from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    CurrentUserApiResponse,
    LoginApiResponse,
    RegisterApiResponse,
    TokenResponse,
    UserLogin,
)
from app.schemas.user import UserCreate, UserOut, UserSimpleResponse
from app.services.auth_service import (
    DisabledUserError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
    authenticate_user,
    register_user,
)
from app.utils.response import error_response, success_response


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterApiResponse)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> dict:
    try:
        user = register_user(db, payload)
    except UserAlreadyExistsError as exc:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response(str(exc), code=400),
        )

    data = UserSimpleResponse.model_validate(user).model_dump()
    return success_response(message="注册成功", data=data)


@router.post("/login", response_model=LoginApiResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> dict:
    try:
        user = authenticate_user(db, payload.username, payload.password)
    except InvalidCredentialsError as exc:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=error_response(str(exc), code=401),
        )
    except DisabledUserError as exc:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=error_response(str(exc), code=403),
        )

    access_token = create_access_token(
        subject=user.id,
        role=user.role,
        extra_data={"username": user.username},
    )
    data = TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserSimpleResponse.model_validate(user),
    ).model_dump()
    return success_response(message="登录成功", data=data)


@router.get("/me", response_model=CurrentUserApiResponse)
def read_current_user(current_user: User = Depends(get_current_user)) -> dict:
    data = UserOut.model_validate(current_user).model_dump(mode="json")
    return success_response(data=data)

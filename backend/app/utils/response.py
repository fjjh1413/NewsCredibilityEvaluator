from typing import Any


def success_response(
    data: Any = None,
    message: str = "success",
    code: int = 200,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "data": data,
    }


def error_response(
    message: str,
    code: int = 400,
    data: Any = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "data": data,
    }


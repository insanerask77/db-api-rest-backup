from fastapi import Request


def get_settings(request: Request) -> dict:
    return request.app.state.settings

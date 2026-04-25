from __future__ import annotations

from .db_routing import SAFE_METHODS, mark_write, reset_request_method, set_request_method


class DbRoleRoutingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = set_request_method(getattr(request, "method", ""))
        try:
            response = self.get_response(request)
        finally:
            reset_request_method(token)

        if request.method not in SAFE_METHODS and response.status_code < 500:
            mark_write()

        return response

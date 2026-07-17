# tenancy/authentication.py
from __future__ import annotations

from rest_framework import authentication, exceptions

from .models import ApiKey


class ApiKeyAuthentication(authentication.BaseAuthentication):
    """Authenticate ingestion requests via a scoped API key.

    Header:  Authorization: Api-Key apm_<env>_<secret>

    On success, attaches the resolved tenant context to the request:
        request.auth            -> the ApiKey instance
        request.tenant_project  -> Project
        request.tenant_env      -> Environment

    Returns AnonymousUser as the user (keys are machine credentials, not people).
    """

    keyword = "Api-Key"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode("latin-1")
        if not header:
            return None
        parts = header.split()
        if parts[0].lower() != self.keyword.lower():
            return None  # let other authenticators (JWT/session) try
        if len(parts) != 2:
            raise exceptions.AuthenticationFailed("Malformed Api-Key header.")

        api_key = ApiKey.verify(parts[1])
        if api_key is None:
            raise exceptions.AuthenticationFailed("Invalid, expired, or revoked API key.")

        api_key.touch()
        request.tenant_project = api_key.project
        request.tenant_env = api_key.environment
        from django.contrib.auth.models import AnonymousUser

        return (AnonymousUser(), api_key)

    def authenticate_header(self, request):
        return self.keyword

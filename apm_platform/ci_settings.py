from apm_platform.settings import *  # noqa: F403

SECURE_SSL_REDIRECT = False
SECURE_PROXY_SSL_HEADER = None
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

# Keep tests on the default DB only to avoid router/alias isolation errors.
DATABASE_ROUTERS = []
if "default" in DATABASES:  # noqa: F405
    DATABASES = {"default": DATABASES["default"]}  # noqa: F405

"""EHL HTTP integration.

The submission endpoint intentionally is not implemented in the initial setup.
"""

from api.client import EHLClient
from api.models import APIError, ForbiddenError, Game, NotFoundError, UnauthorizedError

__all__ = [
    "APIError",
    "EHLClient",
    "ForbiddenError",
    "Game",
    "NotFoundError",
    "UnauthorizedError",
]

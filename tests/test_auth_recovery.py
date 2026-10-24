"""Regression tests for Somfy authentication and session recovery.

Run in a Home Assistant development environment with pytest installed.
"""

from unittest.mock import AsyncMock

import pytest

from custom_components.somfy_protexial.protexial import SomfyProtexial
from custom_components.somfy_protexial.somfy_exception import (
    SomfyAuthError,
    SomfyException,
)


@pytest.mark.asyncio
async def test_invalid_credentials_never_trigger_session_retry():
    """A rejected password must not cause another login (lockout protection)."""
    client = object.__new__(SomfyProtexial)
    client._SomfyProtexial__logout = AsyncMock()
    client._SomfyProtexial__login = AsyncMock()
    request = AsyncMock(side_effect=SomfyAuthError("Wrong credentials"))

    with pytest.raises(SomfyAuthError):
        await client._SomfyProtexial__with_session_retry(request)

    request.assert_awaited_once()
    client._SomfyProtexial__logout.assert_not_awaited()
    client._SomfyProtexial__login.assert_not_awaited()


@pytest.mark.asyncio
async def test_transient_session_failure_still_recovers():
    """Keep the existing single session recovery attempt for transient faults."""
    client = object.__new__(SomfyProtexial)
    client.cookie = "stale"
    client._SomfyProtexial__logout = AsyncMock()
    client._SomfyProtexial__login = AsyncMock()
    request = AsyncMock(side_effect=[SomfyException("Session expired"), "ok"])

    assert await client._SomfyProtexial__with_session_retry(request) == "ok"

    assert request.await_count == 2
    client._SomfyProtexial__logout.assert_awaited_once()
    client._SomfyProtexial__login.assert_awaited_once()


@pytest.mark.asyncio
async def test_auth_failure_during_retry_is_not_retried_again():
    """A credential error on the recovery login must stop immediately."""
    client = object.__new__(SomfyProtexial)
    client.cookie = "stale"
    client._SomfyProtexial__logout = AsyncMock()
    client._SomfyProtexial__login = AsyncMock(
        side_effect=SomfyAuthError("Wrong credentials")
    )
    request = AsyncMock(side_effect=SomfyException("Session expired"))

    with pytest.raises(SomfyAuthError):
        await client._SomfyProtexial__with_session_retry(request)

    request.assert_awaited_once()
    client._SomfyProtexial__login.assert_awaited_once()

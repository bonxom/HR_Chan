"""Cloudflare Turnstile server-side verification.

The secret key stays on the backend. ``verify`` returns False for a rejected token or a
hostname/action that does not match the configured values; network errors, timeouts and
unexpected replies raise ``CaptchaUnavailableError`` (fail closed). Tokens and secrets
are never logged.
"""

import asyncio
from typing import Protocol

import httpx

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
MAX_TOKEN_CHARS = 2048


class CaptchaUnavailableError(Exception):
    def __init__(self, code: str = "captcha_unavailable") -> None:
        super().__init__(code)
        self.code = code


class CaptchaVerifier(Protocol):
    async def verify(self, token: str, remote_ip: str | None) -> bool: ...


class TurnstileVerifier:
    def __init__(
        self,
        secret_key: str,
        *,
        expected_hostname: str | None = None,
        expected_action: str | None = None,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not secret_key:
            raise ValueError("Turnstile secret key is required")
        self._secret = secret_key
        self._hostname = expected_hostname
        self._action = expected_action
        self._timeout = min(timeout, 10.0)
        self._transport = transport

    async def verify(self, token: str, remote_ip: str | None) -> bool:
        if not token or len(token) > MAX_TOKEN_CHARS:
            return False
        form = {"secret": self._secret, "response": token}
        if remote_ip:
            form["remoteip"] = remote_ip
        try:
            async with asyncio.timeout(self._timeout):
                async with httpx.AsyncClient(
                    timeout=self._timeout, transport=self._transport
                ) as client:
                    response = await client.post(TURNSTILE_VERIFY_URL, data=form)
                    if response.status_code != 200:
                        raise CaptchaUnavailableError("captcha_http_error")
                    body = response.json()
        except CaptchaUnavailableError:
            raise
        except TimeoutError:
            raise CaptchaUnavailableError("captcha_timeout") from None
        except (httpx.HTTPError, ValueError):
            raise CaptchaUnavailableError("captcha_unreachable") from None
        if not isinstance(body, dict):
            raise CaptchaUnavailableError("captcha_bad_reply")
        if body.get("success") is not True:
            return False
        if self._hostname is not None and body.get("hostname") != self._hostname:
            return False
        if self._action is not None and body.get("action") != self._action:
            return False
        return True

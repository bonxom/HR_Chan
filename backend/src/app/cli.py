"""Operational commands: Admin bootstrap, development fixtures, and auth cleanup."""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from datetime import timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import clock
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, Failure
from app.integrations.email.client import build_email_client
from app.modules.accounts import repository as account_repository
from app.modules.accounts import service as account_service
from app.modules.accounts.dev_fixtures import DEV_ACCOUNTS, DEV_SEED_PASSWORD
from app.modules.accounts.models import Account
from app.modules.accounts.rules import AccountStatus
from app.modules.auth.passwords import hash_password_async


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.cli")
    subcommands = parser.add_subparsers(dest="command", required=True)

    bootstrap = subcommands.add_parser(
        "bootstrap-admin", help="Create the first Admin account and send its invitation"
    )
    bootstrap.add_argument("--email", required=True)
    bootstrap.add_argument("--name", required=True)

    cleanup = subcommands.add_parser(
        "cleanup-auth", help="Remove expired rate-limiter, password-link, and token records"
    )
    cleanup.add_argument("--batch-size", type=int, default=500)

    subcommands.add_parser(
        "seed-dev-accounts",
        help="Create or refresh the development quick-login accounts (DEV_SEED_ENABLED)",
    )
    return parser


def auth_configuration_warnings(settings: Settings) -> list[str]:
    """Report missing credential settings so local setup failures are visible early."""
    warnings: list[str] = []
    checks = (
        (settings.require_jwt_secret, "JWT_SECRET"),
        (settings.require_limiter_secret, "LIMITER_SECRET"),
    )
    for accessor, name in checks:
        try:
            accessor()
        except AppError:
            warnings.append(f"{name} is missing or shorter than 32 characters in backend/.env")
    return warnings


def _with_auth_warnings(payload: dict, settings: Settings) -> dict:
    warnings = auth_configuration_warnings(settings)
    if not warnings:
        return payload
    return {
        **payload,
        "warnings": warnings,
        "next": "Add the missing secrets to backend/.env, restart the API, then sign in.",
    }


def _session_factory(settings: Settings) -> tuple[async_sessionmaker, object]:
    engine = create_async_engine(str(settings.database_url), pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False), engine


async def run_bootstrap(values: argparse.Namespace, settings: Settings) -> tuple[int, dict]:
    session_factory, engine = _session_factory(settings)
    client = build_email_client(settings)
    try:
        async with session_factory() as session:
            result = await account_service.bootstrap_admin(
                session,
                full_name=values.name,
                email=values.email,
                settings=settings,
                email_client=client,
            )
    finally:
        await engine.dispose()

    if isinstance(result, Failure):
        return 1, {"status": "refused", "code": result.code, "message": result.message}
    return 0, _with_auth_warnings(
        {
            "status": "created",
            "account_id": str(result.account.id),
            "email": result.account.email,
            "email_delivery": result.email_delivery,
        },
        settings,
    )


async def cleanup_auth(session_factory: async_sessionmaker, batch_size: int) -> dict[str, int]:
    """Delete only records that can no longer authorize or verify anything."""
    now = clock.utcnow()
    removed: dict[str, int] = {}
    statements = {
        "rate_limits": (
            "DELETE FROM auth_rate_limits WHERE key IN ("
            " SELECT key FROM auth_rate_limits WHERE expires_at < :now LIMIT :batch_size)",
            {"now": now, "batch_size": batch_size},
        ),
        "expired_links": (
            "DELETE FROM auth_password_links WHERE id IN ("
            " SELECT id FROM auth_password_links"
            " WHERE expires_at < :cutoff AND consumed_at IS NULL AND invalidated_at IS NULL"
            " LIMIT :batch_size)",
            {"cutoff": now - timedelta(days=1), "batch_size": batch_size},
        ),
        "retired_links": (
            "DELETE FROM auth_password_links WHERE id IN ("
            " SELECT id FROM auth_password_links WHERE expires_at < :cutoff"
            " AND (consumed_at IS NOT NULL OR invalidated_at IS NOT NULL) LIMIT :batch_size)",
            {"cutoff": now - timedelta(days=1), "batch_size": batch_size},
        ),
        "refresh_tokens": (
            "DELETE FROM auth_refresh_tokens WHERE id IN ("
            " SELECT tok.id FROM auth_refresh_tokens AS tok"
            " JOIN auth_sessions AS ses ON ses.id = tok.session_id"
            " WHERE tok.expires_at < :now AND ses.absolute_expires_at < :now LIMIT :batch_size)",
            {"now": now, "batch_size": batch_size},
        ),
    }
    async with session_factory() as session:
        for name, (statement, parameters) in statements.items():
            result = await session.execute(text(statement), parameters)
            removed[name] = result.rowcount or 0
        await session.commit()
    return removed


async def seed_dev_accounts(
    session_factory: async_sessionmaker, settings: Settings
) -> tuple[int, dict]:
    """Create or refresh the `dev.*` fixtures used by the development login buttons."""
    if not settings.dev_seed_enabled:
        return 1, {
            "status": "refused",
            "code": "dev_seed_disabled",
            "message": "Set DEV_SEED_ENABLED=true to seed development accounts",
        }

    password_hash = await hash_password_async(DEV_SEED_PASSWORD)
    async with session_factory() as session:
        await account_repository.acquire_administration_lock(session)
        for email, full_name, account_type, roles in DEV_ACCOUNTS:
            account = await account_repository.get_by_email(session, email, for_update=True)
            if account is None:
                account = Account(
                    full_name=full_name,
                    email=email,
                    account_type=account_type,
                    roles=list(roles),
                    status=AccountStatus.ACTIVE,
                    password_hash=password_hash,
                )
                await account_repository.add_account(session, account)
                continue
            account.full_name = full_name
            account.account_type = account_type
            account.roles = list(roles)
            account.status = AccountStatus.ACTIVE
            account.password_hash = password_hash
        await session.commit()

    return 0, _with_auth_warnings(
        {
            "status": "seeded",
            "accounts": [
                {"email": email, "account_type": account_type.value, "roles": list(roles)}
                for email, _name, account_type, roles in DEV_ACCOUNTS
            ],
        },
        settings,
    )


async def run_cleanup(values: argparse.Namespace, settings: Settings) -> tuple[int, dict]:
    session_factory, engine = _session_factory(settings)
    try:
        removed = await cleanup_auth(session_factory, values.batch_size)
    finally:
        await engine.dispose()
    return 0, {"status": "cleaned", "removed": removed}


async def run_dev_seed(settings: Settings) -> tuple[int, dict]:
    session_factory, engine = _session_factory(settings)
    try:
        return await seed_dev_accounts(session_factory, settings)
    finally:
        await engine.dispose()


async def dispatch(values: argparse.Namespace, settings: Settings) -> tuple[int, dict]:
    if values.command == "bootstrap-admin":
        return await run_bootstrap(values, settings)
    if values.command == "seed-dev-accounts":
        return await run_dev_seed(settings)
    return await run_cleanup(values, settings)


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    values = build_parser().parse_args(argv)
    code, payload = asyncio.run(dispatch(values, settings or get_settings()))
    print(json.dumps(payload))
    return code


if __name__ == "__main__":
    sys.exit(main())

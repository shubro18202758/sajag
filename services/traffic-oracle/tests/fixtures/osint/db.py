"""The SANDBOX database backend of the OS-5 tests (``OSINT_TEST_DSN``).

* Without ``OSINT_TEST_DSN`` every database test is skipped.
* With it, the DSN must point at a sandbox — ``127.0.0.1:56561`` (int3c) or ``127.0.0.1:56562``
  (int3cl) — anything else is REFUSED (the live store on :56434 by name), before a connection is
  opened.
* A test never assumes an empty ``osint`` or ``decision`` schema (the orchestrator seeds the PoC
  captures there): it writes only rows it can name — run-unique signal ids, fused ids prefixed
  ``test-<uuid>``, gazetteer ids in a reserved high range, the corridor events it promoted, the
  decision rows it inserted — asserts only on those, and deletes them on teardown.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import pytest

__all__ = [
    "DSN_ENV",
    "SANDBOX_PORTS",
    "TEST_GAZ_BASE",
    "Cleanup",
    "osint_db",
    "refuse_unsafe_dsn",
    "requires_db",
    "sandbox_dsn",
]

DSN_ENV = "OSINT_TEST_DSN"

#: int3c and int3cl — the only databases these tests may touch.
SANDBOX_PORTS = (56561, 56562)

#: The live store's port: refused by name.
LIVE_PORT = 56434

#: Test gazetteer rows live above this id (the real gazetteer uses small ids).
TEST_GAZ_BASE = 9_000_000_000


def refuse_unsafe_dsn(dsn: str) -> str:
    """``dsn`` when it names a sandbox; ``pytest.fail`` otherwise (never connects)."""
    parts = urlsplit(dsn)
    host, port = parts.hostname, parts.port
    if port == LIVE_PORT:
        pytest.fail(f"{DSN_ENV} names the LIVE store (:{LIVE_PORT}) — refused")
    if host != "127.0.0.1" or port not in SANDBOX_PORTS:
        pytest.fail(f"{DSN_ENV} must be 127.0.0.1:{SANDBOX_PORTS[0]} or :{SANDBOX_PORTS[1]} — refused")
    return dsn


def sandbox_dsn() -> str | None:
    dsn = os.environ.get(DSN_ENV)
    return refuse_unsafe_dsn(dsn) if dsn else None


requires_db = pytest.mark.skipif(
    not os.environ.get(DSN_ENV), reason=f"{DSN_ENV} (a sandbox database) not set"
)


@dataclass
class Cleanup:
    """What a test wrote, deleted on teardown (children first)."""

    tag: str
    signal_ids: set[str] = field(default_factory=set)
    event_ids: set[str] = field(default_factory=set)
    gaz_ids: set[int] = field(default_factory=set)
    dss_ids: set[str] = field(default_factory=set)

    async def run(self, conn: Any) -> None:
        prefix = self.tag + "%"
        sids = sorted(self.signal_ids)
        async with conn.transaction():
            if self.dss_ids:
                ids = sorted(self.dss_ids)
                await conn.execute("DELETE FROM decision.dss_decision_log WHERE dss_id = ANY($1::uuid[])", ids)
                await conn.execute("DELETE FROM decision.decision_support WHERE dss_id = ANY($1::uuid[])", ids)
            await conn.execute(
                "DELETE FROM osint.event_sources WHERE signal_id = ANY($1::text[]) OR osint_event_id IN "
                "(SELECT osint_event_id FROM osint.resolved_events WHERE fused_event_id LIKE $2)",
                sids, prefix,
            )
            await conn.execute("DELETE FROM osint.geocodes WHERE signal_id = ANY($1::text[])", sids)
            await conn.execute("DELETE FROM osint.resolved_events WHERE fused_event_id LIKE $1", prefix)
            await conn.execute("DELETE FROM osint.raw_signals WHERE signal_id = ANY($1::text[])", sids)
            if self.event_ids:
                # the lifecycle already cancelled them; their routes and ledger rows cascade
                await conn.execute(
                    "DELETE FROM events.corridor_events WHERE event_id = ANY($1::uuid[])", sorted(self.event_ids)
                )
            if self.gaz_ids:
                await conn.execute("DELETE FROM osint.gazetteer WHERE gaz_id = ANY($1::bigint[])", sorted(self.gaz_ids))


@asynccontextmanager
async def osint_db(tag: str) -> AsyncIterator[tuple[Any, Cleanup]]:
    """``(pool, cleanup)`` on the sandbox; the cleanup always runs."""
    import asyncpg

    dsn = sandbox_dsn()
    if dsn is None:
        pytest.skip(f"{DSN_ENV} not set")
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=4, command_timeout=30)
    cleanup = Cleanup(tag)
    try:
        yield pool, cleanup
    finally:
        try:
            async with pool.acquire() as conn:
                await cleanup.run(conn)
        finally:
            await pool.close()

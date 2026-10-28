"""Owner: @role-3-official-agents. The ANAF fetch tool: the ONE place a human triggers ANAF requests.

ANAF's rules: max 100 CUIs per request, max 1 request/second, overloading is punished. So:
- DRY RUN BY DEFAULT: it prints the exact request it would send. Only `--send` sends it.
- ONE REQUEST PER RUN. Never a loop: run the command again for the next request.
- At least MIN_INTERVAL_S between ANAF requests ON THIS MACHINE, even across separate runs
  (a lock + timestamp file), on top of the in-process RateLimiter.
- No retries (HTTP_MAX_RETRIES=0 here, and anaf_v9 never retries). Real CUIs only.

Usage (from the repo root, on the machine that holds the mirror):
    uv run python -m apps.worker.jobs.sweep_anaf_v9 status CUI [CUI ...]
        what is in the mirror and what is missing. No request.
    uv run python -m apps.worker.jobs.sweep_anaf_v9 v9 CUI [CUI ...] [--send]
        ONE v9 request: today + the last 4 quarter-ends for each CUI, only the missing ones.
        Max 100 entries (20 companies with nothing in the mirror yet).
    uv run python -m apps.worker.jobs.sweep_anaf_v9 bilant CUI [--send]
        ONE /bilant request: the newest missing year of the last 5. Run again for the next one.

Then process the mirror with ZERO ANAF requests (agents -> scoring -> Postgres):
    SYNC_ON_APPLICATION=0 uv run python -m apps.worker.seed CUI [CUI ...]

The scheduled daily sweep (`run`) is deliberately NOT automated: the team decided that only a
human triggers ANAF requests (docs/DECISIONS.md, "ANAF request safety").
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, cast

from apps.wiring import Infra, build_infra
from verifirm.adapters.anaf_bilant import AnafBilantAdapter
from verifirm.adapters.anaf_v9 import MAX_BATCH, AnafV9Adapter, Entry, _body
from verifirm.agents.financials.rules import expected_last_year
from verifirm.agents.financials.rules import load_config as financials_config
from verifirm.core.config import Settings
from verifirm.core.cui import InvalidCUIError, validate_cui

MIN_INTERVAL_S = 1.1  # ANAF: max 1 request/second. A margin on top, across processes.


async def run(infra: Infra) -> dict[str, Any]:
    """The scheduled sweep is not automated on purpose: only a human triggers ANAF requests.
    Use the CLI above. Raising keeps the scheduler from calling ANAF behind anyone's back."""
    raise NotImplementedError("ANAF requests are triggered by a human: see this module's CLI")


# ---------------------------------------------------------------- one request at a time
@contextmanager
def _locked(path: Path) -> Any:
    """Exclusive lock on `path` (Linux / macOS). Without fcntl (Windows) it only warns."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        try:
            import fcntl
        except ImportError:  # pragma: no cover - Windows
            print("  (no file lock on this OS: never run two fetches at the same time)")
            yield handle
            return
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield handle
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


async def anaf_slot(
    stamp: Path,
    send: Callable[[], Awaitable[Any]],
    *,
    now: Callable[[], float] = time.time,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    min_interval_s: float = MIN_INTERVAL_S,
) -> Any:
    """Run `send` (exactly one ANAF request) at least `min_interval_s` after the previous one
    made from this machine, whatever process made it. The lock is held while waiting, so two
    runs started together are serialized, never sent at once."""
    with _locked(stamp) as handle:
        handle.seek(0)
        try:
            last = float(handle.read().strip() or 0)
        except ValueError:
            last = 0.0
        wait = last + min_interval_s - now()
        if wait > 0:
            await sleep(wait)
        handle.seek(0)
        handle.truncate()
        handle.write(f"{now():.3f}")
        handle.flush()
        return await send()


# ------------------------------------------------------------------------ planning
def real_cuis(raw: list[str]) -> list[str]:
    """Validated real CUIs (fictional ones are refused: they live in fixtures/, not at ANAF)."""
    out = []
    for item in raw:
        try:
            out.append(validate_cui(item, fixture_mode=False))
        except InvalidCUIError as exc:
            raise SystemExit(f"refused {item!r}: {exc}") from exc
    return list(dict.fromkeys(out))


async def plan_v9(v9: AnafV9Adapter, cuis: list[str]) -> list[Entry]:
    entries = [(cui, day) for cui in cuis for day in await v9.missing(cui)]
    if len(entries) > MAX_BATCH:
        raise SystemExit(
            f"{len(entries)} entries: ANAF allows {MAX_BATCH} per request. "
            "Pass fewer CUIs now, and the rest in a later run."
        )
    return entries


def bilant_years(today: date) -> list[int]:
    """The years the financials agent reads, newest first (same rule as the agent)."""
    cfg = financials_config()
    last = expected_last_year(today.year, today.month, cfg.filing_available_from_month)
    return list(range(last, last - cfg.years_of_history, -1))


async def plan_bilant(bilant: AnafBilantAdapter, cui: str, today: date) -> list[int]:
    """Years with no answer in the mirror yet, newest first."""
    return [y for y in bilant_years(today) if await bilant.from_mirror(f"{cui}:{y}") is None]


# ------------------------------------------------------------------------ commands
async def cmd_status(infra: Infra, cuis: list[str]) -> None:
    v9 = cast(AnafV9Adapter, infra.sync_adapters["anaf_v9"])
    bilant = cast(AnafBilantAdapter, infra.sync_adapters["anaf_bilant"])
    today = infra.clock.today()
    for cui in cuis:
        v9_missing = [d.isoformat() for d in await v9.missing(cui)]
        years = await plan_bilant(bilant, cui, today)
        print(
            f"  {cui:>10}  v9 missing: {v9_missing or 'none'}  |  bilant missing: {years or 'none'}"
        )


async def cmd_v9(infra: Infra, cuis: list[str], send: bool, stamp: Path) -> None:
    v9 = cast(AnafV9Adapter, infra.sync_adapters["anaf_v9"])
    entries = await plan_v9(v9, cuis)
    if not entries:
        print("  nothing missing: no request needed")
        return
    print(f"  ONE request, {len(entries)} entries:")
    print("  " + json.dumps(_body(entries)))
    if not send:
        print("  dry run: nothing sent. Add --send to send exactly this request.")
        return
    answers = await anaf_slot(stamp, lambda: v9.download(entries))
    for cui, day in entries:
        record = answers.get((cui, day), "missing")
        state = (
            "not answered"
            if record == "missing"
            else "notFound"
            if record is None
            else (record.get("date_generale") or {}).get("denumire", "?")
        )
        print(f"  {cui:>10} {day.isoformat()}  {state}")


async def cmd_bilant(infra: Infra, cui: str, send: bool, stamp: Path) -> None:
    bilant = cast(AnafBilantAdapter, infra.sync_adapters["anaf_bilant"])
    years = await plan_bilant(bilant, cui, infra.clock.today())
    if not years:
        print("  nothing missing: no request needed")
        return
    year = years[0]
    print(f"  ONE request: GET /bilant?an={year}&cui={cui}  ({len(years) - 1} more after this)")
    if not send:
        print("  dry run: nothing sent. Add --send to send exactly this request.")
        return
    result = await anaf_slot(stamp, lambda: bilant.get_year(cui, year))
    print(f"  {cui} {year}: {'filed' if result.data else 'nothing filed'}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="sweep_anaf_v9", description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=["status", "v9", "bilant"])
    parser.add_argument("cuis", nargs="+")
    parser.add_argument("--send", action="store_true", help="really send the ONE request")
    args = parser.parse_args(argv)
    if args.command == "bilant" and len(args.cuis) != 1:
        raise SystemExit("bilant: one CUI per run (one company-year per request)")

    settings = Settings(fixture_mode=False, http_max_retries=0)
    cuis = real_cuis(args.cuis)
    stamp = settings.object_store_path.parent / "anaf_last_request"

    async def go() -> None:
        infra = build_infra(settings)
        try:
            if args.command == "status":
                await cmd_status(infra, cuis)
            elif args.command == "v9":
                await cmd_v9(infra, cuis, args.send, stamp)
            else:
                await cmd_bilant(infra, cuis[0], args.send, stamp)
        finally:
            await infra.aclose()

    asyncio.run(go())


if __name__ == "__main__":
    main(sys.argv[1:])

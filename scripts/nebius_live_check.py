"""Live, cost-capped integration check of the NVIDIA model on Nebius Token Factory.

Refuses to run unless NEBIUS_API_KEY, NEBIUS_MODEL_ID, PG_INFERENCE_BUDGET_USD and PG_MAX_PAID_CALLS are set
(environment or the git-ignored .env.local). Never prints or stores the key.

Steps:
1. GET /v1/models (no inference charge) and confirm the configured model_id is listed.
2. Check that max_paid_calls x worst-case cost per call fits the budget.
3. Run at most max_paid_calls extractions on the synthetic samples through the production code path
   (NebiusClaimModel + ClaimExtraction + quote grounding).
4. Write a redacted record to evidence/policyguard/nebius_live/<UTC timestamp>.json.

Usage: .venv/bin/python scripts/nebius_live_check.py
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.sanitize import mask_account  # noqa: E402
from policyguard.application.errors import BudgetExhausted  # noqa: E402
from policyguard.application.extraction import ClaimExtraction, RulesExtractor  # noqa: E402
from policyguard.config import PGSettings  # noqa: E402
from policyguard.infra.nebius import NebiusClaimModel  # noqa: E402
from policyguard.seed import SAMPLES  # noqa: E402

HARD_CALL_CAP = 3


class LocalBudget:
    def __init__(self, limit: Decimal, max_calls: int):
        self.limit, self.max_calls = limit, max_calls
        self.reserved, self.spent, self.calls = Decimal(0), Decimal(0), 0

    def reserve(self, usd: Decimal) -> str:
        if self.calls + 1 > self.max_calls or self.reserved + self.spent + usd > self.limit:
            raise BudgetExhausted("local")
        self.reserved += usd
        self.calls += 1
        return "local"

    def settle(self, _r: str, usd: Decimal, actual: Decimal) -> None:
        self.reserved -= usd
        self.spent += actual

    def release(self, _r: str, usd: Decimal) -> None:
        self.reserved -= usd
        self.calls -= 1


def redact_claim(claim: dict) -> dict:
    out = {}
    for name, f in claim.items():
        if f is None:
            out[name] = None
            continue
        value = mask_account(f["value"]) if name == "account_number" else f["value"]
        out[name] = {"value": value, "source": f["source"], "quote_chars": len(f["quote"])}
    return out


def main() -> int:
    s = PGSettings.from_env()
    missing = [n for n, v in (("NEBIUS_API_KEY", s.nebius_api_key), ("NEBIUS_MODEL_ID", s.nebius_model_id),
                              ("PG_INFERENCE_BUDGET_USD", s.budget_usd), ("PG_MAX_PAID_CALLS", s.max_paid_calls))
               if not v]
    if missing:
        print("BLOCKED: set " + ", ".join(missing) + " in the environment or .env.local (git-ignored).")
        return 2
    calls = min(s.max_paid_calls, HARD_CALL_CAP)
    model = NebiusClaimModel.from_settings(s)
    started = datetime.now(UTC)
    record: dict = {"checked_at_utc": started.isoformat(), "provider": "nebius", "base_url": s.nebius_base_url,
                    "model_id": s.nebius_model_id, "budget_usd": str(s.budget_usd), "max_paid_calls": calls,
                    "price_per_mtok_usd": {"input": str(s.price_in_per_mtok), "output": str(s.price_out_per_mtok)},
                    "data": "synthetic samples from policyguard/seed.py", "calls": []}

    listed = model.list_models()
    nvidia = sorted(m.get("id", "") for m in listed if str(m.get("id", "")).lower().startswith("nvidia/"))
    record["models_endpoint"] = {"total_models": len(listed), "nvidia_models": nvidia,
                                 "configured_model_listed": s.nebius_model_id in {m.get("id") for m in listed}}
    if not record["models_endpoint"]["configured_model_listed"]:
        print(f"FAIL: {s.nebius_model_id} is not in GET /v1/models. NVIDIA ids listed: {nvidia}")
        _write(record)
        return 1

    def worst_case(text: str) -> Decimal:
        return (Decimal(len(text) + 1500) * s.price_in_per_mtok
                + Decimal(s.max_output_tokens) * s.price_out_per_mtok) / Decimal(1_000_000)

    samples = list(SAMPLES.items())[:calls]
    worst_total = sum(worst_case(sm["input"]["instruction_text"]) for _, sm in samples)
    record["worst_case_total_usd"] = str(worst_total)
    if worst_total > s.budget_usd:
        print(f"REFUSED: worst case {worst_total} USD exceeds the budget {s.budget_usd} USD")
        _write(record)
        return 1

    budget = LocalBudget(s.budget_usd, calls)
    extraction = ClaimExtraction(RulesExtractor(), model, budget, estimate_usd=worst_case,
                                 cost_usd=lambda u: (Decimal(u.prompt_tokens) * s.price_in_per_mtok
                                                     + Decimal(u.completion_tokens) * s.price_out_per_mtok)
                                 / Decimal(1_000_000))
    failures = 0
    for key, sample in samples:
        text = sample["input"]["instruction_text"]
        at = datetime.now(UTC).isoformat()
        try:
            out = extraction.run(text, {"institution_name": None}, final_attempt=True)
            rec = out.record
            ok = rec.mode == "live"
            failures += 0 if ok else 1
            record["calls"].append({
                "scenario": key, "at_utc": at, "mode": rec.mode, "model_id": rec.model_id,
                "latency_ms": rec.latency_ms, "prompt_tokens": rec.prompt_tokens,
                "completion_tokens": rec.completion_tokens, "est_cost_usd": str(rec.est_cost_usd),
                "outcome": rec.outcome, "error_code": rec.error_code,
                "limitations": [lim.value for lim in out.limitations], "claim_redacted": redact_claim(out.claim.as_dict())})
        except Exception as e:   # recorded, never hidden
            failures += 1
            record["calls"].append({"scenario": key, "at_utc": at, "error": type(e).__name__})
    record["spent_usd_estimate"] = str(budget.spent)
    path = _write(record)
    for c in record["calls"]:
        print(f"{c['scenario']:<15} mode={c.get('mode')} latency_ms={c.get('latency_ms')} "
              f"tokens={c.get('prompt_tokens')}/{c.get('completion_tokens')} outcome={c.get('outcome', c.get('error'))}")
    print(f"spent (estimate from reported usage): {budget.spent} USD; record: {path.relative_to(ROOT)}")
    return 0 if failures == 0 else 1


def _write(record: dict) -> Path:
    out = ROOT / "evidence" / "policyguard" / "nebius_live"
    out.mkdir(parents=True, exist_ok=True)
    path = out / (record["checked_at_utc"].replace(":", "").replace("+0000", "Z")[:17] + ".json")
    path.write_text(json.dumps(record, indent=2))
    return path


if __name__ == "__main__":
    raise SystemExit(main())

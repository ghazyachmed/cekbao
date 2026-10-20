"""Synthetic-fixture evaluation: generic keyword baseline vs CEKBAO rules-only.

Usage:  python scripts/evaluate.py [--out evidence/evaluation.json]

This is NOT a user study and NOT a live-model evaluation. It runs labelled
synthetic fixtures through two systems:

1. KEYWORD_BASELINE: a generic scam-text classifier. It flags a message when it
   contains common scam keywords. For slips it accepts any slip whose fields
   look complete and point to an official account ("document looks right").
2. CEKBAO_RULES_ONLY: the full CEKBAO API in DETERMINISTIC_DEMO mode.

A model-enabled run needs LLM_BASE_URL, LLM_MODEL and LLM_API_KEY. Without them
the script reports the model-enabled row as NOT RUN.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import FIXTURES_DIR, Settings  # noqa: E402
from app.main import create_app, load_samples  # noqa: E402

CODES = {u["user_id"]: u["demo_access_code"] for u in json.loads((FIXTURES_DIR / "demo_users.json").read_text())["users"]}
KEYWORDS = re.compile(r"(?i)\b(urgent|immediately|within \d+ hours|today|discount|gift card|crypto|bitcoin|whatsapp|"
                      r"visa|arrest|deport|police|otp|password|segera|hari ini|potongan|diskon|tanpa ribet)\b")

# Extra slip cases beyond Scenario B (labels: True means an institution record exists).
EXTRA_SLIPS = [
    ({"slip_id": "TRX-SYN-0003", "amount": "7500000.00", "currency": "IDR", "transfer_date": "2025-02-04",
      "destination_account": "8808000000420042", "destination_name": "Universitas Contoh Nusantara",
      "payer_reference": "UCN-SYN-2025-0042"}, False),
    ({"slip_id": "TRX-SYN-0005", "amount": "7500000.00", "currency": "IDR", "transfer_date": "2025-02-10",
      "destination_account": "8808000000420042", "destination_name": "Universitas Contoh Nusantara",
      "payer_reference": "UCN-SYN-2025-0042"}, False),
    ({"slip_id": "TRX-SYN-0007", "amount": "7500000.00", "currency": "IDR", "transfer_date": "2025-03-01",
      "destination_account": "8808000000420042", "destination_name": "Universitas Contoh Nusantara",
      "payer_reference": "UCN-SYN-2025-0042"}, False),
]


def keyword_baseline(message: str) -> str:
    return "FLAG" if KEYWORDS.search(message) else "CLEAR"


def baseline_slip(slip: dict) -> bool:
    """Document-only check: complete fields and an official-looking VA account => 'accepted as paid'."""
    return slip["destination_account"].startswith("88080") and len(slip["destination_account"]) == 16


class Actor:
    def __init__(self, app, user_id):
        self.c = TestClient(app)
        r = self.c.post("/api/session/login", json={"user_id": user_id, "access_code": CODES[user_id]})
        self.csrf = r.json()["csrf_token"]

    def post(self, url, body=None, headers=None):
        return self.c.post(url, json=body, headers={"X-CSRF-Token": self.csrf, **(headers or {})})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "evidence" / "evaluation.json"))
    args = ap.parse_args()
    samples = load_samples(FIXTURES_DIR)
    app = create_app(Settings(db_path=Path(tempfile.mkdtemp(prefix="cekbao-eval-")) / "eval.sqlite3"))
    actors = {u: Actor(app, u) for u in ("stu_ayu", "stu_budi", "stu_citra")}

    msg_cases = []
    for s in samples["tuition_requests"]:
        label = "safe" if s["expected"]["decision"] == "PLAN_ALLOWED_AFTER_STUDENT_CONFIRMATION" else "unsafe"
        msg_cases.append((s, label))
    for s in samples["evaluation_only"]:
        msg_cases.append((s, s["label"]))

    rows = []
    for s, label in msg_cases:
        a = actors[s["persona"]]
        cid = a.post("/api/cases", {"case_type": "tuition_request", "claimed_institution": s["claimed_institution"],
                                    "message": s["message"]}).json()["case_id"]
        v = a.post(f"/api/cases/{cid}/analyze").json()
        pol = v["analysis"]["policy"]
        propose = a.post(f"/api/cases/{cid}/plan/propose", {})
        exported = a.c.get(f"/api/cases/{cid}/evidence.json").status_code == 200
        comparisons = [f for f in pol["findings"]]
        attributed = [f for f in comparisons if f["source_url"] and f["source_synthetic"] is True]
        rows.append({
            "id": s["id"], "label": label,
            "baseline": keyword_baseline(s["message"]),
            "cekbao_decision": pol["decision"], "cekbao_status": pol["overall_status"], "state": v["state"],
            "plan_refused": propose.status_code == 409,
            "completed": v["state"] in ("blocked", "needs_review") and exported,
            "findings": len(comparisons), "attributed": len(attributed),
        })

    # Slips: Scenario B plus extra cases, one evidence case per slip so duplicates do not interfere.
    b = samples["payment_evidence"][0]
    slip_cases = [(sl, b["expected"][sl["slip_id"]] == "CONFIRMED_BY_INSTITUTION_LEDGER") for sl in b["slips"]]
    slip_cases += EXTRA_SLIPS
    slip_rows = []
    for sl, has_record in slip_cases:
        a = actors["stu_budi"]
        cid = a.post("/api/cases", {"case_type": "payment_evidence", "institution_id": "SYN-ID-UCN",
                                    "slips": [sl]}).json()["case_id"]
        v = a.post(f"/api/cases/{cid}/analyze").json()
        status = v["analysis"]["settlement"]["results"][0]["settlement_status"]
        slip_rows.append({"slip_id": sl["slip_id"], "institution_record_exists": has_record,
                          "baseline_accepts": baseline_slip(sl), "cekbao_status": status})

    unsafe = [r for r in rows if r["label"] == "unsafe"]
    safe = [r for r in rows if r["label"] == "safe"]
    no_record = [r for r in slip_rows if not r["institution_record_exists"]]
    metrics = {
        "KEYWORD_BASELINE": {
            "scenario_completion": "not applicable (labels only, no workflow)",
            "unsafe_action_refusal": "not applicable (no action gate)",
            "unsafe_messages_flagged": f"{sum(r['baseline'] == 'FLAG' for r in unsafe)}/{len(unsafe)}",
            "false_clearance_messages": sum(r["baseline"] == "CLEAR" for r in unsafe),
            "false_alarm_on_safe": sum(r["baseline"] == "FLAG" for r in safe),
            "false_clearance_slips": sum(r["baseline_accepts"] for r in no_record),
            "evidence_attribution": "0 (no sources cited)",
        },
        "CEKBAO_RULES_ONLY": {
            "scenario_completion": f"{sum(r['completed'] for r in rows)}/{len(rows)}",
            "unsafe_action_refusal": f"{sum(r['plan_refused'] for r in unsafe)}/{len(unsafe)}",
            "unsafe_messages_flagged": f"{sum(r['cekbao_decision'] == 'HOLD_DO_NOT_PAY' for r in unsafe)}/{len(unsafe)}",
            "false_clearance_messages": sum(r["cekbao_decision"] != "HOLD_DO_NOT_PAY" for r in unsafe),
            "false_alarm_on_safe": sum(r["cekbao_decision"] == "HOLD_DO_NOT_PAY" for r in safe),
            "false_clearance_slips": sum(r["cekbao_status"] == "CONFIRMED_BY_INSTITUTION_LEDGER" for r in no_record),
            "evidence_attribution": f"{sum(r['attributed'] for r in rows)}/{sum(r['findings'] for r in rows)} findings "
                                    f"cite a source URL with a synthetic label",
        },
        "MODEL_ENABLED": ("NOT RUN: no LLM credentials configured. The adapter is tested only with a mock transport."
                          if not (os.environ.get("LLM_BASE_URL") and os.environ.get("LLM_API_KEY"))
                          else "Credentials present, but this script does not call a paid API without a manual edit."),
    }

    print(f"{'case':<26}{'label':<8}{'keyword baseline':<18}{'CEKBAO decision':<42}{'plan refused'}")
    for r in rows:
        print(f"{r['id']:<26}{r['label']:<8}{r['baseline']:<18}{r['cekbao_decision']:<42}{r['plan_refused']}")
    print(f"\n{'slip':<16}{'record exists':<15}{'baseline accepts':<18}{'CEKBAO status'}")
    for r in slip_rows:
        print(f"{r['slip_id']:<16}{str(r['institution_record_exists']):<15}{str(r['baseline_accepts']):<18}{r['cekbao_status']}")
    print("\nMETRICS (synthetic fixtures only, not a user study):")
    print(json.dumps(metrics, indent=2))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"messages": rows, "slips": slip_rows, "metrics": metrics}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

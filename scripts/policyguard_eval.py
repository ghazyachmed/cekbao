"""Evaluation A vs B on labelled synthetic cases.

A: newest recorded policy version (what plain retrieval of "the latest document" does).
B: half-open temporal selection (the product rule).
Both share the same authority checks and field comparison, so the difference isolates version selection.
Labels follow the specification, so this measures conformance to the specification on synthetic data,
not real-world accuracy. C (validated experience) and D (Memvid) are not evaluated: both are disabled.

Usage: .venv/bin/python scripts/policyguard_eval.py   -> docs/policyguard/EVALUATION.md
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from policyguard.domain.model import (  # noqa: E402
    ApprovalStatus,
    AssessmentKind,
    AuthorityGrant,
    Citation,
    Claim,
    ClaimField,
    EvaluationContext,
    EvidenceLevel,
    Institution,
    PayeeDetails,
    PolicyDecision,
    PolicyVersion,
)
from policyguard.domain.rules import evaluate  # noqa: E402
from policyguard.domain.temporal import HalfOpenIntervalSelector, LatestRecordedSelector  # noqa: E402
from policyguard.seed import GRANTS, INSTITUTIONS, VERSIONS, local  # noqa: E402

TENANT = "eval"


def build():
    insts = {i["institution_id"]: Institution(i["institution_id"], TENANT, i["name"], i["timezone"]) for i in INSTITUTIONS}
    grants = [AuthorityGrant(g["grant_id"], TENANT, g["institution_id"], g["issuer_id"], "tuition_payment_instructions",
                             g["verification_method"], EvidenceLevel(g["evidence_level"]), g["valid_from"], None,
                             g["valid_from"]) for g in GRANTS]
    versions = []
    for v in VERSIONS:
        p, c = v["payee"], v["citation"]
        versions.append(PolicyVersion(
            tenant_id=TENANT, institution_id=v["institution_id"], policy_id=v["policy_id"], version_id=v["version_id"],
            version_label=v["version_label"], source_url=c["source_url"], source_hash="h", issuer_id=v["issuer_id"],
            authority_scope="tuition_payment_instructions", verification_method="registry",
            evidence_level=EvidenceLevel(v["evidence_level"]), valid_from=v["valid_from"], valid_to=v.get("valid_to"),
            valid_tz=v["valid_tz"], recorded_at=v["recorded_at"],
            payee=PayeeDetails(p["payee_name"], p["account_number"], p["currency"], p["bank_name"], p["swift_bic"],
                               tuple(p["channels"])),
            citation=Citation(c["source_id"], c["source_url"], c["source_title"], c["quote"], c["locator"], c["language"]),
            approval_status=ApprovalStatus(v.get("approval_status", "APPROVED")), freshness_deadline=None))
    return insts, grants, versions


def claim(payee: str, account: str, currency: str) -> Claim:
    f = lambda v: ClaimField(v, v, "rules")  # noqa: E731
    return Claim(payee_name=f(payee), account_number=f(account), currency=f(currency), channel=f("bank_transfer"))


def cases():
    old, new, fake = "GB29 SYNT 6016 1331 9268 19", "GB94 SYNT 4000 0055 5501 77", "GB71 SYNT 7777 0000 1234 56"
    out = []
    for day in ("2025-09-15", "2026-03-10", "2026-08-14", "2026-08-31", "2026-09-01", "2026-11-30", "2027-02-01"):
        t = local(day, "Europe/London")
        current = old if t < local("2026-09-01", "Europe/London") else new
        for acct, label in ((old, "old"), (new, "new"), (fake, "third-party")):
            expected = PolicyDecision.CONSISTENT if acct == current else PolicyDecision.CONFLICT
            out.append((f"Aster Bay, {label} account, pay {day}", "inst-asterbay",
                        claim("Aster Bay University", acct, "GBP"), t, expected))
    for day in ("2026-03-01", "2026-12-05"):   # two authorised sources disagree throughout 2026
        out.append((f"Lumen Coast, web account, pay {day}", "inst-lumen",
                    claim("Lumen Coast College", "SYN 501-234567-001", "SGD"), local(day, "Asia/Singapore"),
                    PolicyDecision.REQUIRES_REVIEW))
    out.append(("Lumen Coast, pay 2027-02-01 (handbook ended; web version continues)", "inst-lumen",
                claim("Lumen Coast College", "SYN 501-234567-001", "SGD"), local("2027-02-01", "Asia/Singapore"),
                PolicyDecision.CONSISTENT))
    out.append(("Kestrel Ridge, agent page only", "inst-kestrel",
                claim("KR Admissions Partners Inc.", "0042-118-7765-019", "CAD"), local("2026-11-20", "America/Toronto"),
                PolicyDecision.INSUFFICIENT_EVIDENCE))
    return out


def _mark(decision: PolicyDecision, expected: PolicyDecision) -> str:
    return f"{decision.value}{'' if decision is expected else ' ✗'}"


def main() -> None:
    insts, grants, versions = build()
    as_of = datetime.fromisoformat("2026-10-28T09:00:00+00:00")
    rows, score = [], {"A": 0, "B": 0}
    for name, inst, c, t, expected in cases():
        ctx = EvaluationContext(TENANT, insts[inst], tuple(versions), tuple(grants), as_of)
        a = evaluate(c, ctx, AssessmentKind.NEXT_PAYMENT, t, LatestRecordedSelector()).decision
        b = evaluate(c, ctx, AssessmentKind.NEXT_PAYMENT, t, HalfOpenIntervalSelector()).decision
        score["A"] += a is expected
        score["B"] += b is expected
        rows.append(f"| {name} | {expected.value} | {_mark(a, expected)} | {_mark(b, expected)} |")
    n = len(rows)
    md = ["# Evaluation A vs B (synthetic, labelled by the specification)", "",
          "A = newest recorded policy version; B = half-open temporal selection. Same authority checks and field "
          "comparison. Labels follow the specification, so the numbers measure conformance on synthetic data, not "
          "real-world accuracy. Evaluations C (validated experience) and D (Memvid) were not run: both features are "
          "disabled until evaluated.", "",
          f"Correct decisions: **A {score['A']}/{n}**, **B {score['B']}/{n}** (as of 2026-10-28; Discovered and revoked "
          "versions excluded by both).", "",
          "| Case | Expected | A: newest version | B: temporal |", "|---|---|---|---|", *rows, ""]
    (ROOT / "docs" / "policyguard" / "EVALUATION.md").write_text("\n".join(md))
    print(f"A {score['A']}/{n}, B {score['B']}/{n}")


if __name__ == "__main__":
    main()

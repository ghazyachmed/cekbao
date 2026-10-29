"""Repeatable synthetic seed. Every institution, account, person and URL here is fictional.

Domains use the reserved ``.example`` TLD (RFC 2606). Accounts use the bank code ``SYNT`` or the prefix
``SYN`` so nobody can mistake them for real accounts. Run: ``python -m policyguard.seed``.
"""
from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import Engine, delete, insert, select

from .infra import tables as t

TENANT = "demo-tenant"
DISCOVERED_VERSION_ID = "pv-lcc-web-2027-discovered"


def local(d: str, tz: str) -> datetime:
    """Local midnight of a calendar date, as an aware UTC datetime."""
    return datetime.combine(date.fromisoformat(d), time(0), ZoneInfo(tz)).astimezone(UTC)


def _h(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode()).hexdigest()


INSTITUTIONS = [
    dict(institution_id="inst-asterbay", name="Aster Bay University", country_code="GB", timezone="Europe/London",
         aliases=["Aster Bay Uni", "ABU"], official_contact_url="https://www.asterbay.example/student-finance/contact"),
    dict(institution_id="inst-kestrel", name="Kestrel Ridge Institute of Technology", country_code="CA",
         timezone="America/Toronto", aliases=["Kestrel Ridge", "KRIT"],
         official_contact_url="https://www.kestrelridge.example/bursar/contact"),
    dict(institution_id="inst-lumen", name="Lumen Coast College", country_code="SG", timezone="Asia/Singapore",
         aliases=["LCC"], official_contact_url="https://www.lumencoast.example/finance/contact"),
]

GRANTS = [
    dict(grant_id="grant-abu-finance", institution_id="inst-asterbay", issuer_id="asterbay-student-finance",
         verification_method="Signed registry entry (synthetic)", evidence_level="INSTITUTION_ATTESTED",
         valid_from=local("2024-01-01", "Europe/London")),
    dict(grant_id="grant-krit-bursar", institution_id="inst-kestrel", issuer_id="kestrelridge-bursar",
         verification_method="Signed registry entry (synthetic)", evidence_level="INSTITUTION_ATTESTED",
         valid_from=local("2024-01-01", "America/Toronto")),
    dict(grant_id="grant-lcc-finance", institution_id="inst-lumen", issuer_id="lumencoast-finance-office",
         verification_method="Signed registry entry (synthetic)", evidence_level="INSTITUTION_ATTESTED",
         valid_from=local("2024-01-01", "Asia/Singapore")),
    dict(grant_id="grant-lcc-registry", institution_id="inst-lumen", issuer_id="lumencoast-registry",
         verification_method="Domain control of lumencoast.example (synthetic)", evidence_level="PUBLIC_SOURCE",
         valid_from=local("2024-01-01", "Asia/Singapore")),
]

SOURCES = [
    dict(source_id="src-abu-2025", institution_id="inst-asterbay", issuer_id="asterbay-student-finance",
         url="https://www.asterbay.example/student-finance/pay-tuition", title="Paying your tuition fees (2025/26)",
         language="en", fetched_at=local("2025-07-02", "Europe/London")),
    dict(source_id="src-abu-2026", institution_id="inst-asterbay", issuer_id="asterbay-student-finance",
         url="https://www.asterbay.example/student-finance/pay-tuition", title="Paying your tuition fees (2026/27)",
         language="en", fetched_at=local("2026-08-11", "Europe/London")),
    dict(source_id="src-krit-partner", institution_id="inst-kestrel", issuer_id="kr-admissions-partners",
         url="https://www.kr-admissions-partners.example/fr/depot", title="Dépôt d'admission – étudiants internationaux",
         language="fr", fetched_at=local("2026-10-20", "America/Toronto")),
    dict(source_id="src-lcc-web", institution_id="inst-lumen", issuer_id="lumencoast-finance-office",
         url="https://www.lumencoast.example/finance/fees", title="Fee payment (Finance Office)", language="en",
         fetched_at=local("2026-10-01", "Asia/Singapore")),
    dict(source_id="src-lcc-handbook", institution_id="inst-lumen", issuer_id="lumencoast-registry",
         url="https://www.lumencoast.example/handbook-2026.pdf", title="Student Handbook 2026, page 14",
         language="en", fetched_at=local("2026-02-03", "Asia/Singapore")),
]


def _payee(name, account, currency, bank, swift, channels=("bank_transfer",)):
    return {"payee_name": name, "account_number": account, "currency": currency, "bank_name": bank,
            "swift_bic": swift, "channels": list(channels)}


def _cite(source_id, quote, locator, language="en", translation=None):
    src = next(s for s in SOURCES if s["source_id"] == source_id)
    return {"source_id": source_id, "source_url": src["url"], "source_title": src["title"], "quote": quote,
            "locator": locator, "language": language, "translation": translation}


VERSIONS = [
    dict(version_id="pv-abu-2025", institution_id="inst-asterbay", policy_id="abu-tuition", version_label="2025.1",
         source_id="src-abu-2025", issuer_id="asterbay-student-finance", evidence_level="INSTITUTION_ATTESTED",
         valid_from=local("2025-08-01", "Europe/London"), valid_to=local("2026-09-01", "Europe/London"),
         valid_tz="Europe/London", recorded_at=local("2025-07-02", "Europe/London"),
         freshness_deadline=local("2026-09-01", "Europe/London"),
         payee=_payee("Aster Bay University", "GB29 SYNT 6016 1331 9268 19", "GBP", "Synthetic Bank plc", "SYNTGB2L",
                      ("bank_transfer", "card_portal")),
         citation=_cite("src-abu-2025", "Tuition fees must be paid to Aster Bay University, IBAN GB29 SYNT 6016 1331 "
                        "9268 19 (SWIFT SYNTGB2L). We never ask you to pay a third party.", "Section 2, paragraph 1")),
    dict(version_id="pv-abu-2026", institution_id="inst-asterbay", policy_id="abu-tuition", version_label="2026.1",
         source_id="src-abu-2026", issuer_id="asterbay-student-finance", evidence_level="INSTITUTION_ATTESTED",
         valid_from=local("2026-09-01", "Europe/London"), valid_to=None, valid_tz="Europe/London",
         recorded_at=local("2026-08-11", "Europe/London"), supersedes_version_id="pv-abu-2025",
         freshness_deadline=local("2027-03-01", "Europe/London"),
         payee=_payee("Aster Bay University", "GB94 SYNT 4000 0055 5501 77", "GBP", "Synthetic Bank plc", "SYNTGB2L",
                      ("bank_transfer", "card_portal")),
         citation=_cite("src-abu-2026", "From 1 September 2026, pay tuition only to Aster Bay University, IBAN GB94 "
                        "SYNT 4000 0055 5501 77 (SWIFT SYNTGB2L). The previous account closes on 31 August 2026. "
                        "We never ask you to pay a third party.", "Section 2, paragraph 1")),
    dict(version_id="pv-krit-partner", institution_id="inst-kestrel", policy_id="krit-deposit", version_label="2026-10",
         source_id="src-krit-partner", issuer_id="kr-admissions-partners", evidence_level="PUBLIC_SOURCE",
         valid_from=local("2026-10-01", "America/Toronto"), valid_to=None, valid_tz="America/Toronto",
         recorded_at=local("2026-10-20", "America/Toronto"), freshness_deadline=local("2027-01-01", "America/Toronto"),
         payee=_payee("KR Admissions Partners Inc.", "0042-118-7765-019", "CAD", "Banque Synthétique", "KRAPCAT2"),
         citation=_cite("src-krit-partner", "Le dépôt d'admission doit être versé à KR Admissions Partners Inc., "
                        "compte 0042-118-7765-019.", "Section « Paiement »", "fr",
                        "The admission deposit must be paid to KR Admissions Partners Inc., account 0042-118-7765-019.")),
    dict(version_id="pv-lcc-web-2026", institution_id="inst-lumen", policy_id="lcc-fees-web", version_label="2026.2",
         source_id="src-lcc-web", issuer_id="lumencoast-finance-office", evidence_level="INSTITUTION_ATTESTED",
         valid_from=local("2026-01-01", "Asia/Singapore"), valid_to=None, valid_tz="Asia/Singapore",
         recorded_at=local("2026-10-01", "Asia/Singapore"), freshness_deadline=local("2027-01-01", "Asia/Singapore"),
         payee=_payee("Lumen Coast College", "SYN 501-234567-001", "SGD", "Synthetic Bank (Singapore)", "SYNTSGS1"),
         citation=_cite("src-lcc-web", "Pay all tuition fees to Lumen Coast College, account SYN 501-234567-001.",
                        "Fee payment, step 2")),
    dict(version_id="pv-lcc-handbook-2026", institution_id="inst-lumen", policy_id="lcc-fees-handbook",
         version_label="2026", source_id="src-lcc-handbook", issuer_id="lumencoast-registry",
         evidence_level="PUBLIC_SOURCE", valid_from=local("2026-01-01", "Asia/Singapore"),
         valid_to=local("2027-01-01", "Asia/Singapore"), valid_tz="Asia/Singapore",
         recorded_at=local("2026-02-03", "Asia/Singapore"), freshness_deadline=local("2027-01-01", "Asia/Singapore"),
         payee=_payee("Lumen Coast College", "SYN 501-765432-009", "SGD", "Synthetic Bank (Singapore)", "SYNTSGS1"),
         citation=_cite("src-lcc-handbook", "Tuition is payable to Lumen Coast College, account SYN 501-765432-009.",
                        "Page 14, 'Fees'")),
    dict(version_id=DISCOVERED_VERSION_ID, institution_id="inst-lumen", policy_id="lcc-fees-web",
         version_label="2027.1 (discovered)", source_id="src-lcc-web", issuer_id="lumencoast-finance-office",
         evidence_level="INSTITUTION_ATTESTED", valid_from=local("2027-01-01", "Asia/Singapore"), valid_to=None,
         valid_tz="Asia/Singapore", recorded_at=local("2026-10-25", "Asia/Singapore"), approval_status="DISCOVERED",
         discovered_by="ingestion-bot",
         payee=_payee("Lumen Coast College", "SYN 501-234567-001", "SGD", "Synthetic Bank (Singapore)", "SYNTSGS1"),
         citation=_cite("src-lcc-web", "From 1 January 2027, pay fees to Lumen Coast College, account "
                        "SYN 501-234567-001.", "Fee payment, notice")),
]

_FOOTER = "\n\n[SYNTHETIC EXAMPLE: fictional institution, people and accounts]"

SAMPLES: dict[str, dict] = {
    "conflict": {
        "title": "Payee changed to a third party",
        "input": dict(institution_id="inst-asterbay", payment_tz="Europe/London", instruction_received_on="2026-10-27",
                      due_on="2026-11-15", instruction_text=(
                          "From: Student Finance Team <finance-update@asterbay-payments.example>\n"
                          "Subject: Updated tuition payment details - action required\n\n"
                          "Dear student,\n\nAster Bay University has moved tuition collection to a new processing "
                          "partner. Please pay your Term 2 balance of GBP 9,250.00 by 15 November 2026 by bank "
                          "transfer.\n\nPayee: Northbridge Education Services Ltd\nIBAN: GB71 SYNT 7777 0000 1234 56\n"
                          "SWIFT/BIC: NBESGB2L\n\nPayments to the old account will be rejected after 31 October.\n\n"
                          "Kind regards,\nStudent Finance Team" + _FOOTER)),
    },
    "policy_change": {
        "title": "Old invoice after an account change",
        "input": dict(institution_id="inst-asterbay", payment_tz="Europe/London", instruction_received_on="2026-07-02",
                      paid_on="2026-08-14", due_on="2026-11-30", instruction_text=(
                          "ASTER BAY UNIVERSITY - TUITION INVOICE\nInvoice: ABU-SYN-2026-0193   Issued: 2 July 2026\n"
                          "Amount due: GBP 4,625.00 (instalment 2 of 3), due by 30 November 2026\n"
                          "Method: bank transfer\nPayee: Aster Bay University\nIBAN: GB29 SYNT 6016 1331 9268 19\n"
                          "SWIFT/BIC: SYNTGB2L" + _FOOTER)),
    },
    "insufficient": {
        "title": "Agent page without issuer authority",
        "input": dict(institution_id="inst-kestrel", payment_tz="America/Toronto", instruction_received_on="2026-10-26",
                      due_on="2026-11-20", instruction_text=(
                          "Kestrel Ridge Admissions Partners\n\nHello! To secure your seat at Kestrel Ridge Institute of "
                          "Technology, send the first-term deposit of CAD 3,000.00 by 20 November 2026 by bank "
                          "transfer.\n\nPayee: KR Admissions Partners Inc.\nAccount: 0042-118-7765-019\n"
                          "SWIFT/BIC: KRAPCAT2\n\nThis is the official payment page for international applicants."
                          + _FOOTER)),
    },
    "source_conflict": {
        "title": "Two official sources disagree",
        "input": dict(institution_id="inst-lumen", payment_tz="Asia/Singapore", instruction_received_on="2026-10-24",
                      due_on="2026-12-05", instruction_text=(
                          "Lumen Coast College - Fee reminder\n\nSemester 1 fees: SGD 12,400.00 due 5 December 2026.\n"
                          "Pay by bank transfer to:\nPayee: Lumen Coast College\nAccount: SYN 501-234567-001\n"
                          "SWIFT/BIC: SYNTSGS1" + _FOOTER)),
    },
}


def load_demo(engine: Engine, now: datetime, tenant_id: str = TENANT) -> None:
    """Idempotent: deletes and re-inserts the synthetic registry for one tenant. Cases are kept."""
    scope = "tuition_payment_instructions"
    with engine.begin() as conn:
        if conn.execute(select(t.tenants.c.tenant_id).where(t.tenants.c.tenant_id == tenant_id)).first() is None:
            conn.execute(insert(t.tenants).values(tenant_id=tenant_id, name="CEKBAO demo workspace (synthetic)"))
        for table in (t.policy_versions, t.source_documents, t.authority_grants):
            conn.execute(delete(table).where(table.c.tenant_id == tenant_id))
        existing = set(conn.execute(select(t.institutions.c.institution_id)
                                    .where(t.institutions.c.tenant_id == tenant_id)).scalars())
        for inst in INSTITUTIONS:
            if inst["institution_id"] not in existing:
                conn.execute(insert(t.institutions).values(tenant_id=tenant_id, synthetic=True, **inst))
        conn.execute(insert(t.authority_grants), [dict(g, tenant_id=tenant_id, authority_scope=scope, valid_to=None,
                                                       recorded_at=g["valid_from"]) for g in GRANTS])
        conn.execute(insert(t.source_documents), [dict(s, tenant_id=tenant_id, content_hash=_h(str(s["source_id"])),
                                                       synthetic=True) for s in SOURCES])
        rows = []
        for v in VERSIONS:
            src = next(s for s in SOURCES if s["source_id"] == v["source_id"])
            rows.append({"approval_status": "APPROVED", "supersedes_version_id": None, "freshness_deadline": None,
                         "discovered_by": None, **v, "tenant_id": tenant_id, "source_url": src["url"],
                         "source_hash": _h(v["source_id"]), "authority_scope": scope,
                         "verification_method": "registry_contract", "fetched_at": src["fetched_at"],
                         "verified_at": src["fetched_at"], "extraction_version": "manual-synthetic-1",
                         "synthetic": True, "approved_by": None if v.get("approval_status") else "seed",
                         "approved_at": None if v.get("approval_status") else now})
        conn.execute(insert(t.policy_versions), rows)


def main() -> None:
    from sqlalchemy import create_engine

    from .config import PGSettings
    engine = create_engine(PGSettings.from_env().database_url)
    load_demo(engine, datetime.now(UTC))
    print(f"seeded tenant {TENANT}: {len(INSTITUTIONS)} institutions, {len(VERSIONS)} policy versions (synthetic)")


if __name__ == "__main__":
    main()

# Evaluation A vs B (synthetic, labelled by the specification)

A = newest recorded policy version; B = half-open temporal selection. Same authority checks and field comparison. Labels follow the specification, so the numbers measure conformance on synthetic data, not real-world accuracy. Evaluations C (validated experience) and D (Memvid) were not run: both features are disabled until evaluated.

Correct decisions: **A 15/25**, **B 25/25** (as of 2026-10-28; Discovered and revoked versions excluded by both).

| Case | Expected | A: newest version | B: temporal |
|---|---|---|---|
| Aster Bay, old account, pay 2025-09-15 | CONSISTENT | CONFLICT ✗ | CONSISTENT |
| Aster Bay, new account, pay 2025-09-15 | CONFLICT | CONSISTENT ✗ | CONFLICT |
| Aster Bay, third-party account, pay 2025-09-15 | CONFLICT | CONFLICT | CONFLICT |
| Aster Bay, old account, pay 2026-03-10 | CONSISTENT | CONFLICT ✗ | CONSISTENT |
| Aster Bay, new account, pay 2026-03-10 | CONFLICT | CONSISTENT ✗ | CONFLICT |
| Aster Bay, third-party account, pay 2026-03-10 | CONFLICT | CONFLICT | CONFLICT |
| Aster Bay, old account, pay 2026-08-14 | CONSISTENT | CONFLICT ✗ | CONSISTENT |
| Aster Bay, new account, pay 2026-08-14 | CONFLICT | CONSISTENT ✗ | CONFLICT |
| Aster Bay, third-party account, pay 2026-08-14 | CONFLICT | CONFLICT | CONFLICT |
| Aster Bay, old account, pay 2026-08-31 | CONSISTENT | CONFLICT ✗ | CONSISTENT |
| Aster Bay, new account, pay 2026-08-31 | CONFLICT | CONSISTENT ✗ | CONFLICT |
| Aster Bay, third-party account, pay 2026-08-31 | CONFLICT | CONFLICT | CONFLICT |
| Aster Bay, old account, pay 2026-09-01 | CONFLICT | CONFLICT | CONFLICT |
| Aster Bay, new account, pay 2026-09-01 | CONSISTENT | CONSISTENT | CONSISTENT |
| Aster Bay, third-party account, pay 2026-09-01 | CONFLICT | CONFLICT | CONFLICT |
| Aster Bay, old account, pay 2026-11-30 | CONFLICT | CONFLICT | CONFLICT |
| Aster Bay, new account, pay 2026-11-30 | CONSISTENT | CONSISTENT | CONSISTENT |
| Aster Bay, third-party account, pay 2026-11-30 | CONFLICT | CONFLICT | CONFLICT |
| Aster Bay, old account, pay 2027-02-01 | CONFLICT | CONFLICT | CONFLICT |
| Aster Bay, new account, pay 2027-02-01 | CONSISTENT | CONSISTENT | CONSISTENT |
| Aster Bay, third-party account, pay 2027-02-01 | CONFLICT | CONFLICT | CONFLICT |
| Lumen Coast, web account, pay 2026-03-01 | REQUIRES_REVIEW | CONSISTENT ✗ | REQUIRES_REVIEW |
| Lumen Coast, web account, pay 2026-12-05 | REQUIRES_REVIEW | CONSISTENT ✗ | REQUIRES_REVIEW |
| Lumen Coast, pay 2027-02-01 (handbook ended; web version continues) | CONSISTENT | CONSISTENT | CONSISTENT |
| Kestrel Ridge, agent page only | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE |

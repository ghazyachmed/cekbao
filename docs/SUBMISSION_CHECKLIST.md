# CEKBAO submission checklist

Source of requirements: official FinTechathon 2026 International Track brochure (PDF linked as Appendix 2 at https://www.pol.cmu.ac.th/public/blog/attachment/download/7a51866a-4cee-42b5-9187-fa4e1f4df411), read on 20 October 2026. The local files `international-topics-rules-en.docx` and `international-registration-form-en.xlsx` were **not found** on this machine. Check them if the organizer sent them.

## 1. Official constraints (from the brochure)

| Item | Requirement | CEKBAO status |
|---|---|---|
| Theme | "AI as a Financial Participant": an AI agent that completes real tasks in a financial scenario | Agent workflow implemented. LLM extraction optional and not live-verified. Deterministic decision layer |
| Topic | C: Cross-border & Student Finance Assistant (remittances, tuition payments, credit building, multi-currency) | Tuition-payment verification and FX quote comparison |
| Scoring | Task completion 40%, security and compliance 30%, innovation and interaction 30% | See docs |
| Eligibility | Full-time students at overseas universities. At least 60% non-Chinese nationals | **Team to confirm** |
| Team size | 2 to 5 students | 2 members (HMIF) |
| Language | English for submissions, presentations and reviews | All docs and UI in English |
| Deadline | 20 October 2026, 23:59 Beijing time (UTC+8) = 15:59 UTC = **22:59 WIB** | Open |
| Updates | Submissions may be updated before the deadline. The latest version counts | Submit early, update later |
| Integrity and IP | Independent work. Third-party code and data properly licensed | MIT for own code, `THIRD_PARTY_NOTICES.md`, synthetic data only. Disclose AI assistance if the organizer asks |
| Contact | Website fintechathon.g-ican.com. E-mail wangyr@pbcsf.tsinghua.edu.cn | Check the organizer's submission instructions |

## 2. Deliverables

| # | Official item | File(s) | Status |
|---|---|---|---|
| 01 | Technical documentation: system architecture, core algorithm description, security design | `docs/TECHNICAL.md` (+ security design in `docs/SECURITY_SELF_ASSESSMENT.md`) | Done (Markdown). Export to PDF if the form needs a file |
| 02 | Presentation deck: final presentation of 10 minutes or less | `docs/PITCH_OUTLINE.md` (outline). The old `CEKBAO_Pitch_Deck_DRAFT.pptx` is **outdated** (it says the agent is not implemented) | **Open:** build or update the deck from the outline |
| 03 | Demo video (optional, 5 minutes or less) | `docs/DEMO_STORYBOARD.md` | **NOT DONE.** Record manually |
| 04 | Source code with README, GitHub repository link, deployment instructions and test cases | `README.md`, `app/`, `tests/`, `requirements*.txt` | Code done. **Open:** create the GitHub repository and push (manual) |
| 05 | Security self-assessment: permission-tier implementation and known-risk list | `docs/SECURITY_SELF_ASSESSMENT.md` | Done |
| 06 | Execution evidence (non-on-chain): simulated-account or sandbox operation logs and demo video | `docs/EXECUTION_EVIDENCE.md`, `evidence/` | Logs done. **Video open** (same as 03) |

## 3. Steps left for the team (in order)

1. Review all changed files. Run `.venv/bin/python -m pytest -q` once more.
2. Decide what to do with `CEKBAO_FinTechathon_2026_DRAFT_Package/`. It is outdated. Keep it out of the submission, or keep it only as clearly labelled history.
3. Commit locally (commands in the final handover message). Create a GitHub repository yourself. Push. Copy the real URL into the submission form. Do not invent a URL.
4. Record the demo video (5 minutes or less) with `docs/DEMO_STORYBOARD.md`.
5. Build or update the deck from `docs/PITCH_OUTLINE.md`. Re-check the FBI source before using it.
6. Confirm eligibility (60% non-Chinese nationals, full-time students) and fill the registration form.
7. Submit before **22:59 WIB on 20 October 2026**. Update later if needed.

## 4. Things CEKBAO must not claim

- "Fraud-free", "bank verified", "100% accurate", "recipient verified", "official university partner", "first" or "only".
- Any live-LLM accuracy. The LLM path is mock-tested only.
- Any real institution in the registry. There is none.

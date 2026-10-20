# CEKBAO | FinTechathon 2026 | HMIF

Current artifact status: OFFLINE REFERENCE SANDBOX + DRAFT SUBMISSION DOCUMENTS. It is NOT a working LLM-driven product and NOT submission-ready.

**Topic C:** Cross-border & Student Finance Assistant. **Concept:** Review tuition-payment requests against curated university policies before payment. Student keeps control of any action. No payments or bank lookups occur in this code.

## Directory
- `sandbox/checker.py`: deterministic matching engine using fictional hardcoded payment policies.
- `sandbox/fixtures.json`: four entirely synthetic situations.
- `sandbox/tests.py`: actual offline unit tests.
- `sandbox/run_demo.py`: reproducible four-scenario execution.
- `sandbox/execution_results.json`, `sandbox/*txt`: saved local proof.
- `docs/`: drafts of technical documentation, security assessment, execution evidence, and presenter notes.
- `slides/`: editable PowerPoint and PDF deck for preview. Planned capabilities are NOT labeled implemented.

## Run
Requires only Python 3.10+ standard library. No API key or installation needed.

```bash
cd sandbox
python run_demo.py
python -m unittest -v tests
```

**Observed on 2026-10-20 04:36 UTC:** 4/4 scripted synthetic scenarios matched expected states; 10/10 unit tests passed. This tests the deterministic reference engine only, not a live model agent, backend authorization, or efficacy with real students.

## Major missing requirements
Actual AI orchestration; trusted source integration; authenticated permissions; end-to-end application; secured action approvals; audited deployment; actual demo-video recording; judge-accessible GitHub repository; team sign-off. Do not present this partial package as a complete submission.

## Problem sources
- Singapore Police, 19 March 2026: https://www.police.gov.sg/Media-Hub/News/2026/03/20260319_police_advisory_on_resurgence_of_impersonation_scams_involving_educational_institutions
- Initial UMTS incident reporting, February 2025: https://www.detik.com/sumut/hukum-dan-kriminal/d-7791580/ada-273-korban-diduga-ditipu-2-mahasiwa-hingga-rp-1-2-m-di-sidimpuan
- Later 2026 court report with narrower audit value: https://www.detik.com/sumut/hukum-dan-kriminal/d-8325227/2-penipu-rekan-sesama-mahasiswa-rp-1-2-m-di-sidimpuan-divonis-hingga-3-tahun-bui
- Official competition Appendix 2: https://www.pol.cmu.ac.th/public/blog/attachment/download/7a51866a-4cee-42b5-9187-fa4e1f4df411

## Third-party notice
Python standard library only is used in the baseline. Slide generation relies on python-pptx, and the PDF document build uses ReportLab in the authoring environment. No external images or private personal data are embedded in this package.

## Manual Git control
Do not publish or push this draft automatically. Review all source and data first, and complete the missing agent and permissions before finalizing repository access to judges.

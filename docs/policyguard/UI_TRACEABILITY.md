# User task → screen → test traceability (frontend)

Implementation status, test status and user-validation status are separate columns. "User validation" means sessions with real participants; none were held, so that column is "not done" everywhere.

| User task | Screen / route | Behavioural tests (`tests/pgtests/test_web.py`) | Automated UI evidence (`evidence/policyguard/ui/`) | User validation |
|---|---|---|---|---|
| Sign in with a demo account | A. `/check/sign-in` | `test_check_requires_sign_in`, `test_expired_session_keeps_the_instruction_on_the_page` | `screens/sign-in-*.png`, `axe/sign-in-*.json`, Lighthouse | not done |
| Enter a payment instruction | A. `/check` | `test_form_has_labels_landmarks_and_synthetic_examples`, `test_validation_errors_are_summarized_and_input_is_preserved` | `screens/check-form-*.png`, `screens/check-errors-1024.png` | not done |
| Select or name the institution (incl. not listed) | A. `/check` | `test_unknown_institution_needs_a_name` | keyboard run in `audit-summary.json` | not done |
| Give the intended and earlier payment dates | A. `/check` | `test_validation_errors_*` (date format), `test_policy_change_shows_both_dates_and_versions` | `screens/check-form-*.png` | not done |
| Attach a supporting document | A. `/check` (upload) | `test_upload_rejection_reason_is_returned` | `screens/upload-rejected-1024.png` | not done |
| Avoid duplicate submissions | A → C | `test_submit_redirects_and_duplicate_submission_returns_same_case` | — | not done |
| Follow processing | C. `/check/cases/{id}` | `test_processing_page_reflects_backend_state_without_fake_progress` | `screens/processing-1024.png` | not done |
| Understand the result and next action | D. `/check/cases/{id}` | `test_result_reading_order_and_no_safety_claim`, `test_decision_labels`, `test_every_next_action_and_failure_state_has_text` | `screens/result-*-{320..1440}.png` | not done |
| Compare instruction and policy detail by detail | D. comparison table | `test_comparison_table_is_the_core_of_the_result`, `test_comparison_marks_a_source_without_authority`, `test_comparison_shows_both_conflicting_sources` | `screens/result-conflict-375.png` (stacked), `-1440.png` (table) | not done |
| Inspect evidence (quote, version, validity, retrieval, translation) | E. evidence cards | `test_translated_evidence_is_labeled_and_original_kept`, `test_result_reading_order_*` (quote, "Effective from", "Retrieved on") | `screens/result-insufficient-*.png` | not done |
| Review what was read and correct it | B. "What we read" + `/check?correct=` | covered indirectly by result tests; correction form fields rendered | `screens/result-*` | not done |
| Find earlier checks | `/check/history` | `test_status_json_is_tenant_and_owner_scoped` | `screens/history-*.png` | not done |
| Review a check as the institution | F. `/review`, `/review/cases/{id}` | `test_reviewer_workspace_is_server_enforced` | `screens/review-queue-*.png`, `screens/review-case-*.png` | not done |
| Distinguish policy consistency from payment confirmation | D. next-action note, limitations | `test_result_reading_order_and_no_safety_claim` | — | not done |

Cross-cutting checks: axe-core 0 violations on all audited states at 375 and 1440 px; no horizontal overflow at 320–1440 px; keyboard-only main journey completed with visible focus at every stop; Lighthouse lab reports in `lighthouse/` (accessibility 100 on audited pages).

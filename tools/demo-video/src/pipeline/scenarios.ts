// scenario_seeding: the three demonstration scenarios and the repeatable synthetic seed.
import { run } from "./util.ts";

export type Scenario = {
  key: "conflict" | "policy_change" | "insufficient" | "escalation";
  code: "A" | "B" | "C";
  title: string;
  expected: string[];                 // decision headlines the app must show (primary first)
  steps: string[];                    // capture steps, in order
  required: string[];                 // markers without which the capture is rejected
};

const BASE_REQUIRED = ["sign_in_page", "form_open", "click:use_example", "form_filled", "dates_shown",
                       "click:check_instructions", "submitted", "status_shown", "result_shown", "explanation_shown",
                       "evidence_shown"];

export const SCENARIOS: Scenario[] = [
  { key: "conflict", code: "A", title: "payee changed to a third party",
    expected: ["Conflicts with the checked policy."],
    steps: ["institution", "next_action", "explanation", "evidence", "inference"],
    required: [...BASE_REQUIRED, "next_action_shown", "inference_shown"] },
  { key: "policy_change", code: "B", title: "an old invoice after a policy change",
    expected: ["Conflicts with the checked policy.", "Matches the checked policy."],
    steps: ["explanation", "evidence", "earlier_payment"],
    required: [...BASE_REQUIRED, "earlier_payment_shown"] },
  { key: "insufficient", code: "C", title: "a publisher without authority",
    expected: ["Not enough evidence to verify."],
    steps: ["explanation", "evidence"],
    required: BASE_REQUIRED },
  { key: "escalation", code: "C", title: "institution review",
    expected: ["Not enough evidence to verify."],
    steps: [],
    required: ["sign_in_page", "queue_shown", "click:open_case", "review_case_shown", "review_filled",
               "click:record_review", "review_recorded", "review_history_shown"] },
];

/** Re-create the synthetic registry (institutions, grants, sources, policy versions). Idempotent. */
export function seed(): string {
  run("scripts/policyguard_local.sh", ["start"]);
  run(".venv/bin/alembic", ["upgrade", "head"]);
  return run(".venv/bin/python", ["-m", "policyguard.seed"]).trim();
}

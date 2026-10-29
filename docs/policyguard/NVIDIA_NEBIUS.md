# NVIDIA model through Nebius Token Factory

Checked on 2026-10-28, updated 2026-10-29. Status: **IMPLEMENTED and contract-tested; live integration BLOCKED.** Nebius Token Factory onboarding is not available from Indonesia (country not in the billing list; card declined). The hackathon FAQ (https://nebiusglobalaihackathon.devpost.com/details/faqs) treats this as an account-provisioning gap handled case by case via the Nebius Discord, and says an NVIDIA model called through another provider does not qualify. A build.nvidia.com key exists but is not used by the app.

## Selected model

| Field | Value | Source |
|---|---|---|
| Model ID (Nebius) | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | Nebius model page for NVIDIA Nemotron: https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference (lists the ID, 262K context, FP8 serving, $0.06 / $0.24 per 1M input/output tokens) |
| Availability check | Not yet confirmed by API. The official docs list models only through `GET /v1/models`, which needs a key: https://docs.tokenfactory.nebius.com/api-reference/examples/list-of-models.md | `scripts/nebius_live_check.py` performs this check first and stops if the ID is absent |
| Endpoint | `POST https://api.tokenfactory.nebius.com/v1/chat/completions` (OpenAI-compatible) | https://docs.tokenfactory.nebius.com/ |
| Structured output | `response_format: {"type": "json_schema", "json_schema": {"strict": true, ...}}` | https://docs.tokenfactory.nebius.com/ai-models-inference/json.md |
| Rate limits | HTTP 429 with `Retry-After`; dynamic per-minute limits | https://docs.tokenfactory.nebius.com/ai-models-inference/rate-limits.md |
| Weights | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8` and `-BF16` on Hugging Face, not gated, last modified 2026-08-24 | Hugging Face API, `cardData.license_name` |
| License | **NVIDIA Nemotron Open Model License** (last modified 2025-12-15) | https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-nemotron-open-model-license/ |

## Open source or open weight?

The weights are downloadable (open weight). The license is NVIDIA's own license: it allows commercial use, redistribution and derivative models, with conditions (keep notices, a NOTICE line for derivatives, termination if the licensee sues over patents or copyright in the work, indemnity, export compliance, U.S. and Delaware law). The license page makes no claim of OSI approval and it is not one of the standard OSI licenses. CEKBAO therefore calls the model **open weight**, not open source. The license applies to the weights; CEKBAO calls a hosted endpoint and does not redistribute them.

## How CEKBAO uses the model

1. The worker sends the instruction to the model as untrusted data inside `<instruction>` tags. The system prompt is constant (`policyguard/infra/nebius.py`).
2. The model returns, for each field (payee, account, bank, SWIFT/BIC, amount, currency, channel, due date, institution), a value and a verbatim quote. The JSON schema is strict.
3. `policyguard/application/extraction.py::ground` keeps a field only if its quote appears in the instruction and contains the value. Fabricated quotes are dropped (tested).
4. Deterministic temporal rules make the decision (`policyguard/domain/rules.py`). The model never decides.
5. Before each call the budget ledger reserves the worst-case cost; calls beyond the approved budget or call cap are refused and the instruction is read with fixed rules, with a visible limitation.
6. 429, 5xx, timeouts and network errors retry with backoff and jitter (Retry-After respected). On the final attempt the case completes with fixed rules and the limitation "The AI model was unavailable". A 401/403/404 is a configuration error and is not retried.

## Cost bound for the live test

Worst case per call = (instruction characters + 1,500) × $0.06/1M + 1,200 output tokens × $0.24/1M. For the three synthetic samples this is below **$0.002 in total**. The script refuses to run if the worst case exceeds `PG_INFERENCE_BUDGET_USD`, and it never makes more than 3 paid calls.

## To run the live test

```bash
cp .env.example .env.local
```

Edit `.env.local`: set `NEBIUS_API_KEY`, keep `NEBIUS_MODEL_ID=nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, and set an approved `PG_INFERENCE_BUDGET_USD` and `PG_MAX_PAID_CALLS` (at most 3).

```bash
.venv/bin/python scripts/nebius_live_check.py
```

The redacted record (model ID, UTC time, latency, token counts, cost estimate, grounded fields with masked accounts, no key, no instruction text) is written to `evidence/policyguard/nebius_live/`. After that, `npm run demo:build` in `tools/demo-video` records the app with live inference and names the output as the final video instead of a MOCK preview.

## Evidence in this repository

| Claim | Evidence | Status |
|---|---|---|
| Request shape, strict schema, untrusted-data framing | `tests/pgtests/test_nebius_adapter.py` (mock transport, 13 tests) | VERIFIED_LOCAL (contract only) |
| 429 / 5xx / timeout handling, invalid and truncated JSON, fabricated quotes | same file | VERIFIED_LOCAL (contract only) |
| Budget refusal and fallback | `tests/pgtests/test_intake_queue.py::test_17_exhausted_budget_skips_paid_inference` | VERIFIED_LOCAL |
| Live call, model availability, latency, tokens | `scripts/nebius_live_check.py` → `evidence/policyguard/nebius_live/` | BLOCKED: no key or budget (script exit code 2 on 2026-10-28) |

Mock tests and configuration are not evidence of a live integration.

# Devpost submission draft: Nebius x NVIDIA Global AI Hackathon

Draft answers for the submission form. Rules checked on 2026-10-29 at https://nebiusglobalaihackathon.devpost.com/rules.
Deadline: **Friday 30 October 2026, 10:00 am Pacific Time** (Saturday 31 October, 00:00 WIB).

## Nebius access (blocker on 2026-10-29)

The key in hand is from build.nvidia.com. The FAQ says an NVIDIA model called through another provider does not qualify ("Can I call an NVIDIA model through a different provider ... instead of Nebius? No"). The Indonesian card was declined at Nebius billing. Routes listed by the organisers:

1. Credits form with activation code `NEBIUS-DEVPOST-GLOBAL26` (USD 25 Token Factory credits): https://nebius.com/promo-code?utm_promo_event_code=2026-devpost-global-ai-hack&utm_promo_code_type=Token_Factory&utm_promo_activation_code=NEBIUS-DEVPOST-GLOBAL26
2. Nebius Builders Program (another USD 25): https://dev.nebius.com/builders
3. Country or billing problems are "handled case by case with Nebius": Nebius Discord https://discord.gg/eXYTGhgnhK

Fallback if access does not arrive in time: submit the complete draft with the preview video (it states that the model was not called), and replace the video before the deadline if the live run succeeds.

Items marked **[AFTER LIVE RUN]** need numbers from `scripts/nebius_live_check.py` and the final demo build. Items marked **[YOU]** are personal answers that only the entrant can give. Do not submit a rating or a result that was not measured.

## Project overview

**Project name** (50/60 characters)

> CEKBAO: Check a Payment Instruction Before You Pay

**Elevator pitch** (157/200 characters)

> Paste a payment request, pick the institution and the date you pay. NVIDIA Nemotron on Nebius reads it; rules check it against the policy valid on that date.

## Project details

### About the project (Markdown)

```markdown
## Inspiration
Tuition and deposit emails use the university's name, but ask you to pay a new account. On 19 March 2026 the Singapore Police Force reported at least 20 cases of scams impersonating schools since March 2026, with losses of at least S$31,000. The emails asked for urgent payment of school fees to a bank account.
Real payment details also change. An account that was correct in August can be wrong in November. So the question is not only "is this account right?" but "is this account right for the date I pay?".

## What it does
CEKBAO (PolicyGuard) checks a payment instruction against the payment policy an institution published **for the payment date**.
- Paste the instruction, choose the institution, enter the date you intend to pay (and an earlier payment date, if any).
- The result is one of four labels: *Matches the checked policy*, *Conflicts with the checked policy*, *Not enough evidence to verify*, *Institution review required*. It never says "safe to pay".
- The result page shows the next step first, then a detail-by-detail comparison (payee, account, bank code, currency, method), the policy quote, its version, effective period, publisher and authority, and what is still unknown.
- An earlier payment is assessed separately from the next one, against the version valid on each date.
- Unclear cases go to an institution reviewer queue. Payment status always stays "unknown": CEKBAO moves no money.

## How we built it
- **NVIDIA Nemotron 3 Nano** (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`) on **Nebius Token Factory** reads the instruction. We call the OpenAI-compatible chat completions endpoint with a strict JSON schema and temperature 0. Every field must carry a verbatim quote from the instruction; code drops any field whose quote is not in the text. Fixed rules then decide. The model never decides.
- Policy versions are bitemporal: a half-open validity period (valid from, valid to) plus the time we recorded them, with time zones per institution.
- Backend: FastAPI, PostgreSQL (Alembic migrations), Redis. A check is saved first (HTTP 202 after commit) and processed by a worker with leased jobs, a transactional outbox, retries with jitter and dead letters. Idempotency keys, tenant isolation, JWT roles, a hash-chained audit log and a budget ledger that reserves the worst-case model cost before each paid call.
- Frontend: server-rendered English pages with externalized strings, WCAG 2.2 AA checks (axe-core: 0 violations on audited pages), Inter type scale, measured colour contrast.
- Tests: 231 automated tests (pytest, Hypothesis). Query plans checked on 100,000 synthetic cases.
- The demo video is generated from the real app with Playwright and Remotion.

## Challenges we ran into
- Time: "valid on the payment date" needs half-open intervals, time zones and a separate "when did we know it" axis.
- Keeping a language model useful without letting it decide: quotes that code can check, then rules.
- Cost control: the budget ledger refuses any call that could exceed the approved budget.
- Wording: showing a clear next step without implying that a payment is safe.

## What we learned
[YOU: two or three sentences in your own words.]

## Status of the NVIDIA Nemotron call
The worker is built to call NVIDIA Nemotron 3 Nano on Nebius Token Factory, and the adapter is contract-tested. We could not run it live before the deadline: Nebius Token Factory onboarding is not available to us from Indonesia (the country is not in the billing list and our card was declined). The hackathon FAQ asks entrants in this situation to contact Nebius on Discord, and it does not allow other providers, so we did not switch provider. In the demo, fixed rules read every instruction, and every result page says "Fixed rules (no AI model call)". With a Nebius key, `scripts/nebius_live_check.py` checks the model ID and runs three capped calls.
[If the live run succeeds before the deadline, replace this section with the measured results from docs/policyguard/NVIDIA_NEBIUS.md.]

## Limits
All institutions, accounts and people are synthetic. No user testing yet. A policy match is not a payment confirmation.

## What's next
Pilot with a real institution's published payment page, user testing with students, and more languages for instructions.
```

### Built with (21 of 25 tags)

python, fastapi, postgresql, redis, sqlalchemy, alembic, pydantic, jinja2, nvidia-nemotron, nebius-token-factory, opentelemetry, jwt, pytest, hypothesis, playwright, axe-core, lighthouse, remotion, react, typescript, kokoro-tts

### "Try it out" links

- Code: https://github.com/ghazyachmed/cekbao (push the current work to `main` first; GitHub's `main` is still at `745bb1f`).
- Demo video: the YouTube link after upload.

### Image gallery (JPG, PNG or GIF, 5 MB max, 3:2 recommended, up to 15)

Upload `artifacts/demo/gallery/01-cover.jpg` to `07-tested.jpg` in order (1800x1200, 3:2, 0.2 to 0.3 MB each; `npm run demo:gallery` rebuilds them from the latest capture). Do not use `docs/screenshots/`: those show the earlier MVP (payment slips, payment plan), not PolicyGuard.

| File | Shows |
|---|---|
| 01-cover | Three phone captures of the result page |
| 02-result-first | Result and next step (Scenario A) |
| 03-detail-by-detail | Comparison table: instruction against policy |
| 04-policy-versions | 30 November conflicts, 14 August matched |
| 05-evidence-authority | Publisher without authority, French original with unofficial translation |
| 06-how-it-works | Pipeline: saved, leased, Nemotron on Nebius, quote check, rules |
| 07-tested | Measured: tests, axe-core, Lighthouse, query time |

### Demo video URL

YouTube, **Public** (the rules say "publicly visible on YouTube"; the form also accepts unlisted). Under three minutes: the current edit is 2:44.

## Additional info (judges and organizers)

| Field | Draft answer |
|---|---|
| Upload a file | Optional. Not needed. |
| Submitter type | [YOU] Team (Ghazy Achmed Movlech Urbayani, M Azzam Robbani) or individual |
| Organization name | N/A (unless you enter on behalf of HMIF ITB) |
| Country of residence | [YOU] Indonesia |
| Canada province | N/A |
| Track | **Best Apps and Agents**: an app someone would actually use, powered by Nemotron on Token Factory, Nano for fast everyday calls |
| New or existing before 26 August 2026 | **New**, if no code existed before that date: the repository's first commit is 20 October 2026 [YOU confirm] |
| If existing, how updated | N/A |
| Public code repository URL | https://github.com/ghazyachmed/cekbao (MIT licence file at the root, README section "NVIDIA Nemotron on Nebius Token Factory") |
| Working demo / hosted app / test build URL | None hosted (deployment was not authorized). Local run instructions are in the README. If a hosted demo is required, it needs a separate decision and budget. |
| AI tools leveraged | Claude Code (Anthropic) for coding, testing, design review, documentation and the video pipeline; NVIDIA Nemotron 3 Nano on Nebius Token Factory inside the product; Kokoro-82M (open TTS) for the narration voice. |
| Tavily | No |
| Builders & Brews city | [YOU] none, unless you attended an IRL event |
| Age of majority / not an employee of the promotion entities | [YOU] tick only if true |
| Level of learning / AI value for career | [YOU] |

### Nemotron and Nebius questions

**Which model(s) did you use, and why did you choose that size/variant?**

> NVIDIA Nemotron 3 Nano (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`) on Nebius Token Factory. The model has one job: read a payment instruction and return the payee, account, bank, SWIFT/BIC, amount, currency, channel and due date, each with a verbatim quote, as strict JSON. Fixed rules make the decision, so we do not need a large reasoning model. Nano is a mixture-of-experts model with about 3B active parameters: it is fast and cheap per call (USD 0.06 / 0.24 per 1M input / output tokens), and its long context easily holds a full email. This follows the track guidance to let Nano handle fast, everyday calls.

**How would you rate Nemotron's output quality for your use case? (1-10)**

> Fallback if there is no live run: the form needs a number, so pick the value you can defend and say what it is based on. Suggested text: "Not measured on Nebius: Token Factory onboarding was not available from Indonesia before the deadline. We designed for Nemotron 3 Nano because of its strict structured output and long context; the score reflects our expectation, not a measurement." Otherwise: [AFTER LIVE RUN] Base the number on the live results: how many fields were returned with exact quotes, whether any field was dropped by the quote check, and whether the three scenarios gave the expected results. Example wording once measured: "N/10. On our three synthetic instructions, Nemotron returned X of Y fields with exact quotes; the quote check dropped Z. Instruction-following with the strict schema was ...".

**Did you fine-tune, prompt-engineer, or use Nemotron out of the box?**

> Out of the box, no fine-tuning. Prompt engineering plus constraints: a short system prompt that forbids guessing or correcting values, `response_format` with a strict JSON schema, temperature 0, and a rule that every value needs a verbatim quote. Code then checks each quote against the input and drops unsupported fields. If the model is unavailable, returns invalid JSON, or the budget is exhausted, the worker falls back to a deterministic extractor and labels the result as read by rules.

**How did Nemotron's performance compare to other models you've used for similar tasks?**

> Fallback: "We could not compare: no live Nemotron run was possible from Indonesia before the deadline, and we did not use other LLM providers." Otherwise: [AFTER LIVE RUN] We did not benchmark other LLMs. Our baseline is the deterministic regex extractor in the same app. Compare the live Nemotron fields with the rules extractor on the same three instructions and report only what was measured.

**Which Nebius platform capabilities were most valuable and how?**

> Nebius Token Factory's OpenAI-compatible chat completions API: one HTTPS adapter in our worker, no GPU instances or model serving to manage. Structured output with a strict JSON schema, which we validate directly. `GET /v1/models`, which our live check uses to confirm the model ID before any paid call. Clear per-token pricing, which lets our budget ledger reserve the worst-case cost before every call. We did not use GPU instances, Serverless Endpoints or Serverless Jobs.

**How likely are you to recommend running Nemotron on Nebius? (1-10)** and **How would you rate your experience compared to previous environments? (1-10)**

> [YOU, AFTER LIVE RUN] Your own rating and reason.

**What additional features or improvements would have made it more effective?**

> Token Factory onboarding for more countries: Indonesia is not in the billing list, so we could not run our integration live. Also: a public, unauthenticated model availability list (we could not confirm a model ID before we had a key). Per-key spending caps enforced on the server side. Documentation that states which models support strict JSON schema output. Optional character offsets for quoted spans in structured output, so applications can verify grounding without string search.

**What do you most hope to see from the Nemotron team next?**

> A small Nemotron variant tuned for grounded document extraction (fields with source spans), and published multilingual extraction evaluations for invoices and payment instructions.

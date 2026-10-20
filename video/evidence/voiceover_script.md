# CEKBAO demo video: narration script

Voice: Kokoro-82M `af_heart` (Apache-2.0), speed 0.95, generated offline by `scripts/make_audio.py`.
Timecodes are the actual placements in the rendered video. Lines marked *added* describe only what the recorded footage shows.


## 0:00 Hook

- `0:01.00–0:07.27` A student gets an email about tuition. It looks official. But one detail is new: the bank account.
- `0:08.40–0:09.41` Would you pay this?

## 0:12 Mechanism

- `0:12.80–0:17.97` A university usually publishes one official way to pay, such as its student portal.
- `0:19.00–0:22.27` A message can quietly point to a different account instead.
- `0:24.20–0:27.80` The request looks authentic, but the money would go somewhere else.

## 0:30 Reported evidence

- `0:30.60–0:39.94` In Indonesia, about two hundred seventy-three UMTS students were reportedly affected in 2025, according to campus reports.
- `0:40.29–0:47.12` In Singapore, police reported at least twenty education impersonation cases since March 2026.

## 0:47 Root cause

- `0:47.60–0:49.63` And a payment slip is only a claim.
- `0:51.00–0:56.04` It shows what the sender says was sent. It does not show that the university received it.
- `0:57.60–1:00.95` Only the institution's own record can confirm payment.

## 1:03 CEKBAO

- `1:03.60–1:06.48` CEKBAO checks the request before the student pays.
- `1:07.40–1:13.76` It compares the message with evidence, holds anything that does not match, and points to the official next step.

## 1:16 Scenario A (real app)

- `1:17.00–1:22.08` This is the real app, running in a local sandbox. Ayu is a synthetic student.
- `1:23.60–1:27.62` She loads the urgent deposit email and asks CEKBAO to check it.
- `1:29.40–1:35.50` The result is a conflict. Seven details do not match the university's documented procedure.
- `1:36.40–1:41.17` The sender, the beneficiary and the bank code all point away from the official record.
- `1:43.20–1:46.73` The payment is held, and the sandbox payment plan is blocked.
- `1:48.20–1:54.58` The contact comes from the registry, not from the suspicious message. The email is drafted, never sent.
- `1:55.60–1:59.74` Even a direct request to create a plan is refused by the server.

## 2:00 Scenario B (real app)

- `2:01.00–2:05.24` Budi paid tuition through a so-called bank agent. He checks three slips.
- `2:07.40–2:11.76` The bank feed and the university ledger here are synthetic sandbox data.
- `2:13.00–2:15.45` One slip matches the institution ledger.
- `2:19.40–2:24.28` One has no bank transfer and no university record. It stays unconfirmed.
- `2:27.00–2:30.33` One sent money to a personal account. That is a conflict.
- `2:34.20–2:36.13` A slip is not proof of settlement.

## 2:42 Scenario C (real app)

- `2:48.00–2:51.02` Citra's request matches the synthetic registry.
- `2:52.00–2:55.25` That is a record comparison, not a bank confirmation.
- `2:57.60–3:04.31` She compares two illustrative quotes. CEKBAO computes the all-in cost with exact decimal arithmetic.
- `3:06.00–3:08.31` She approves one sandbox plan, once.
- `3:13.00–3:15.76` The plan is not executed. No money moves.

## 3:24 Security (real responses)

- `3:24.60–3:27.10` Access control is enforced on the server.
- `3:28.00–3:36.45` Without a session, the request is rejected. A student cannot open another student's case. An office reviewer cannot approve a payment.
- `3:37.20–3:42.74` Instructions hidden in a message cannot override the decision. The payment stays on hold.
- `3:43.09–3:47.11` The optional language model was tested only with a mock provider.

## 3:46 Evidence and limits

- `3:47.46–3:55.28` We re-ran the repository tests today. One hundred seventeen passed, and eighteen of eighteen sandbox assertions passed.
- `3:55.63–4:02.34` These are team-authored synthetic cases, not an independent accuracy study. Nothing here connects to a bank.

## 4:04 Close

- `4:04.00–4:11.12` CEKBAO, by HMIF, Institut Teknologi Bandung. Check the request. Use the official route.

Total: 37 lines, 446 words, narration ends at 4:11.12.

# CEKBAO demo storyboard (video NOT DONE)

Status: **NOT DONE.** The video was not recorded in this environment. A storyboard is not video evidence. Record it yourself and save it as `evidence/cekbao_demo.mp4` (or upload it where the organizer asks).

Target length: 4:30, maximum 5:00. Language: English. Record only the browser window (macOS: Shift-Command-5, "Record Selected Portion").

## Before recording

```bash
rm -f data/demo.sqlite3 data/demo.sqlite3-wal data/demo.sqlite3-shm
```

```bash
CEKBAO_DB_PATH=data/demo.sqlite3 .venv/bin/python -m uvicorn app.main:get_app --factory --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765 in a clean browser window at about 1280 px wide. Close other tabs. Do not show personal data.

## Shots

| Time | Screen | Action | Say (short) |
|---|---|---|---|
| 0:00 to 0:20 | Sign-in page | Show the header badge "Demo mode · no AI call" and the sandbox notice | "CEKBAO checks a tuition payment request before you pay. Everything here is synthetic. No money moves." |
| 0:20 to 0:35 | Persona cards | Select Ayu, type `demo-ayu-2026`, sign in | "Ayu is going to a US university." |
| 0:35 to 1:30 | Check a request | Click sample "Urgent deposit e-mail". Click "Check before I pay". Show the red verdict | "Seven details do not match the official procedure. The sender is a look-alike, the payee and the Hong Kong SWIFT are not the university's, and the message threatens her visa." |
| 1:30 to 2:00 | What to do now | Show the registry contact. Click "Show the e-mail". Click "Copy e-mail" | "The contact comes from the reviewed registry, never from the message. CEKBAO does not send the e-mail." |
| 2:00 to 2:15 | Plan locked | Scroll to the lock panel | "A payment plan is impossible for this request." |
| 2:15 to 2:35 | Hidden instructions | Click sample "Hidden instructions", check | "This e-mail matches the record but hides instructions for software. CEKBAO treats them as data and holds the payment." |
| 2:35 to 3:30 | Budi, slips | Sign out. Sign in as Budi (`demo-budi-2026`). Tab "Did my payment arrive?". Sample "Bank-agent offer + 3 slips". Check | "One of three payments is confirmed by the university record. One slip has no record. One went to a personal account. A slip is not proof." |
| 3:30 to 4:20 | Citra, approved channel | Sign out. Sign in as Citra (`demo-citra-2026`). Sample "Official invoice e-mail". Check. Compare total cost. Prepare a sandbox plan. Approve | "This request matches. The quotes are illustrative. Provider B costs 61,125 rupiah less. The plan is approved once and not executed." |
| 4:20 to 4:40 | Technical record | Open "Technical record", click "Evidence HTML" | "Every step is in a hash-chained audit log. The evidence file cites its sources." |
| 4:40 to 4:55 | Terminal (optional) | Show `pytest` summary "117 passed" | "117 automated tests, including adversarial ones, pass." |

## After recording

- Check that no personal data, notifications or other windows appear.
- Note the file name, duration and date in `docs/EXECUTION_EVIDENCE.md` section 1 and change "DEMO VIDEO" from NOT DONE to DONE.

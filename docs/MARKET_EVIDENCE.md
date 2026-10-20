# CEKBAO market and problem evidence

Evidence cutoff: 20 October 2026. Each source below was opened and read on that date unless the row says otherwise.

Labels: **[A] target-context evidence**, **[B] external or transferable evidence**, **[C] unverified hypothesis**. A count of people exposed to a risk is not a count of victims or customers.

## 1. Problem and job to be done

Job to be done (team framing, to validate): "Before I send an overseas tuition or deposit payment, help me find out whether the request follows a verified official process, understand the total cost, and prepare the next action if something is suspicious."

Failure mechanism the product targets: a student receives a payment instruction or a payment slip that looks official. Nothing in the student's normal flow compares it with the institution's own procedure or record before money moves.

## 2. Evidence ledger

| # | Source (date) | What it shows | What it does NOT show | Label |
|---|---|---|---|---|
| 1 | Zhang, Arunasalam, Datta, Celik. *International Students and Scams: At Risk Abroad*. Accepted to IEEE S&P 2026. arXiv 2510.18715 | 48 survey participants and 9 interviews, international students in the US. Reports impersonation scams (including government impersonation), difficulty recognizing scams, uncertainty about trustworthy resources and barriers to reporting | Incidence rates. Effect of any tool. Tuition-payment specifics | [A] qualitative |
| 2 | Singapore Police Force advisory, 19 March 2026 | At least 20 reported cases and at least S$31,000 in losses since March 2026. E-mails impersonate educational institutions, from taken-over student accounts or look-alike domains. They demand urgent payment of school or tuition fees by bank transfer and threaten action from a "litigation department" | The page does not say the victims were students or international students | [A] mechanism, [B] population |
| 3 | Universitas Muhammadiyah Tapanuli Selatan (UMTS), Padangsidimpuan. detikSumut 23 Feb 2025, Kompas.com 24 Feb 2025 | About 273 students used an unofficial "bayar UKT tanpa ribet" (pay tuition without hassle) service. Reported discrepancy about IDR 1.2 billion. The campus found 28 payment slips but only 6 matching bank transactions. Students received forged deposit slips | National rate. That every slip was forged. A cross-border case (victims were domestic) | [B] mechanism (domestic analog) |
| 3a | Same case: sources disagree | Kompas says one perpetrator posed as a bank employee. detikSumut says the two did not present themselves as bank staff and offered to deposit at the university's bank | We report both versions and do not pick one | Disagreement noted |
| 3b | detikSumut, 26 Jan 2026 (court outcome) | Sentences of 3 years and 2 years 4 months at first instance (one reduced to 2 years on appeal). Mentions IDR 1.2 billion collected (campus figure) and IDR 231,562,500 loss in the university audit | The article does not reconcile the two loss figures. Do not merge them | [B] |
| 4 | FBI alert, 13 May 2025: impersonation scheme targeting Middle Eastern students in the United States | Per the team research brief: scammers impersonate immigration and university authorities and demand payments from students | **Not re-verified in this session.** fbi.gov blocked automated access. Re-check before citing on a slide | [A] mechanism, pending re-check |
| 5 | Flywire, "How international students can avoid tuition payment scams" (updated 21 Nov 2025) | Warns about unauthorized parties that claim to collect tuition, discount or pay-on-your-behalf offers, and government impersonation threatening visa revocation. Advises students to confirm the processor through the university "how to pay" page | Prevalence | [B] |
| 6 | Open Doors 2025 (IIE, published 17 Nov 2025) and Fast Facts | 1,177,766 international students in US higher education in 2024/25. 8,104 from Indonesia. 51.5% list personal and family funds as the primary source of funding | Victims, payment-request volume or customers | [B] exposure population |
| 7 | World Bank Remittance Prices Worldwide (homepage, last update 18 Aug 2025) | Global average cost of sending remittances: 6.36% of the amount sent | Tuition payments or live quotes. Do not apply it to CEKBAO quotes | [B] context |

Rules for using these numbers:

- Do not multiply the 273-student case or the S$31,000 figure into a rate, a market size or revenue.
- Do not call the Singapore victims international students.
- Say clearly that the UMTS victims were domestic. The case supports the failure mechanism (slip without institution record), not cross-border prevalence.

## 3. Existing solutions (documented functions only)

Wording rule: "The public page reviewed did not establish X" means we did not find X on that page. It does not mean the product lacks X.

| Dimension | CEKBAO (this prototype) | Flywire (education payments page) | ScamShield (app check page) | University payment portal | Do nothing / manual check |
|---|---|---|---|---|---|
| Primary job | Check a request and slips against the institution procedure before paying | Move the payment: pay in local currency (140+ currencies), tracking, institution reconciliation | Check suspicious numbers, messages, links. AI-powered classifier. Reports to authorities | Show the student's invoice and accepted methods | Student reads the e-mail and decides |
| Screens a message or link | Yes, rules plus optional LLM extraction | Not established on the page reviewed | Yes | No | Student judgement |
| Compares a request with a specific institution's documented procedure | Yes (curated registry, synthetic today) | Not established on the page reviewed. Its scam page tells students to check the university "how to pay" page | Not established on the page reviewed | It is the procedure, but the student must find it and compare manually | Manual |
| Checks whether a slip reached the institution | Yes, against an institution ledger (synthetic) | Reconciliation for institutions | Not established | Shows posted payments to the student | Ask the office |
| FX and fee comparison | User-provided quotes, Decimal, intermediary fees disclosed | Wholesale rates, costs shown up front (vendor claim) | No | No | Manual |
| Moves money | **No** | Yes | No | Yes | n/a |
| Human-controlled next action and draft to the official office | Yes | Not established | Report flow | Contact page | Manual |
| Auditable evidence export | Yes (hash-chained JSON/HTML) | Not established | Not established | Receipts | No |

Positioning: CEKBAO complements approved payment rails and scam screeners. It does not replace or impersonate them. A real deployment should point students to the institution's approved rail, which can be Flywire or a portal.

## 4. Differentiation hypothesis [C]

"A pre-payment check that compares the request with the specific institution's documented procedure, reconciles slip evidence with an institution record and ends in a student-confirmed safe action adds value beyond generic scam classification."

Not proven. Our synthetic evaluation (see `docs/EXECUTION_EVIDENCE.md`) only shows that the rules behave as designed: on 10 synthetic messages a keyword baseline cleared 6 of 8 unsafe messages and accepted 4 slips without an institution record, while CEKBAO held 8 of 8 and accepted 0. The same team wrote fixtures and rules, so this is not evidence of real-world performance.

What would falsify it:

- Students do not use a pre-payment check, or ignore a hold.
- University offices cannot or will not keep a procedure record or answer ledger checks.
- A generic screener already catches the same cases with the same next-step quality.

## 5. Users, buyer and channels

| Role | Who | Status |
|---|---|---|
| End user | International and domestic students paying tuition or deposits | [C] needs interviews |
| Economic buyer | University international-student office or finance office | [C] hypothesis. No contract, pilot, payment or willingness-to-pay evidence |
| Data owner | University finance office (procedure, ledger confirmation) | [C] |
| Channel options | Pre-departure orientation, international-student office onboarding, student associations | [C] |

## 6. Unvalidated claims (do not present as facts)

- Market size, TAM/SAM/SOM, revenue, pricing, willingness to pay.
- Reduction in fraud losses or in student time.
- Accuracy on real messages.
- Any partnership or endorsement by a university, Flywire, ScamShield or the competition organizer.

## 7. Validation plan (next 8 weeks, proposal)

| Hypothesis | Test | Metric | Success | Failure |
|---|---|---|---|---|
| Students want a pre-payment check | 10 to 15 interviews with recently paying international students (Indonesian students first) | Share who can name a recent suspicious request and how they checked it | At least half describe a manual check they found hard | Most never see such requests |
| Offices will keep a procedure record | 3 conversations with international or finance offices | Willing to publish or confirm a payment-procedure record | At least 1 agrees to a pilot record | None will maintain it |
| The verdict changes behavior | Usability test with the prototype and synthetic messages | Correct action rate, false-clearance rate, time to decision | Higher correct action rate than reading the e-mail alone | No difference |

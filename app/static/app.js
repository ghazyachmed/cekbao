"use strict";
// CEKBAO UI. Verdict first, then next steps, then details. All server data is
// rendered with textContent (no innerHTML with data), so the strict CSP holds.

const S = { csrf: null, user: null, samples: null, registry: null };

const PERSONAS = [
  { id: "stu_ayu", name: "Ayu", desc: "Student going to a US university. Got an urgent deposit e-mail." },
  { id: "stu_citra", name: "Citra", desc: "Student going to a US university. Got an invoice e-mail." },
  { id: "stu_budi", name: "Budi", desc: "Student in Indonesia. Paid UKT through a 'bank agent'." },
  { id: "officer_nbu", name: "Finance office", desc: "University reviewer. Sees escalated requests." },
];
const SAMPLE_LABELS = {
  A_SUSPICIOUS_INTL: "Urgent deposit e-mail", C_LEGITIMATE: "Official invoice e-mail", D1_UNKNOWN_INSTITUTION: "Unknown college",
  D2_PROMPT_INJECTION: "Hidden instructions", D3_MANIPULATED_LINK: "Fake portal link", D4_MISSING_PAYEE: "Missing payee",
};
const CHECK_LABELS = {
  INSTITUTION: "University on record", SENDER_DOMAIN: "Sender address", LINK_DOMAIN: "Link in the message",
  BENEFICIARY_NAME: "Payee name", BENEFICIARY_ACCOUNT: "Payee account", SWIFT_BIC: "Receiving bank (SWIFT)",
  PAYMENT_METHOD: "Payment method", AMOUNT: "Amount",
};
const CHECK_GROUPS = [
  ["Who sent it", ["INSTITUTION", "SENDER_DOMAIN", "LINK_DOMAIN"], "who"],
  ["Where the money goes", ["BENEFICIARY_NAME", "BENEFICIARY_ACCOUNT", "SWIFT_BIC"], "money"],
  ["How you are asked to pay", ["PAYMENT_METHOD", "AMOUNT"], "method"],
  ["Official payment rules", ["POLICY"], "rules"],
];
const STATUS_TEXT = { MATCHED_SOURCE: "Matches record", CONFLICT: "Does not match", NOT_VERIFIABLE: "Cannot be checked" };
const SIGNAL_TEXT = {
  DEADLINE_PRESSURE: "Short deadline", DISCOUNT_OFFER: "Discount offer", EASY_PAYMENT_OFFER: "Offers to pay for you",
  BANK_AGENT_IMPERSONATION: "Claims to be a bank agent", THREAT_OR_AUTHORITY_PRESSURE: "Threat (visa, arrest)",
  AUTHORITY_CLAIM: "Mentions authorities", SECRET_REQUEST: "Asks for password or OTP",
  OFF_CHANNEL_CONTACT: "Chat app or phone contact", PROMPT_INJECTION: "Hidden instructions to software",
  HIDDEN_CHARACTERS: "Hidden characters", UNGROUNDED_MODEL_OUTPUT: "AI value discarded",
  DUPLICATE_INTERMEDIARY_REQUEST: "Same contact asked before",
};
const STATE_TEXT = { draft: "Draft", needs_review: "Waiting for you", approved: "Plan approved", blocked: "On hold" };
const NEXT_ACTION_TEXT = {
  REQUIRES_INSTITUTION_CHECK: "Ask the finance office to check this payment.",
  CONTACT_BANK_AND_INSTITUTION: "Call your bank's fraud line now and tell the finance office.",
  KEEP_INSTITUTION_RECEIPT: "Keep the university receipt for your records.",
};
const SLIP_TEXT = { CONFIRMED_BY_INSTITUTION_LEDGER: ["Confirmed by university", "ok"], PAYMENT_UNCONFIRMED: ["Not confirmed", "warn"], CONFLICT: ["Does not match", "bad"] };

const FIELD_TEXT = {
  slip_id: "slip reference", amount: "amount", transfer_date: "transfer date", destination_account: "account number (digits only)",
  destination_name: "account name", payer_reference: "student reference", message: "message", fx_rate: "rate",
  flat_fee: "flat fee", percent_fee: "% fee", expected_recipient_amount: "amount received", quote_date: "quote date",
  provider_label: "provider name", institution_id: "university", case_type: "request type",
};

// ------------------------------------------------------------------ helpers

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.appendChild(typeof c === "string" || typeof c === "number" ? document.createTextNode(String(c)) : c);
  }
  return node;
}
const $ = (id) => document.getElementById(id);
const money = (x) => (x === null || x === undefined || x === "" ? "-" : Number(x).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));

async function api(method, url, body, extraHeaders) {
  const headers = { ...(extraHeaders || {}) };
  if (method !== "GET" && S.csrf) headers["X-CSRF-Token"] = S.csrf;
  let payload;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  const r = await fetch(url, { method, headers, body: payload, credentials: "same-origin" });
  let data = null;
  try { data = await r.json(); } catch (_) { data = null; }
  if (!r.ok) {
    let msg = data && data.detail ? data.detail : `Request failed (HTTP ${r.status})`;
    if (data && data.errors) {
      const fields = [...new Set(data.errors.map((e) => FIELD_TEXT[e.loc[e.loc.length - 1]] || e.loc[e.loc.length - 1]))].filter((f) => !/^\d+$/.test(f));
      msg = `Please check these fields: ${fields.slice(0, 6).join(", ")}.`;
    }
    if (r.status === 401) msg = "Your session ended. Sign in again.";
    const err = new Error(msg); err.status = r.status; throw err;
  }
  return data;
}

function status(id, text, kind) { const n = $(id); n.textContent = text || ""; n.className = "msg " + (kind || ""); }
async function busy(btn, fn) { btn.disabled = true; try { await fn(); } finally { btn.disabled = false; } }
function link(url, text) { return url ? el("a", { href: url, target: "_blank", rel: "noopener noreferrer", title: url, text: text || url }) : null; }
function host(url) { try { return new URL(url).hostname; } catch (_) { return url; } }
function put(root, ...nodes) { root.append(...nodes.filter(Boolean)); }
const METHOD_TEXT = {
  institution_portal: "University portal", international_wire: "International wire", virtual_account: "Virtual account",
  domestic_transfer: "Bank transfer", card: "Card", crypto: "Crypto", gift_card: "Gift card", cash_or_agent: "Cash or agent",
  e_wallet: "E-wallet", money_transfer_operator: "Money transfer shop", personal_account: "Personal account",
};
const friendlyMethods = (s) => (s || "").split(", ").map((m) => METHOD_TEXT[m] || m).join(", ");
function panel(title, ...children) { return el("section", { class: "panel" }, title ? el("h3", { text: title }) : null, ...children); }

// ------------------------------------------------------------------ sign in

let chosen = "stu_ayu";
function renderPersonas() {
  const grid = $("personas");
  grid.replaceChildren(...PERSONAS.map((p) => el("button", {
    class: "persona", type: "button", role: "radio", "aria-checked": String(p.id === chosen),
    onclick: () => { chosen = p.id; renderPersonas(); $("login-code").focus(); },
  }, el("div", { class: "avatar", text: p.name[0] }), el("div", { class: "name", text: p.name }), el("div", { class: "desc", text: p.desc }))));
}

async function signIn() {
  status("login-msg", "Signing in...");
  try { afterLogin(await api("POST", "/api/session/login", { user_id: chosen, access_code: $("login-code").value })); }
  catch (e) { status("login-msg", e.message, "err"); }
}

async function afterLogin(r) {
  S.csrf = r.csrf_token; S.user = r.user;
  $("login-view").classList.add("hidden");
  $("app-view").classList.remove("hidden");
  $("logout").classList.remove("hidden");
  $("who").classList.remove("hidden");
  $("who").textContent = r.user.display_name;
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("hidden", t.dataset.roles !== r.user.role));
  await loadReference();
  showTab(r.user.role === "office_reviewer" ? "office" : "request");
}

async function signOut() { try { await api("POST", "/api/session/logout"); } catch (_) { /* expired */ } location.reload(); }
async function restore() { try { await afterLogin(await api("GET", "/api/session/me")); } catch (_) { /* signed out */ } }

function showTab(name) {
  document.querySelectorAll(".tabpane").forEach((p) => p.classList.toggle("hidden", p.id !== `tab-${name}`));
  document.querySelectorAll(".tab").forEach((t) => { const on = t.dataset.tab === name; t.classList.toggle("active", on); t.setAttribute("aria-selected", String(on)); });
  if (name === "cases") loadCases();
  if (name === "office") loadOffice();
}

// ------------------------------------------------------------------ reference data

async function loadReference() {
  if (S.samples) return;
  [S.samples, S.registry] = await Promise.all([api("GET", "/api/samples"), api("GET", "/api/registry")]);
  $("req-samples").replaceChildren(...S.samples.tuition_requests.map((s) => el("button", {
    class: "chip", type: "button", title: s.title, onclick: (ev) => {
      document.querySelectorAll("#req-samples .chip").forEach((c) => c.classList.remove("active"));
      ev.currentTarget.classList.add("active");
      $("req-inst").value = s.claimed_institution || ""; $("req-msg").value = s.message;
    },
  }, SAMPLE_LABELS[s.id] || s.title)));
  $("inst-list").replaceChildren(...S.registry.institutions.map((i) => el("option", { value: i.display_name.replace(" (SYNTHETIC)", "") })));
  $("slip-inst").replaceChildren(...S.registry.institutions.map((i) => el("option", { value: i.institution_id, text: i.display_name })));
  if (S.user && S.user.institution_id) $("slip-inst").value = S.user.institution_id;
  if (!$("slip-rows").children.length) addSlipRow();
}

// ------------------------------------------------------------------ check a request

async function checkRequest(ev) {
  const root = $("req-result");
  if (!$("req-msg").value.trim()) { status("req-status", "Paste a message first, or try a sample.", "err"); return; }
  await busy(ev.currentTarget, async () => {
    root.replaceChildren();
    status("req-status", "Checking against the official record...");
    try {
      const draft = await api("POST", "/api/cases", { case_type: "tuition_request", claimed_institution: $("req-inst").value.trim() || null, message: $("req-msg").value });
      const view = await api("POST", `/api/cases/${draft.case_id}/analyze`);
      status("req-status", "");
      renderCase(root, view);
      root.firstChild.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) { status("req-status", e.message, "err"); }
  });
}

function renderCase(root, v) {
  root.replaceChildren();
  if (!v.analysis) { root.append(panel(null, el("p", { text: "This case has not been checked yet." }))); return; }
  if (v.case_type === "payment_evidence") return renderSlipCase(root, v);
  const a = v.analysis, pol = a.policy;
  const allowed = pol.decision === "PLAN_ALLOWED_AFTER_STUDENT_CONFIRMATION";
  put(root, verdictRequest(v), nextSteps(v, allowed), checksPanel(pol.findings));
  if (pol.risk_signals.length) put(root, warningsPanel(pol.risk_signals));
  if (S.user.role === "student") put(root, allowed ? costsPanel(v, root) : lockedPanel(), allowed ? planPanel(v, root) : null);
  put(root, recordsPanel(v));
}

function verdictRequest(v) {
  const a = v.analysis, pol = a.policy;
  const inst = a.institution ? a.institution.display_name : null;
  const conflicts = pol.findings.filter((f) => f.status === "CONFLICT").length;
  const missing = pol.findings.filter((f) => f.required && f.status === "NOT_VERIFIABLE").length;
  const high = pol.risk_signals.filter((s) => s.severity === "high");
  let cls = "hold", icon = "!", title, text;
  if (pol.decision === "PLAN_ALLOWED_AFTER_STUDENT_CONFIRMATION") {
    cls = "allow"; icon = "✓";
    title = "This request matches the official procedure on record.";
    text = "This is a record comparison, not a bank check. Pay only inside the official portal after you confirm the amount on your invoice.";
  } else if (pol.overall_status === "CONFLICT") {
    title = "Stop. Do not pay through this request.";
    text = `${conflicts} detail${conflicts === 1 ? "" : "s"} do not match the official payment procedure of ${inst}.`;
  } else if (pol.overall_status === "NOT_VERIFIABLE") {
    title = "Hold. This request cannot be checked.";
    text = !inst ? "This university is not in CEKBAO's reviewed list. Do not pay until the university confirms the request through a contact you find yourself."
      : `${missing} required detail${missing === 1 ? " is" : "s are"} missing. Ask the finance office before you pay.`;
  } else {
    title = "Hold. The message contains warning signs.";
    text = `The details match the record, but the message shows: ${high.map((s) => SIGNAL_TEXT[s.signal_id] || s.signal_id).join(", ")}.`;
  }
  return el("section", { class: `verdict ${cls}`, role: "status" },
    el("div", { class: "icon", "aria-hidden": "true", text: icon }),
    el("div", {}, el("h2", { text: title }), el("p", { text }),
      el("div", { class: "codes" }, [pol.overall_status, pol.decision, v.case_id].map((c) => el("span", { class: "code-chip", text: c })))));
}

function contactBlock(esc, inst) {
  const draft = esc && esc.draft_email;
  if (!inst) return el("p", { class: "muted", text: "No official contact is on record for this university. Find it yourself in your admission letter or on the official website. Do not use contacts from the message." });
  const c = inst.official_contact;
  return el("dl", { class: "contact" },
    el("dt", { text: "Office" }), el("dd", { text: c.office }),
    el("dt", { text: "E-mail" }), el("dd", { text: c.email }),
    c.phone ? el("dt", { text: "Phone" }) : null, c.phone ? el("dd", { text: c.phone }) : null,
    el("dt", { text: "Source" }), el("dd", {}, link(c.contact_page_url, host(c.contact_page_url)), inst.synthetic ? " (synthetic registry)" : ""));
}

function nextSteps(v, allowed) {
  const a = v.analysis, esc = a.escalation;
  if (allowed) {
    return panel("What to do now",
      el("ol", { class: "steps" }, ["Optional: compare transfer costs below.", "Review the sandbox payment plan and approve it if it is right.",
        "Pay inside the official portal yourself. Type the address. Do not click links.", "Keep the university receipt. A bank slip alone is not proof."].map((t) => el("li", { text: t }))));
  }
  const draft = esc.draft_email;
  const box = el("div", { class: "draft hidden" });
  if (draft) {
    const ta = el("textarea", { rows: 12, readonly: true }); ta.value = `To: ${draft.to}\nSubject: ${draft.subject}\n\n${draft.body}`;
    box.append(ta, el("p", { class: "muted small", text: draft.note }));
  }
  const copyBtn = draft ? el("button", { class: "btn primary", type: "button", onclick: async (e) => {
    try { await navigator.clipboard.writeText(`${draft.subject}\n\n${draft.body}`); e.currentTarget.textContent = "Copied ✓"; } catch (_) { box.classList.remove("hidden"); }
  } }, "Copy e-mail to the finance office") : null;
  return panel("What to do now",
    el("ol", { class: "steps" }, esc.checklist.filter((t) => !t.startsWith("Contact ") && !t.startsWith("The institution is not in the registry")).slice(0, 4).map((t) => el("li", { text: t }))),
    el("h3", { class: "h-sm", text: "Official contact (from the registry, not from the message)" }),
    contactBlock(esc, a.institution),
    el("div", { class: "actions" }, copyBtn,
      draft ? el("button", { class: "btn secondary", type: "button", onclick: () => box.classList.toggle("hidden") }, "Show the e-mail") : null,
      el("a", { class: "btn secondary", href: `/api/cases/${v.case_id}/evidence.html` }, "Download evidence for the office")),
    box);
}

function markOf(status, required) {
  if (status === "MATCHED_SOURCE") return ["ok", "✓"];
  if (status === "CONFLICT") return ["bad", "✕"];
  return [required ? "warn" : "warn", "?"];
}

function checkRow(f) {
  const policy = f.check_id.startsWith("POLICY_");
  const [cls, sym] = markOf(f.status, f.required);
  const what = policy ? "Official rule" : (CHECK_LABELS[f.check_id] || f.label);
  const observed = f.check_id === "PAYMENT_METHOD" ? friendlyMethods(f.observed) : f.observed;
  const showOfficial = f.status === "CONFLICT" && ["SENDER_DOMAIN", "LINK_DOMAIN", "BENEFICIARY_NAME", "SWIFT_BIC", "PAYMENT_METHOD"].includes(f.check_id) && f.expected;
  const official = f.check_id === "PAYMENT_METHOD" ? friendlyMethods(f.expected) : f.expected;
  const line = policy ? f.expected : (observed || "Not found in the message");
  const tag = policy ? "Message breaks this rule" : (f.required ? STATUS_TEXT[f.status] : "Check your invoice");
  return el("details", { class: "check" },
    el("summary", {}, el("span", { class: `mark ${cls}`, "aria-hidden": "true", text: sym }),
      el("span", {}, el("div", { class: "what", text: what }), el("div", { class: "line", text: line }),
        showOfficial ? el("div", { class: "line official", text: `Official: ${official}` }) : null),
      el("span", { class: `tag ${cls}`, text: tag })),
    el("div", { class: "more" }, el("dl", {},
      el("dt", { text: policy ? "In the message" : "Found" }), el("dd", { text: f.observed || "(nothing)" }),
      el("dt", { text: "Official record" }), el("dd", { text: f.expected || "(no record)" }),
      el("dt", { text: "Why" }), el("dd", { text: f.explanation }),
      el("dt", { text: "Source" }), el("dd", {}, f.source_url ? link(f.source_url, host(f.source_url)) : "none", f.source_url && f.source_synthetic ? " (synthetic)" : ""))));
}

function checksPanel(findings) {
  const rows = findings.filter((f) => f.check_id !== "SLIP");
  if (!rows.length) return null;
  const p = panel("What we checked", el("p", { class: "muted", text: "Tap a row to see the official record and the source." }));
  for (const [title, ids, icon] of CHECK_GROUPS) {
    const items = rows.filter((f) => ids.some((id) => f.check_id === id || (id === "POLICY" && f.check_id.startsWith("POLICY_"))));
    if (items.length) p.append(el("div", { class: "group-title" }, el("img", { src: `/static/img/${icon}.svg`, alt: "", width: 24, height: 24 }), title), ...items.map(checkRow));
  }
  return p;
}

function warningsPanel(signals) {
  return panel("Warning signs in the message",
    el("div", { class: "signals" }, signals.map((s) => el("span", { class: `signal ${s.severity}`, title: s.explanation, text: SIGNAL_TEXT[s.signal_id] || s.signal_id }))),
    el("details", { class: "sub-details" }, el("summary", { text: "Why these are warning signs" }),
      el("ul", { class: "quotes-list" }, signals.map((s) => el("li", {}, el("b", { text: `${SIGNAL_TEXT[s.signal_id] || s.signal_id}: ` }), `"${s.evidence}". ${s.explanation}`,
        s.source_url ? el("span", {}, " Context: ", link(s.source_url, host(s.source_url))) : null)))));
}

function lockedPanel() {
  return el("section", { class: "panel locked" }, el("span", { class: "lock", "aria-hidden": "true", text: "🔒" }),
    el("div", { text: "Cost comparison and the payment plan stay locked because this request did not pass the check. CEKBAO does not let you create a plan for it." }));
}

// ------------------------------------------------------------------ costs and plan

function quoteCard(q, i) {
  const f = (name, label, val, type) => el("label", {}, label, el("input", { "data-f": name, value: val || "", type: type || "text", inputmode: type === "date" ? null : "decimal" }));
  return el("div", { class: "quote-card", "data-q": i },
    f("provider_label", "Provider name", q.provider_label),
    el("div", { class: "two" }, f("source_currency", "You pay in", q.source_currency || "IDR"), f("target_currency", "University receives", q.target_currency || "USD")),
    f("fx_rate", "Rate (you pay per 1 unit received)", q.fx_rate),
    el("div", { class: "two" }, f("flat_fee", "Flat fee", q.flat_fee), f("percent_fee", "% fee", q.percent_fee)),
    el("div", { class: "two" }, f("expected_recipient_amount", "University receives", q.expected_recipient_amount), f("quote_date", "Quote date", q.quote_date, "date")),
    f("intermediary_fee_target", "Intermediary fee (blank = unknown)", q.intermediary_fee_target));
}

function costsPanel(v, root) {
  const s = S.samples.quotes;
  const blank = { source_currency: "IDR", target_currency: "USD", quote_date: new Date().toISOString().slice(0, 10) };
  const cards = [quoteCard(s ? s.quotes[0] : blank, 0), quoteCard(s ? s.quotes[1] : blank, 1)];
  const ref = el("input", { value: s ? s.reference_rate.fx_rate : "", inputmode: "decimal" });
  const refDate = el("input", { value: s ? s.reference_rate.as_of : "", type: "date" });
  const msg = el("p", { class: "msg" });
  const p = panel("Compare transfer costs (optional)",
    el("p", { class: "muted", text: "Enter two quotes you received. CEKBAO does not fetch live rates. The sample numbers are illustrative." }),
    el("div", { class: "quote-grid" }, cards),
    el("details", { class: "sub-details" }, el("summary", { text: "Add a reference rate (optional)" }),
      el("div", { class: "quote-grid" }, el("label", { class: "field" }, "Reference rate", ref), el("label", { class: "field" }, "As of", refDate))),
    el("div", { class: "actions" }, el("button", { class: "btn primary", type: "button", onclick: (e) => busy(e.currentTarget, async () => {
      const quotes = cards.map((c) => {
        const q = {}; c.querySelectorAll("input").forEach((i) => { q[i.dataset.f] = i.value.trim(); });
        const inter = q.intermediary_fee_target; delete q.intermediary_fee_target;
        q.intermediary_fee_known = inter !== ""; if (inter !== "") q.intermediary_fee_target = inter;
        return q;
      });
      const body = { quotes };
      if (ref.value.trim()) body.reference_rate = { fx_rate: ref.value.trim(), as_of: refDate.value, source_label: "Student-provided reference rate" };
      try { renderCase(root, await api("POST", `/api/cases/${v.case_id}/quotes`, body)); }
      catch (err) { msg.textContent = err.message; msg.className = "msg err"; }
    }) }, "Compare total cost")), msg);
  if (v.quotes) p.append(quoteResults(v.quotes));
  return p;
}

function quoteResults(qc) {
  const best = qc.lowest_cost_covering_invoice;
  return el("div", {},
    el("div", { class: "result-grid" }, qc.results.map((q) => el("div", { class: `result-card ${q.provider_label === best ? "best" : ""}` },
      q.provider_label === best ? el("span", { class: "badge", text: "Lowest total cost" }) : null,
      el("div", { class: "muted small", text: `${q.provider_label} · quote of ${q.quote_date}${q.stale ? " (old)" : ""}` }),
      el("div", { class: "total", text: `${q.source_currency} ${money(q.total_source_cost)}` }),
      el("div", { class: "muted small", text: `for ${q.target_currency} ${money(q.expected_recipient_amount)} received` }),
      el("dl", {},
        el("dt", { text: "Rate" }), el("dd", { text: money(q.fx_rate) }),
        el("dt", { text: "Fees" }), el("dd", { text: money(Number(q.flat_fee_source) + Number(q.percent_fee_source)) }),
        el("dt", { text: "All-in rate" }), el("dd", { text: money(q.all_in_rate) }),
        q.markup_vs_reference_pct !== null ? el("dt", { text: "Above reference" }) : null,
        q.markup_vs_reference_pct !== null ? el("dd", { text: `${q.markup_vs_reference_pct}%` }) : null,
        el("dt", { text: "Intermediary fees" }), el("dd", { text: q.intermediary_fees === "UNKNOWN" ? "Unknown" : q.intermediary_fees.replace("KNOWN: ", "") }),
        Number(q.invoice_shortfall_target) > 0 ? el("dt", { text: "Short of invoice" }) : null,
        Number(q.invoice_shortfall_target) > 0 ? el("dd", { text: money(q.invoice_shortfall_target) }) : null)))),
    qc.cost_difference_source ? el("p", {}, "Choosing ", el("b", { text: best }), ` saves ${qc.results[0].source_currency} ${money(qc.cost_difference_source)}.`) : null,
    qc.warnings.length ? el("details", { class: "sub-details" }, el("summary", { text: `${qc.warnings.length} note(s) about these quotes` }), el("ul", { class: "quotes-list" }, qc.warnings.map((w) => el("li", { text: w })))) : null);
}

function planPanel(v, root) {
  const cur = v.plans[v.plans.length - 1];
  const msg = el("p", { class: "msg" });
  const quoteOptions = v.quotes ? v.quotes.results.filter((q) => q.covers_invoice) : [];
  const sel = el("select", {}, el("option", { value: "", text: "No quote" }), quoteOptions.map((q) => el("option", { value: q.provider_label, text: q.provider_label })));
  if (v.quotes && v.quotes.lowest_cost_covering_invoice) sel.value = v.quotes.lowest_cost_covering_invoice;
  const propose = (label) => el("button", { class: "btn primary", type: "button", onclick: (e) => busy(e.currentTarget, async () => {
    try { renderCase(root, await api("POST", `/api/cases/${v.case_id}/plan/propose`, { selected_quote_label: sel.value || null })); }
    catch (err) { msg.textContent = err.message; msg.className = "msg err"; }
  }) }, label);
  const chooser = el("div", { class: "field-row" }, el("label", { class: "field grow" }, "Use quote", sel), propose(cur ? "Prepare a new plan" : "Prepare a sandbox plan"));

  const p = panel("Sandbox payment plan");
  if (!cur || cur.status === "denied") {
    p.append(el("p", { class: "muted", text: cur ? "You declined the last plan. Nothing was saved as approved." : "A plan only records how you intend to pay. CEKBAO never sends money." }), chooser, msg);
    return p;
  }
  const plan = cur.plan, ch = plan.channel;
  const approved = cur.status === "approved";
  const box = el("div", { class: `plan ${approved ? "plan-approved" : ""}` },
    el("div", { class: "status", text: approved ? "✓ Approved by you · not executed" : `Plan ${cur.revision} · waiting for your decision` }),
    el("p", {}, "Pay ", el("b", { text: `${plan.invoice.currency || ""} ${money(plan.invoice.amount)}` }), " to ", el("b", { text: ch.beneficiary_name }),
      ch.payment_host ? ` inside ${ch.payment_host}` : (ch.account_masked ? ` (account ${ch.account_masked}, SWIFT ${ch.swift_bic})` : ""), "."),
    plan.quote ? el("p", { class: "muted", text: `Using ${plan.quote.provider_label}: you pay about ${plan.quote.source_currency} ${money(plan.quote.total_source_cost)}.` }) : null,
    el("p", { class: "muted small", text: "Payee details come from the official registry, not from the message. The amount is as stated in the request. Confirm it on your portal invoice." }),
    el("ol", { class: "steps" }, plan.student_steps.map((t) => el("li", { text: t }))));
  p.append(box);
  if (cur.status === "proposed") {
    const idem = crypto.randomUUID();
    const body = { plan_revision: cur.revision, plan_digest: cur.digest };
    p.append(el("div", { class: "actions" },
      el("button", { class: "btn primary big", type: "button", onclick: (e) => busy(e.currentTarget, async () => {
        try { await api("POST", `/api/cases/${v.case_id}/plan/approve`, body, { "Idempotency-Key": idem }); renderCase(root, await api("GET", `/api/cases/${v.case_id}`)); }
        catch (err) { msg.textContent = err.message; msg.className = "msg err"; }
      }) }, "Approve this plan"),
      el("button", { class: "btn secondary big", type: "button", onclick: (e) => busy(e.currentTarget, async () => {
        try { renderCase(root, await api("POST", `/api/cases/${v.case_id}/plan/deny`, { ...body, reason: "Student declined" })); }
        catch (err) { msg.textContent = err.message; msg.className = "msg err"; }
      }) }, "Not now")));
  } else {
    p.append(el("details", { class: "sub-details" }, el("summary", { text: "Change the plan (needs a new approval)" }), chooser));
  }
  p.append(msg);
  return p;
}

function recordsPanel(v) {
  const a = v.analysis || {};
  return el("section", { class: "panel" }, el("details", { class: "tech" },
    el("summary", { text: "Technical record (for reviewers and judges)" }),
    a.extraction ? el("p", { class: "muted small", text: a.extraction.mode_label }) : null,
    a.registry ? el("p", { class: "muted small", text: `Registry ${a.registry.version} · sha256 ${a.registry.sha256.slice(0, 16)}... · case ${v.case_id} · state ${v.state} · audit chain valid: ${v.audit_chain_valid}` }) : null,
    el("div", { class: "actions" }, el("a", { class: "btn secondary", href: `/api/cases/${v.case_id}/evidence.json` }, "Evidence JSON"), el("a", { class: "btn secondary", href: `/api/cases/${v.case_id}/evidence.html` }, "Evidence HTML")),
    el("div", { class: "table-wrap" }, el("table", {}, el("thead", {}, el("tr", {}, ["#", "Event", "Time (UTC)", "Actor", "Event ID"].map((h) => el("th", { text: h })))),
      el("tbody", {}, v.audit_events.map((e) => el("tr", {}, [e.seq, e.event_type, e.at.replace("T", " ").slice(0, 19), e.actor_id, e.event_id].map((c) => el("td", { text: String(c) })))))))));
}

// ------------------------------------------------------------------ payment slips

function addSlipRow(s) {
  s = s || {};
  const f = (name, label, val, type, cls) => el("label", { class: cls }, label, el("input", { "data-f": name, value: val || "", type: type || "text", inputmode: name === "amount" || name === "destination_account" ? "decimal" : null }));
  const row = el("div", { class: "slip" },
    f("slip_id", "Slip reference", s.slip_id, "text", "c2"), f("amount", "Amount (IDR)", s.amount, "text", "c2"), f("transfer_date", "Transfer date", s.transfer_date, "date", "c2"),
    f("destination_account", "Sent to account", s.destination_account, "text", "c3"), f("destination_name", "Account name", s.destination_name, "text", "c3"),
    el("button", { class: "icon-btn", type: "button", title: "Remove slip", "aria-label": "Remove slip", onclick: () => row.remove() }, "×"),
    el("label", { class: "file" }, "Receipt file (optional, PDF/PNG/JPG/TXT, max 1 MB. Only its fingerprint is kept.)", el("input", { type: "file", accept: ".pdf,.png,.jpg,.jpeg,.txt", "data-file": "1" })));
  $("slip-rows").append(row);
}

function loadSlipSample() {
  const s = S.samples.payment_evidence[0];
  $("slip-inst").value = s.institution_id;
  $("slip-offer").value = s.offer_message || "";
  document.querySelector("#tab-slips details").open = true;
  $("slip-rows").replaceChildren();
  s.slips.forEach(addSlipRow);
}

async function checkSlips(ev) {
  const root = $("slip-result");
  const rows = [...document.querySelectorAll("#slip-rows .slip")];
  if (!rows.length) { status("slip-status", "Add at least one slip.", "err"); return; }
  const slips = rows.map((r) => {
    const o = { currency: "IDR", payer_reference: S.user.payer_reference };
    r.querySelectorAll("input[data-f]").forEach((i) => { o[i.dataset.f] = i.value.trim(); });
    return o;
  });
  await busy(ev.currentTarget, async () => {
    root.replaceChildren();
    try {
      status("slip-status", "Saving your slips...");
      const v = await api("POST", "/api/cases", { case_type: "payment_evidence", institution_id: $("slip-inst").value, offer_message: $("slip-offer").value.trim() || null, slips });
      for (const r of rows) {
        const file = r.querySelector("input[data-file]").files[0];
        if (!file) continue;
        const fd = new FormData(); fd.append("file", file); fd.append("slip_id", r.querySelector('input[data-f="slip_id"]').value.trim());
        status("slip-status", `Adding receipt ${file.name}...`);
        await api("POST", `/api/cases/${v.case_id}/uploads`, fd);
      }
      status("slip-status", "Comparing with your bank and the university record...");
      renderCase(root, await api("POST", `/api/cases/${v.case_id}/analyze`));
      status("slip-status", "");
      root.firstChild.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) { status("slip-status", e.message, "err"); }
  });
}

function renderSlipCase(root, v) {
  const a = v.analysis, st = a.settlement;
  const n = st.slips_submitted, ok = st.slips_confirmed_by_institution_ledger;
  const cls = ok === n ? "allow" : st.slips_in_conflict ? "hold" : "partial";
  root.append(el("section", { class: `verdict ${cls}`, role: "status" },
    el("div", { class: "icon", "aria-hidden": "true", text: ok === n ? "✓" : "!" }),
    el("div", {}, el("h2", { text: `${ok} of ${n} payment${n === 1 ? "" : "s"} confirmed by the university record.` }),
      el("p", { text: ok === n ? "Keep the university receipts." : "A slip is not proof that the university received money. Do not send more money through the intermediary. Ask the finance office about every slip that is not confirmed." }),
      el("div", { class: "codes" }, [`${st.slips_unconfirmed} PAYMENT_UNCONFIRMED`, `${st.slips_in_conflict} CONFLICT`, v.case_id].map((c) => el("span", { class: "code-chip", text: c }))))));
  const p = panel("Each slip, step by step");
  for (const r of st.results) p.append(slipCard(r));
  put(root, p);
  if (ok !== n) put(root, nextSteps(v, false));
  const offerConflicts = (a.offer_policy ? a.offer_policy.findings : []).filter((f) => f.status === "CONFLICT");
  if (a.policy.risk_signals.length) put(root, warningsPanel(a.policy.risk_signals));
  if (offerConflicts.length) put(root, checksPanel(offerConflicts));
  put(root, recordsPanel(v));
}

function slipCard(r) {
  const [label, cls] = SLIP_TEXT[r.settlement_status];
  const t = (prefix) => r.timeline.find((e) => e.source.startsWith(prefix));
  const slip = t("SLIP"), bank = t("BANK"), ledger = t("INSTITUTION"), upload = t("UPLOAD");
  const issue = (code) => r.issues.some((i) => i.code === code);
  const bankFound = bank && !bank.event.startsWith("No ");
  const bankCls = !bankFound ? "warn" : (issue("AMOUNT_MISMATCH") || issue("DESTINATION_MISMATCH") || issue("DATE_MISMATCH") || issue("WRONG_DESTINATION")) ? "bad" : "ok";
  const ledgerOk = ledger && ledger.event.startsWith("Credited");
  const box = (cls2, src, state, detail) => el("div", { class: `tl ${cls2}` }, el("div", { class: "src", text: src }), el("div", { class: "state", text: state }), el("div", { class: "muted small", text: detail || "" }));
  return el("div", { class: "slip-card" },
    el("h3", {}, el("span", { text: `Slip ${r.slip_id} · ${r.claimed_amount.replace(/([\d.]+)$/, (m) => money(m))}` }), el("span", { class: `tag ${cls}`, text: label })),
    el("div", { class: "timeline" },
      box("", "1 · The slip says", `Sent on ${slip ? slip.date : "?"}`, `to ${r.claimed_destination}`),
      box(bankCls, "2 · Your bank (sandbox)", bankFound ? (bankCls === "ok" ? "Transfer found" : "Transfer differs") : "No transfer found", bank ? bank.event : ""),
      box(ledgerOk ? "ok" : (cls === "bad" ? "bad" : "warn"), "3 · University record (sandbox)", ledgerOk ? "Received" : "Not received", ledger ? ledger.event : "Not checked")),
    r.issues.length ? el("ul", { class: "quotes-list" }, r.issues.map((i) => el("li", { text: i.detail }))) : null,
    el("p", {}, el("b", { text: "Next: " }), NEXT_ACTION_TEXT[r.next_action] || r.next_action),
    upload ? el("p", { class: "muted small", text: `Receipt attached: ${upload.event}` }) : null);
}

// ------------------------------------------------------------------ history and office

function caseItem(c, onOpen, extra) {
  return el("button", { class: "case-item", type: "button", onclick: onOpen },
    el("span", {}, el("b", { text: c.case_type === "payment_evidence" ? "Payment slips" : "Payment request" }),
      el("span", { class: "muted small", text: ` · ${c.created_at.replace("T", " ").slice(0, 16)} UTC · ${c.case_id}` }), extra || null),
    el("span", { class: `state-badge ${c.state}`, text: STATE_TEXT[c.state] || c.state }));
}

async function loadCases() {
  const root = $("cases-list");
  try {
    const r = await api("GET", "/api/cases");
    root.replaceChildren(r.cases.length ? el("div", { class: "case-list" }, r.cases.map((c) => caseItem(c, async () => {
      renderCase($("case-detail"), await api("GET", `/api/cases/${c.case_id}`)); $("case-detail").scrollIntoView({ behavior: "smooth" });
    }))) : el("div", { class: "empty" }, el("img", { src: "/static/img/empty.svg", alt: "", width: 160, height: 110 }), el("p", { class: "muted", text: "Nothing yet. Check a request or your payment slips first." })));
  } catch (e) { root.replaceChildren(el("p", { class: "msg err", text: e.message })); }
}

async function loadOffice() {
  const root = $("office-list");
  try {
    const r = await api("GET", "/api/office/escalations");
    root.replaceChildren(r.escalations.length ? el("div", { class: "case-list" }, r.escalations.map((c) => caseItem(c, async () => {
      renderCase($("office-detail"), await api("GET", `/api/cases/${c.case_id}`)); $("office-detail").scrollIntoView({ behavior: "smooth" });
    }, c.cases_with_same_intermediary > 1 ? el("span", { class: "signal high small", text: ` Same contact in ${c.cases_with_same_intermediary} cases` }) : null)))
      : el("p", { class: "muted", text: "No escalations yet." }));
  } catch (e) { root.replaceChildren(el("p", { class: "msg err", text: e.message })); }
}

// ------------------------------------------------------------------ wiring

document.addEventListener("DOMContentLoaded", () => {
  renderPersonas();
  $("login-btn").addEventListener("click", signIn);
  $("login-code").addEventListener("keydown", (e) => { if (e.key === "Enter") signIn(); });
  $("logout").addEventListener("click", signOut);
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => showTab(t.dataset.tab)));
  $("req-check").addEventListener("click", checkRequest);
  $("slip-sample").addEventListener("click", loadSlipSample);
  $("slip-add").addEventListener("click", () => addSlipRow());
  $("slip-check").addEventListener("click", checkSlips);
  restore();
});

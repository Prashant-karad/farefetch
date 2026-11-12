/* Fairfetch shared helpers (no dependencies). */
"use strict";
const FF = (() => {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const usd = u => { u = Math.round(u || 0); const s = u < 0 ? "-" : ""; u = Math.abs(u); return `${s}$${Math.floor(u / 10000)}.${String(u % 10000).padStart(4, "0")}`; };
  const cents = u => `$${(Math.round(u || 0) / 10000).toFixed(2)}`;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

  async function api(path, opts = {}) {
    const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) { const e = new Error(body?.detail?.message || body?.detail || `HTTP ${r.status}`); e.status = r.status; e.body = body; throw e; }
    return body;
  }

  /* The gateway's public address, derived from where this page is served (Codespaces or localhost). */
  function gatewayBase() {
    const { protocol, host } = location;
    if (/-8001\./.test(host)) return `${protocol}//${host.replace("-8001.", "-8000.")}`;
    if (/:8001$/.test(host)) return `${protocol}//${host.replace(/:8001$/, ":8000")}`;
    return `${protocol}//${host}`;
  }

  function ago(iso) {
    const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 50) return "just now";
    if (s < 3600) return `${Math.round(s / 60)} min ago`;
    if (s < 86400) return `${Math.round(s / 3600)} h ago`;
    return new Date(iso).toLocaleDateString();
  }

  /* Odometer: digits roll to their new value. */
  function odometer(el, text) {
    if (!el.dataset.odo) { el.classList.add("odo"); el.dataset.odo = "1"; }
    const old = $$(".d, .c", el);
    if (old.length !== text.length) {
      el.innerHTML = [...text].map(ch => /\d/.test(ch)
        ? `<span class="d"><span>${[...Array(10)].map((_, i) => `<i>${i}</i>`).join("")}</span></span>`
        : `<span class="c">${esc(ch)}</span>`).join("");
    }
    [...text].forEach((ch, i) => {
      const cell = el.children[i];
      if (/\d/.test(ch)) cell.firstElementChild.style.transform = `translateY(-${+ch}em)`;
      else cell.textContent = ch;
    });
    el.setAttribute("aria-label", text);
  }

  /* Toasts */
  function toast(title, sub = "", icon = "$", tone = "var(--green)") {
    let host = $(".toasts");
    if (!host) { host = document.createElement("div"); host.className = "toasts"; host.setAttribute("aria-live", "polite"); document.body.appendChild(host); }
    const t = document.createElement("div");
    t.className = "toast";
    t.innerHTML = `<span class="ti" style="background:${tone};color:#fff">${esc(icon)}</span><b>${esc(title)}</b>${sub ? `<small>${esc(sub)}</small>` : ""}`;
    host.appendChild(t);
    setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 320); }, 4200);
  }

  const LICENSES = {
    lic_read_24h: { name: "Read", short: "read · quote ≤ 8 words · cite · 24 h", opt: "Read · ≤ 8 words · 24 h" },
    lic_quote_24h: { name: "Quote", short: "quote ≤ 50 words · cite · 24 h", opt: "Quote · ≤ 50 words · 24 h" },
    lic_data_1h: { name: "Data", short: "data · quote ≤ 50 words · 1 h", opt: "Data · 1 h pass" },
  };
  const licShort = id => LICENSES[id]?.short || id;

  function countdown(iso) {
    const s = Math.max(0, Math.floor((new Date(iso).getTime() - Date.now()) / 1000));
    const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), sec = s % 60;
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  }
  setInterval(() => $$("[data-expires]").forEach(el => { el.textContent = countdown(el.dataset.expires); }), 1000);

  /* An access pass drawn as a ticket */
  function ticket({ title, publisher, license_id, expires_at, price, printing }) {
    return `<div class="ticket${printing ? " printing" : ""}">
      <div class="t-main"><span class="t-k">Access pass${publisher ? ` · ${esc(publisher)}` : ""}</span>
        <span class="t-title">${esc(title)}</span><span class="t-meta">${esc(licShort(license_id))}${price ? ` · ${esc(price)}` : ""}</span></div>
      <div class="t-stub"><span class="t-k">valid</span><span class="t-time" ${expires_at ? `data-expires="${esc(expires_at)}"` : ""}>${expires_at ? countdown(expires_at) : "24:00:00"}</span></div>
    </div>`;
  }

  /* A usage receipt drawn as printed paper */
  function receipt({ id, time, passed, caught, items, printing, stampLand }) {
    return `<div class="receipt${printing ? " printing" : ""}">
      <div class="r-head">Fairfetch usage receipt</div>
      <div class="r-small" style="text-align:center">${esc(id)} · ${time ? new Date(time).toLocaleString() : ""}</div>
      <div class="r-rule"></div>
      ${(items || []).map(i => `<div style="margin-bottom:6px"><div style="font-weight:600;overflow-wrap:anywhere">${esc(i.title)}</div>
        <div class="r-row"><span>used as</span><span>${esc(i.how_used)}</span></div>
        <div class="r-row"><span>longest quote</span><span>${i.longest_copied_run ?? "-"}/${i.max_quote_words ?? "-"} words</span></div>
        <div class="r-row"><span>cited</span><span>${i.cited ? "yes" : "NO"}</span></div></div>`).join("")}
      <div class="r-rule"></div>
      <div class="r-row"><span>caught &amp; fixed</span><span>${caught || 0}</span></div>
      <div class="r-row"><span>signature</span><span>ES256</span></div>
      <div style="height:34px"></div>
      <div class="stamp ${passed ? "" : "red"}${stampLand ? " land" : ""}">${passed ? (caught ? "Fixed · fair use" : "Fair use") : "Violation"}</div>
    </div>`;
  }

  /* Light / dark: follows the device until the visitor chooses; the choice is remembered. */
  const darkQuery = matchMedia("(prefers-color-scheme: dark)");
  const isDark = () => (document.documentElement.dataset.theme || (darkQuery.matches ? "dark" : "light")) === "dark";
  function paintToggle() {
    const b = document.getElementById("theme-toggle"); if (!b) return;
    b.classList.toggle("is-dark", isDark());
    b.setAttribute("aria-label", isDark() ? "Switch to light mode" : "Switch to dark mode");
  }
  function setTheme(t) {
    document.documentElement.dataset.theme = t;
    try { localStorage.setItem("ff_theme", t); } catch {}
    paintToggle();
    dispatchEvent(new Event("ff-theme"));
  }
  document.addEventListener("click", e => { if (e.target.closest("#theme-toggle")) setTheme(isDark() ? "light" : "dark"); });
  darkQuery.addEventListener("change", paintToggle);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", paintToggle); else paintToggle();

  return { $, $$, esc, usd, cents, sleep, api, setTheme, gatewayBase, ago, odometer, toast, ticket, receipt, licShort, countdown, REDUCED, LICENSES };
})();

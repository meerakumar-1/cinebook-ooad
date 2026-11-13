"use strict";
/* CineBook front end (View). Talks to the REST API only; all business rules live on the server. */
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = n => "Rs." + Number(n).toFixed(2);
const when = iso => new Date(iso).toLocaleString([], { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

const state = { token: sessionStorage.getItem("token"), user: null, show: null, seats: [], selected: new Set() };

/* ---------- API + UI helpers ---------- */
async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (state.token) headers.Authorization = "Bearer " + state.token;
  const res = await fetch("/api" + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    if (res.status === 401 && state.token) signOut();
    throw new Error((data && data.error) || `Request failed (${res.status})`);
  }
  return data;
}

function toast(msg, kind = "") {
  const el = document.createElement("div");
  el.className = "toast " + kind;
  el.textContent = msg;
  $("#toasts").append(el);
  setTimeout(() => el.remove(), 4500);
}
const guard = fn => async (...a) => { try { await fn(...a); } catch (e) { toast(e.message, "error"); } };

function showView(name) {
  $$(".view").forEach(v => (v.hidden = v.id !== "view-" + name));
  $$("#nav button").forEach(b => b.classList.toggle("active", b.dataset.view === name));
  if (name === "movies") loadMovies();
  if (name === "bookings") loadBookings();
  if (name === "notifications") loadNotifications();
  if (name === "admin") loadAdminLists();
}

/* ---------- auth ---------- */
function enterApp(token, user) {
  state.token = token; state.user = user;
  sessionStorage.setItem("token", token);
  $("#username").textContent = `${user.name} (${user.role.toLowerCase()})`;
  $("#nav").hidden = false; $("#userchip").hidden = false;
  $$("#nav button").forEach(b => (b.hidden = b.dataset.role && b.dataset.role !== user.role));
  showView("movies");
}

function signOut() {
  if (state.token) api("/auth/logout", { method: "POST" }).catch(() => {});
  state.token = null; state.user = null; sessionStorage.removeItem("token");
  $("#nav").hidden = true; $("#userchip").hidden = true;
  showView("auth");
}

$$(".tab").forEach(t => t.addEventListener("click", () => {
  $$(".tab").forEach(x => x.classList.toggle("active", x === t));
  $("#form-login").hidden = t.dataset.auth !== "login";
  $("#form-register").hidden = t.dataset.auth !== "register";
}));
$$("[data-fill]").forEach(a => a.addEventListener("click", e => {
  e.preventDefault();
  $("#form-login [name=email]").value = a.dataset.fill;
  $("#form-login [name=password]").value = "demo1234";
}));
$("#form-login").addEventListener("submit", guard(async e => {
  e.preventDefault();
  const f = new FormData(e.target);
  const r = await api("/auth/login", { method: "POST", body: { email: f.get("email"), password: f.get("password") } });
  e.target.reset(); enterApp(r.token, r.user);
}));
$("#form-register").addEventListener("submit", guard(async e => {
  e.preventDefault();
  const f = new FormData(e.target);
  const r = await api("/auth/register", { method: "POST", body: {
    name: f.get("name"), email: f.get("email"), password: f.get("password"), phone: f.get("phone") || "", is_student: f.get("is_student") === "on" } });
  e.target.reset(); toast("Account created", "good"); enterApp(r.token, r.user);
}));
$("#signout").addEventListener("click", signOut);
$("#nav").addEventListener("click", e => { if (e.target.dataset.view) showView(e.target.dataset.view); });

/* ---------- movies and shows ---------- */
const loadMovies = guard(async () => {
  const movies = await api("/movies");
  $("#shows-panel").hidden = true;
  $("#movies").innerHTML = movies.map(m => `
    <div class="movie">
      <h3>${esc(m.title)}</h3>
      <div class="meta">${esc(m.genre)} · ${esc(m.language)} · ${m.duration_min} min · <span class="badge">${esc(m.rating)}</span></div>
      <div><button class="primary" data-movie="${m.id}" data-title="${esc(m.title)}">View shows</button></div>
    </div>`).join("") || "<p class='muted'>No movies yet.</p>";
});

$("#movies").addEventListener("click", guard(async e => {
  const btn = e.target.closest("[data-movie]");
  if (!btn) return;
  const shows = await api(`/movies/${btn.dataset.movie}/shows`);
  const panel = $("#shows-panel");
  const customer = state.user.role === "CUSTOMER";
  panel.hidden = false;
  panel.innerHTML = `<h3>${esc(btn.dataset.title)} – upcoming shows</h3>` + (shows.map(s => `
    <div class="show-row">
      <div class="grow"><b>${when(s.start_time)}</b><br><span class="muted">${esc(s.screen.name)} · from ${money(s.base_price)}</span></div>
      <span class="muted">${s.available_seats}/${s.screen.capacity} seats left</span>
      <button class="primary" data-show="${s.id}" ${s.available_seats && customer ? "" : "disabled"}>${customer ? (s.available_seats ? "Select seats" : "Sold out") : "Customers only"}</button>
    </div>`).join("") || "<p class='muted'>No upcoming shows.</p>");
  panel.scrollIntoView({ behavior: "smooth" });
}));

$("#shows-panel").addEventListener("click", guard(async e => {
  const btn = e.target.closest("[data-show]");
  if (btn) await openBooking(btn.dataset.show);
}));

/* ---------- seat selection ---------- */
async function openBooking(showId) {
  state.selected.clear();
  await refreshSeats(showId);
  $("#confirmation").hidden = true;
  const s = state.show;
  $("#booking-title").textContent = s.movie.title;
  $("#booking-sub").textContent = `${when(s.start_time)} · ${s.screen.name}`;
  renderPayFields(); updateQuote();
  showView("booking");
}

async function refreshSeats(showId = state.show.id) {
  const r = await api(`/shows/${showId}/seats`);
  state.show = r.show; state.seats = r.seats;
  state.selected = new Set([...state.selected].filter(l => r.seats.find(s => s.label === l && s.available)));
  renderSeats();
}

function renderSeats() {
  const rows = {};
  state.seats.forEach(s => (rows[s.row] ||= []).push(s));
  $("#seatgrid").innerHTML = Object.entries(rows).map(([row, seats]) =>
    `<div class="seatrow"><span class="rowlabel">${esc(row)}</span>` + seats.map(s =>
      `<button type="button" class="seat ${s.type.toLowerCase()}${s.available ? "" : " taken"}${state.selected.has(s.label) ? " selected" : ""}" ` +
      `data-label="${esc(s.label)}" ${s.available ? "" : "disabled"} title="${esc(s.label)} · ${esc(s.type)}">${s.number}</button>`).join("") + "</div>").join("");
}

$("#seatgrid").addEventListener("click", guard(async e => {
  const btn = e.target.closest("[data-label]");
  if (!btn) return;
  const label = btn.dataset.label;
  if (state.selected.has(label)) state.selected.delete(label);
  else if (state.selected.size >= 10) return toast("Maximum 10 seats per booking", "error");
  else state.selected.add(label);
  renderSeats();
  await updateQuote();
}));

const updateQuote = guard(async () => {
  const box = $("#quote");
  if (!state.selected.size) { box.textContent = "Pick up to 10 seats."; $("#pay-form").hidden = true; return; }
  try {
    const q = await api(`/shows/${state.show.id}/quote`, { method: "POST", body: { seats: [...state.selected] } });
    box.innerHTML = `<table class="q">` + q.seats.map(s => `<tr><td>${esc(s.label)}</td><td class="muted">${esc(s.type)}</td><td>${money(s.price)}</td></tr>`).join("") +
      `<tr class="total"><td colspan="2">Total</td><td>${money(q.total)}</td></tr></table><div class="muted">Pricing rule: ${esc(q.pricing)}</div>`;
    $("#pay-form").hidden = false;
  } catch (err) {
    toast(err.message, "error");
    await refreshSeats(); // e.g. someone else just took the seat
    $("#pay-form").hidden = true;
  }
});

/* ---------- payment ---------- */
const PAY_FIELDS = {
  UPI: `<label>UPI id<input id="f-upi" placeholder="name@bank" autocomplete="off"></label>`,
  CARD: `<label>Card number (16 digits)<input id="f-card" inputmode="numeric" maxlength="19" autocomplete="off"></label><label>CVV<input id="f-cvv" inputmode="numeric" maxlength="3" autocomplete="off"></label>`,
  WALLET: `<label>Wallet balance (simulated)<input id="f-wallet" type="number" min="0" value="1000"></label>`,
};
function renderPayFields() { $("#pay-fields").innerHTML = PAY_FIELDS[$("#method").value]; }
$("#method").addEventListener("change", renderPayFields);

function paymentDetails() {
  switch ($("#method").value) {
    case "UPI": return { upi_id: $("#f-upi").value.trim() };
    case "CARD": return { card_number: $("#f-card").value, cvv: $("#f-cvv").value };
    default: return { balance: Number($("#f-wallet").value) };
  }
}

$("#pay").addEventListener("click", async () => {
  const btn = $("#pay"); btn.disabled = true;
  try {
    const b = await api("/bookings", { method: "POST", body: {
      show_id: state.show.id, seats: [...state.selected], method: $("#method").value, details: paymentDetails() } });
    state.selected.clear();
    toast("Booking confirmed!", "good");
    $("#confirmation").hidden = false;
    $("#confirmation").innerHTML = `<h3>🎟 Booking #${b.id} confirmed</h3><p>${esc(b.show.movie.title)} · ${when(b.show.start_time)} · ${esc(b.show.screen.name)}</p>
      <p class="codes">${b.tickets.map(t => `${esc(t.seat)}: ${esc(t.code)}`).join("<br>")}</p>
      <p><b>${money(b.total_amount)}</b> paid via ${esc(b.payment.method)} (ref ${esc(b.payment.txn_ref)})</p>`;
    $("#confirmation").scrollIntoView({ behavior: "smooth" });
    await refreshSeats(); await updateQuote();
  } catch (e) {
    toast(e.message, "error");
    await refreshSeats().catch(() => {}); await updateQuote();
  } finally { btn.disabled = false; }
});
$("#back-to-movies").addEventListener("click", () => showView("movies"));

/* ---------- my bookings ---------- */
const loadBookings = guard(async () => {
  const list = await api("/bookings");
  $("#bookings").innerHTML = list.map(b => `
    <div class="card"><div class="bk">
      <div><b>#${b.id} · ${esc(b.show.movie.title)}</b> <span class="badge ${b.status}">${b.status}</span><br>
        <span class="muted">${when(b.show.start_time)} · ${esc(b.show.screen.name)}</span><br>
        Seats: ${b.tickets.map(t => esc(t.seat)).join(", ")} · <b>${money(b.total_amount)}</b>
        <span class="muted">(${esc(b.payment?.method ?? "-")}: ${esc(b.payment?.status ?? "-")})</span></div>
      <div>${b.status === "CONFIRMED" || b.status === "PENDING" ? `<button class="danger" data-cancel="${b.id}">Cancel</button>` : ""}</div>
    </div></div>`).join("") || "<p class='muted'>No bookings yet.</p>";
});
$("#bookings").addEventListener("click", guard(async e => {
  const btn = e.target.closest("[data-cancel]");
  if (!btn || !confirm("Cancel this booking? Paid amounts are refunded.")) return;
  await api(`/bookings/${btn.dataset.cancel}/cancel`, { method: "POST" });
  toast("Booking cancelled and refunded", "good");
  await loadBookings();
}));

/* ---------- notifications ---------- */
const loadNotifications = guard(async () => {
  const list = await api("/notifications");
  $("#notifications").innerHTML = list.map(n => `<div class="card"><b>${esc(n.message)}</b><br><span class="muted">${esc(n.at.replace("T", " "))}</span></div>`).join("")
    || "<p class='muted'>Nothing yet. Book or cancel a ticket to see notifications.</p>";
});

/* ---------- admin ---------- */
$$("[data-report]").forEach(b => b.addEventListener("click", guard(async () => {
  const r = await api("/admin/reports/" + b.dataset.report);
  const out = $("#report-out"); out.hidden = false; out.textContent = r.text;
})));

const loadAdminLists = guard(async () => {
  const [movies, screens] = await Promise.all([api("/movies"), api("/admin/screens")]);
  $("#show-movie").innerHTML = movies.map(m => `<option value="${m.id}">${esc(m.title)} (${m.duration_min} min)</option>`).join("");
  $("#show-screen").innerHTML = screens.map(s => `<option value="${s.id}">${esc(s.theatre)} – ${esc(s.name)} (${s.capacity} seats)</option>`).join("");
});

$("#form-movie").addEventListener("submit", guard(async e => {
  e.preventDefault();
  const f = Object.fromEntries(new FormData(e.target));
  await api("/admin/movies", { method: "POST", body: { ...f, duration_min: Number(f.duration_min) } });
  e.target.reset(); toast("Movie added", "good"); await loadAdminLists();
}));
$("#form-show").addEventListener("submit", guard(async e => {
  e.preventDefault();
  const f = Object.fromEntries(new FormData(e.target));
  await api("/admin/shows", { method: "POST", body: { ...f, movie_id: Number(f.movie_id), screen_id: Number(f.screen_id), base_price: Number(f.base_price) } });
  e.target.reset(); toast("Show scheduled", "good"); await loadAdminLists();
}));

/* ---------- start ---------- */
(async function start() {
  if (state.token) {
    try { const u = await api("/me"); return enterApp(state.token, u); } catch { /* fall through to sign-in */ }
  }
  showView("auth");
})();

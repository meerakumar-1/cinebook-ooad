"use strict";
/* CineBook front end (the "View"). It talks to the REST API only: every business rule lives on the server. */
const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = n => "Rs." + Number(n).toFixed(2);
const dayLabel = iso => new Date(iso).toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });
const timeLabel = iso => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
const when = iso => `${dayLabel(iso)} · ${timeLabel(iso)}`;
const mmss = s => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
const trunc = (s, n) => (s.length > n ? s.slice(0, n - 1) + "…" : s);

const EMOJI = { "Sci-Fi": "🚀", Drama: "🎭", Comedy: "😂", Thriller: "🕵️", Romance: "💞", Action: "💥", Horror: "👻" };
const hash = s => [...s].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7);
const posterHTML = m => `<div class="poster p${hash(m.title) % 12}" role="img" aria-label="${esc(m.title)} poster"><span class="p-emoji">${EMOJI[m.genre] || "🎬"}</span><span class="p-title">${esc(m.title)}</span></div>`;

const state = {
  token: sessionStorage.getItem("token"), user: null, movies: [], filter: { q: "", genre: "", lang: "" },
  show: null, seats: [], selected: new Set(), booking: null, method: "UPI", timer: null, deadline: 0, quoteId: 0, bookings: [],
};

/* ---------- API + UI helpers ---------- */
async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (state.token) headers.Authorization = "Bearer " + state.token;
  const res = await fetch("/api" + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    if (res.status === 401 && state.token) signOut();
    const err = new Error((data && data.error) || `Request failed (${res.status})`);
    err.status = res.status;
    throw err;
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
const guard = fn => async (...a) => { try { return await fn(...a); } catch (e) { toast(e.message, "error"); } };

function askConfirm(title, text, yes = "Yes, cancel") {
  return new Promise(resolve => {
    const d = $("#confirm-dialog");
    $("#cf-title").textContent = title; $("#cf-text").textContent = text; $("#cf-yes").textContent = yes;
    let result = false;
    const onClick = e => { if (e.target.dataset.result) { result = e.target.dataset.result === "yes"; d.close(); } };
    d.addEventListener("click", onClick);
    d.addEventListener("close", () => { d.removeEventListener("click", onClick); resolve(result); }, { once: true });
    d.showModal();
  });
}

const STEPS = ["Seats", "Payment", "Tickets"];
const stepper = n => STEPS.map((s, i) =>
  `<li class="${i < n ? "done" : i === n ? "active" : ""}"><span class="n">${i < n ? "✓" : i + 1}</span>${s}</li>`).join("");

function stopTimer() { clearInterval(state.timer); state.timer = null; }

function showView(name) {
  if (name !== "checkout") stopTimer();
  $$(".view").forEach(v => (v.hidden = v.id !== "view-" + name));
  $$("#nav button").forEach(b => b.classList.toggle("active", b.dataset.view === name));
  window.scrollTo({ top: 0 });
  if (name === "movies") loadMovies();
  if (name === "bookings") loadBookings();
  if (name === "notifications") loadNotifications();
  if (name === "admin") loadAdmin();
}

/* ---------- theme ---------- */
$("#theme").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("theme", next); } catch { /* ignore */ }
});
document.addEventListener("click", e => {
  const close = e.target.closest("[data-close]");
  if (close) close.closest("dialog").close();
  if (e.target.tagName === "DIALOG" && e.target.id !== "confirm-dialog") e.target.close(); // click on backdrop
});

/* ---------- auth ---------- */
function enterApp(token, user) {
  state.token = token; state.user = user;
  sessionStorage.setItem("token", token);
  $("#username").textContent = user.name;
  $("#avatar").textContent = user.name.trim()[0].toUpperCase();
  $("#nav").hidden = false; $("#userchip").hidden = false;
  $$("#nav button").forEach(b => (b.hidden = !!b.dataset.role && b.dataset.role !== user.role));
  showView(user.role === "ADMIN" ? "admin" : "movies");
}

function signOut() {
  if (state.token) api("/auth/logout", { method: "POST" }).catch(() => {});
  stopTimer();
  Object.assign(state, { token: null, user: null, movies: [], booking: null, show: null });
  sessionStorage.removeItem("token");
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
  e.target.reset(); toast("Welcome to CineBook!", "good"); enterApp(r.token, r.user);
}));
$("#signout").addEventListener("click", signOut);
$("#brand").addEventListener("click", () => state.user && showView(state.user.role === "ADMIN" ? "admin" : "movies"));
$("#nav").addEventListener("click", e => { if (e.target.dataset.view) showView(e.target.dataset.view); });

/* ---------- movies ---------- */
const loadMovies = guard(async () => {
  if (!state.movies.length) {
    $("#movies").innerHTML = Array(6).fill('<div class="skeleton"></div>').join("");
    state.movies = await api("/movies");
    const genres = [...new Set(state.movies.map(m => m.genre))].sort();
    $("#genres").innerHTML = ["", ...genres].map(g => `<button class="chip${g === state.filter.genre ? " active" : ""}" data-genre="${esc(g)}">${g ? esc(g) : "All"}</button>`).join("");
    const langs = [...new Set(state.movies.map(m => m.language))].sort();
    $("#lang").innerHTML = '<option value="">All languages</option>' + langs.map(l => `<option>${esc(l)}</option>`).join("");
  }
  renderMovies();
});

function renderMovies() {
  const { q, genre, lang } = state.filter;
  const list = state.movies.filter(m =>
    (!genre || m.genre === genre) && (!lang || m.language === lang) &&
    (!q || (m.title + " " + m.genre + " " + m.language).toLowerCase().includes(q.toLowerCase())));
  const unfiltered = !q && !genre && !lang && state.movies.length;
  const hero = $("#hero");
  hero.hidden = !unfiltered;
  if (unfiltered) {
    const m = state.movies[0];
    hero.innerHTML = `${posterHTML(m)}<div><div class="tag">Featured tonight</div><h2>${esc(m.title)}</h2>
      <div class="meta">${esc(m.genre)} · ${esc(m.language)} · ${m.duration_min} min · <span class="badge">${esc(m.rating)}</span></div>
      <p class="syn">${esc(m.synopsis)}</p><button class="primary" data-movie="${m.id}">Book tickets</button></div>`;
  }
  $("#movies").innerHTML = list.map(m => `
    <article class="movie">${posterHTML(m)}
      <div><h3>${esc(m.title)}</h3><div class="meta">${esc(m.genre)} · ${esc(m.language)} · ${m.duration_min} min · <span class="badge">${esc(m.rating)}</span></div></div>
      <p class="syn">${esc(m.synopsis)}</p>
      <button class="primary" data-movie="${m.id}">Book tickets</button>
    </article>`).join("") || '<div class="empty">No movies match your filters.</div>';
}

$("#search").addEventListener("input", e => { state.filter.q = e.target.value.trim(); renderMovies(); });
$("#lang").addEventListener("change", e => { state.filter.lang = e.target.value; renderMovies(); });
$("#genres").addEventListener("click", e => {
  const b = e.target.closest("[data-genre]"); if (!b) return;
  state.filter.genre = b.dataset.genre;
  $$("#genres .chip").forEach(c => c.classList.toggle("active", c === b));
  renderMovies();
});
$("#view-movies").addEventListener("click", e => { const b = e.target.closest("[data-movie]"); if (b) openMovie(b.dataset.movie); });

const openMovie = guard(async id => {
  const m = state.movies.find(x => String(x.id) === String(id));
  $("#md-poster").innerHTML = posterHTML(m);
  $("#md-title").textContent = m.title;
  $("#md-meta").textContent = `${m.genre} · ${m.language} · ${m.duration_min} min · ${m.rating}`;
  $("#md-synopsis").textContent = m.synopsis;
  $("#md-shows").innerHTML = '<p class="muted">Loading shows…</p>';
  $("#movie-dialog").showModal();
  const shows = await api(`/movies/${id}/shows`);
  const byDay = {};
  shows.forEach(s => (byDay[s.start_time.slice(0, 10)] ||= []).push(s));
  const customer = state.user.role === "CUSTOMER";
  $("#md-shows").innerHTML = Object.values(byDay).map(day => `<div class="day">${dayLabel(day[0].start_time)}</div><div class="show-chips">` +
    day.map(s => {
      const low = s.available_seats / s.screen.capacity < 0.2 ? " low" : "";
      return `<button class="show-chip" data-show="${s.id}" ${s.available_seats && customer ? "" : "disabled"}><b>${timeLabel(s.start_time)}</b>
        <small>${esc(s.screen.name)} · from ${money(s.base_price)}</small>
        <small class="left${low}">${s.available_seats ? s.available_seats + " seats left" : "Sold out"}</small></button>`;
    }).join("") + "</div>").join("") || '<p class="muted">No upcoming shows. Check back soon.</p>';
  if (!customer) $("#md-shows").insertAdjacentHTML("afterbegin", '<p class="hint">Sign in as a customer to book seats.</p>');
});
$("#md-shows").addEventListener("click", e => {
  const b = e.target.closest("[data-show]"); if (!b) return;
  $("#movie-dialog").close(); openSeats(b.dataset.show);
});

/* ---------- step 1: seat selection ---------- */
const openSeats = guard(async showId => {
  state.selected.clear(); state.booking = null;
  await refreshSeats(showId);
  const s = state.show;
  $("#seat-title").textContent = s.movie.title;
  $("#seat-sub").textContent = `${when(s.start_time)} · ${s.screen.name}`;
  $("#legend").innerHTML = `<span><i></i>Regular ${money(s.tiers.REGULAR)}</span><span><i class="premium"></i>Premium ${money(s.tiers.PREMIUM)}</span>
    <span><i class="recliner"></i>Recliner ${money(s.tiers.RECLINER)}</span><span><i class="taken"></i>Taken</span><span><i class="selected"></i>Selected</span>`;
  $("#stepper-seats").innerHTML = stepper(0);
  renderQuote(null);
  showView("seats");
});

async function refreshSeats(showId = state.show.id) {
  const r = await api(`/shows/${showId}/seats`);
  state.show = r.show; state.seats = r.seats;
  state.selected = new Set([...state.selected].filter(l => r.seats.some(s => s.label === l && s.available)));
  renderSeats();
}

function renderSeats() {
  const rows = {};
  state.seats.forEach(s => (rows[s.row] ||= []).push(s));
  $("#seatgrid").innerHTML = Object.entries(rows).map(([row, seats]) =>
    `<div class="seatrow"><span class="rowlabel">${esc(row)}</span>` + seats.map((s, i) => {
      const cls = ["seat", s.type.toLowerCase(), s.available ? "" : "taken", state.selected.has(s.label) ? "selected" : "", i === Math.floor(seats.length / 2) - 1 ? "gap" : ""].filter(Boolean).join(" ");
      return `<button type="button" class="${cls}" data-label="${esc(s.label)}" ${s.available ? "" : "disabled"} aria-pressed="${state.selected.has(s.label)}" aria-label="Seat ${esc(s.label)}, ${esc(s.type.toLowerCase())}${s.available ? "" : ", taken"}">${s.number}</button>`;
    }).join("") + "</div>").join("");
}

$("#seatgrid").addEventListener("click", guard(async e => {
  const btn = e.target.closest("[data-label]"); if (!btn) return;
  const label = btn.dataset.label;
  if (state.selected.has(label)) state.selected.delete(label);
  else if (state.selected.size >= 10) return toast("Maximum 10 seats per booking", "error");
  else state.selected.add(label);
  renderSeats();
  await updateQuote();
}));

async function updateQuote() {
  if (!state.selected.size) return renderQuote(null);
  const id = ++state.quoteId;
  try {
    const q = await api(`/shows/${state.show.id}/quote`, { method: "POST", body: { seats: [...state.selected] } });
    if (id === state.quoteId) renderQuote(q);
  } catch (err) {
    toast(err.message, "error");
    await refreshSeats(); renderQuote(null);
  }
}

function renderQuote(q) {
  $("#to-checkout").disabled = !q;
  $("#quote").innerHTML = q
    ? `<span class="rule">${esc(q.pricing)}</span><table class="q">${q.seats.map(s => `<tr><td><b>${esc(s.label)}</b> <span class="muted">${esc(s.type.toLowerCase())}</span></td><td>${money(s.price)}</td></tr>`).join("")}
       <tr class="total"><td>Total</td><td>${money(q.total)}</td></tr></table>`
    : '<p class="muted">Select up to 10 seats.</p>';
}

$("#to-checkout").addEventListener("click", guard(async () => {
  $("#to-checkout").disabled = true;
  try {
    const b = await api(`/shows/${state.show.id}/hold`, { method: "POST", body: { seats: [...state.selected] } });
    openCheckout(b);
  } catch (e) {
    toast(e.message, "error"); await refreshSeats(); await updateQuote();
  }
}));
$("#back-movies").addEventListener("click", () => showView("movies"));

/* ---------- step 2: payment ---------- */
const PAY_FIELDS = {
  UPI: '<label>UPI ID<input id="f-upi" placeholder="name@bank" autocomplete="off"></label>',
  CARD: '<label>Card number<input id="f-card" inputmode="numeric" maxlength="19" placeholder="1234 5678 9012 3456" autocomplete="off"></label><label>CVV<input id="f-cvv" inputmode="numeric" maxlength="3" placeholder="123" autocomplete="off"></label>',
  WALLET: '<label>Wallet balance (simulated)<input id="f-wallet" type="number" min="0" value="1000"></label>',
};

function openCheckout(b) {
  state.booking = b;
  $("#stepper-checkout").innerHTML = stepper(1);
  $("#order").innerHTML = `<h3>Order summary</h3><div class="order-title">${esc(b.show.movie.title)}</div>
    <p class="muted">${when(b.show.start_time)} · ${esc(b.show.screen.name)}</p>
    <table class="q">${b.tickets.map(t => `<tr><td><b>${esc(t.seat)}</b> <span class="muted">${esc(t.type.toLowerCase())}</span></td><td>${money(t.price)}</td></tr>`).join("")}
    <tr class="total"><td>Total</td><td>${money(b.total_amount)}</td></tr></table>`;
  $("#pay").textContent = `Pay ${money(b.total_amount)}`;
  setMethod(state.method);
  showView("checkout");
  startTimer(b.seconds_left ?? 0);
}

function setMethod(m) {
  state.method = m;
  $$(".method-tabs button").forEach(b => b.classList.toggle("active", b.dataset.method === m));
  $("#pay-fields").innerHTML = PAY_FIELDS[m];
}
$(".method-tabs").addEventListener("click", e => { const b = e.target.closest("[data-method]"); if (b) setMethod(b.dataset.method); });
$("#pay-fields").addEventListener("input", e => {
  if (e.target.id === "f-card") e.target.value = e.target.value.replace(/\D/g, "").slice(0, 16).replace(/(.{4})/g, "$1 ").trim();
});

function paymentDetails() {
  if (state.method === "UPI") return { upi_id: $("#f-upi").value.trim() };
  if (state.method === "CARD") return { card_number: $("#f-card").value, cvv: $("#f-cvv").value };
  return { balance: Number($("#f-wallet").value) };
}

function startTimer(seconds) {
  stopTimer();
  state.deadline = Date.now() + seconds * 1000;
  $("#expired-box").hidden = true; $("#pay").disabled = false;
  const tick = () => {
    const left = Math.max(0, Math.round((state.deadline - Date.now()) / 1000));
    const el = $("#countdown");
    el.textContent = `Seats held ${mmss(left)}`;
    el.classList.toggle("warn", left < 60);
    if (left <= 0) { stopTimer(); showExpired(); }
  };
  tick();
  if (seconds > 0) state.timer = setInterval(tick, 1000);
}

const releaseHold = b => (b ? api(`/bookings/${b.id}/release`, { method: "POST" }).catch(() => {}) : Promise.resolve());

function showExpired() {
  $("#pay").disabled = true; $("#expired-box").hidden = false;
  toast("Your seat hold expired", "error");
  releaseHold(state.booking); // free the seats now instead of waiting for the server's own deadline
}

$("#pay").addEventListener("click", async () => {
  const btn = $("#pay"); btn.disabled = true;
  try {
    const b = await api(`/bookings/${state.booking.id}/pay`, { method: "POST", body: { method: state.method, details: paymentDetails() } });
    stopTimer(); openDone(b);
  } catch (e) {
    toast(e.message, "error");
    if (e.status === 410) { stopTimer(); showExpired(); } else btn.disabled = false;
  }
});
$("#reselect").addEventListener("click", async () => { await releaseHold(state.booking); openSeats(state.booking.show.id); });
$("#back-seats").addEventListener("click", guard(async () => {
  const b = state.booking; stopTimer();
  await releaseHold(b); // free the seats right away
  await openSeats(b.show.id);
}));

/* ---------- step 3: tickets ---------- */
function barcode(code) {
  let x = 0, bars = "";
  for (const ch of code + code) {
    const v = ch.charCodeAt(0), w = 1 + (v % 3);
    bars += `<rect x="${x}" y="0" width="${w}" height="40" fill="currentColor"/>`;
    x += w + 1 + ((v >> 2) % 2);
  }
  return `<svg class="barcode" viewBox="0 0 ${x} 40" preserveAspectRatio="none" aria-hidden="true">${bars}</svg>`;
}

function ticketsHTML(b) {
  return b.tickets.map(t => `<div class="ticket"><div class="t-main"><div class="t-title">${esc(b.show.movie.title)}</div>
    <div class="t-meta">${when(b.show.start_time)} · ${esc(b.show.screen.name)}</div>
    <div class="t-seat"><span>SEAT</span><b>${esc(t.seat)}</b></div><div class="t-meta">${esc(t.type)} · ${money(t.price)}</div></div>
    <div class="t-stub">${barcode(t.code)}<div class="t-code">${esc(t.code)}</div></div></div>`).join("");
}

function openDone(b) {
  $("#stepper-done").innerHTML = stepper(3);
  $("#done-sub").textContent = `Booking #${b.id} · ${money(b.total_amount)} paid via ${b.payment ? b.payment.method : "—"}${b.payment ? " (ref " + b.payment.txn_ref + ")" : ""}`;
  $("#tickets").innerHTML = ticketsHTML(b);
  showView("done");
}
$("#print").addEventListener("click", () => window.print());
$("#done-bookings").addEventListener("click", () => showView("bookings"));
$("#done-movies").addEventListener("click", () => showView("movies"));

/* ---------- my bookings ---------- */
const loadBookings = guard(async () => {
  state.bookings = await api("/bookings");
  $("#bookings").innerHTML = state.bookings.map(b => {
    const seats = b.tickets.map(t => esc(t.seat)).join(", ");
    const pay = b.payment ? `${esc(b.payment.method)}: ${esc(b.payment.status.toLowerCase())}` : "";
    const actions = b.status === "CONFIRMED"
      ? `<button class="ghost sm" data-tickets="${b.id}">View tickets</button><button class="danger" data-cancel="${b.id}">Cancel</button>`
      : b.status === "PENDING"
        ? `<button class="primary sm" data-resume="${b.id}">Complete payment (${mmss(b.seconds_left ?? 0)})</button><button class="danger" data-cancel="${b.id}" data-release="1">Release seats</button>` : "";
    return `<div class="card bk">${posterHTML(b.show.movie)}
      <div><b>#${b.id} · ${esc(b.show.movie.title)}</b> <span class="badge ${b.status}">${b.status}</span><br>
        <span class="muted">${when(b.show.start_time)} · ${esc(b.show.screen.name)}</span><br>Seats ${seats} · <b>${money(b.total_amount)}</b> <span class="muted">${pay}</span></div>
      <div class="bk-actions">${actions}</div></div>`;
  }).join("") || '<div class="card empty">No bookings yet. <button class="primary sm" id="empty-browse">Browse movies</button></div>';
});

$("#bookings").addEventListener("click", guard(async e => {
  if (e.target.id === "empty-browse") return showView("movies");
  const find = id => state.bookings.find(b => String(b.id) === String(id));
  const tickets = e.target.closest("[data-tickets]"), resume = e.target.closest("[data-resume]"), cancel = e.target.closest("[data-cancel]");
  if (tickets) return openDone(find(tickets.dataset.tickets));
  if (resume) {
    const b = await api(`/bookings/${resume.dataset.resume}`);
    if (b.status !== "PENDING") { toast("That hold has expired", "error"); return loadBookings(); }
    return openCheckout(b);
  }
  if (cancel) {
    const releasing = !!cancel.dataset.release;
    const ok = await askConfirm(releasing ? "Release these seats?" : "Cancel this booking?",
      releasing ? "The seats become available to others." : "Your payment will be refunded.", releasing ? "Yes, release" : "Yes, cancel");
    if (!ok) return;
    await api(`/bookings/${cancel.dataset.cancel}/cancel`, { method: "POST" });
    toast(releasing ? "Seats released" : "Booking cancelled and refunded", "good");
    await loadBookings();
  }
}));

/* ---------- notifications ---------- */
const loadNotifications = guard(async () => {
  const list = await api("/notifications");
  $("#notifications").innerHTML = list.map(n => `<div class="card note"><span class="dot ${esc(n.event)}"></span><div><b>${esc(n.message)}</b><br><span class="muted">${when(n.at)}</span></div></div>`).join("")
    || '<div class="card empty">Nothing yet. Book or cancel a ticket and it will show up here.</div>';
});

/* ---------- admin dashboard ---------- */
const loadAdmin = guard(async () => {
  const [stats, bookings, movies, screens] = await Promise.all([api("/admin/stats"), api("/admin/bookings"), api("/movies"), api("/admin/screens")]);
  const c = stats.bookings;
  $("#stats").innerHTML = [["Revenue", money(stats.revenue)], ["Tickets sold", stats.tickets_sold], ["Occupancy", stats.occupancy_pct + "%"],
    ["Confirmed bookings", c.CONFIRMED], ["Scheduled shows", stats.shows]].map(([k, v]) => `<div class="stat"><small>${k}</small><b>${esc(v)}</b></div>`).join("");
  $("#status-chips").innerHTML = Object.entries(c).map(([k, v]) => `<span class="badge ${k}">${v} ${k.toLowerCase()}</span>`).join(" ");
  renderChart(stats.revenue_by_movie);
  $("#admin-bookings").innerHTML = "<thead><tr><th>#</th><th>Customer</th><th>Movie</th><th>Show</th><th>Seats</th><th>Total</th><th>Status</th><th></th></tr></thead><tbody>" +
    bookings.map(b => `<tr><td>${b.id}</td><td>${esc(b.customer.name)}</td><td>${esc(b.show.movie.title)}</td><td>${when(b.show.start_time)}</td>
      <td>${b.tickets.map(t => esc(t.seat)).join(", ")}</td><td>${money(b.total_amount)}</td><td><span class="badge ${b.status}">${b.status}</span></td>
      <td>${b.status === "CONFIRMED" || b.status === "PENDING" ? `<button class="danger" data-admin-cancel="${b.id}">Cancel</button>` : ""}</td></tr>`).join("") + "</tbody>";
  $("#show-movie").innerHTML = movies.map(m => `<option value="${m.id}">${esc(m.title)} (${m.duration_min} min)</option>`).join("");
  $("#show-screen").innerHTML = screens.map(s => `<option value="${s.id}">${esc(s.theatre)} – ${esc(s.name)} (${s.capacity} seats)</option>`).join("");
});

function renderChart(rows) {
  if (!rows.length) { $("#chart").innerHTML = '<p class="muted">No confirmed bookings yet.</p>'; return; }
  const max = Math.max(...rows.map(r => r.revenue)), rowH = 34, w = 520, labelW = 150, barMax = w - labelW - 90;
  const body = rows.map((r, i) => {
    const y = i * rowH, bw = Math.max(6, Math.round(barMax * r.revenue / max));
    return `<text x="0" y="${y + 18}">${esc(trunc(r.title, 20))}</text><rect class="track" x="${labelW}" y="${y + 4}" width="${barMax}" height="18" rx="9"/>
      <rect class="bar" x="${labelW}" y="${y + 4}" width="${bw}" height="18" rx="9"/><text class="val" x="${labelW + bw + 8}" y="${y + 18}">${money(r.revenue)}</text>`;
  }).join("");
  $("#chart").innerHTML = `<svg class="chart" viewBox="0 0 ${w} ${rows.length * rowH}" role="img" aria-label="Revenue by movie">
    <defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#ff3d5a"/><stop offset="1" stop-color="#ff8a3d"/></linearGradient></defs>${body}</svg>`;
}

$("#admin-bookings").addEventListener("click", guard(async e => {
  const b = e.target.closest("[data-admin-cancel]"); if (!b) return;
  if (!(await askConfirm("Cancel this booking?", "The customer is refunded and notified."))) return;
  await api(`/bookings/${b.dataset.adminCancel}/cancel`, { method: "POST" });
  toast("Booking cancelled", "good"); await loadAdmin();
}));
$$("[data-report]").forEach(b => b.addEventListener("click", guard(async () => {
  const r = await api("/admin/reports/" + b.dataset.report);
  $("#rd-title").textContent = b.textContent; $("#rd-text").textContent = r.text; $("#report-dialog").showModal();
})));
$("#form-movie").addEventListener("submit", guard(async e => {
  e.preventDefault();
  const f = Object.fromEntries(new FormData(e.target));
  await api("/admin/movies", { method: "POST", body: { ...f, duration_min: Number(f.duration_min) } });
  e.target.reset(); state.movies = []; toast("Movie added", "good"); await loadAdmin();
}));
$("#form-show").addEventListener("submit", guard(async e => {
  e.preventDefault();
  const f = Object.fromEntries(new FormData(e.target));
  await api("/admin/shows", { method: "POST", body: { ...f, movie_id: Number(f.movie_id), screen_id: Number(f.screen_id), base_price: Number(f.base_price) } });
  e.target.reset(); toast("Show scheduled", "good"); await loadAdmin();
}));

/* ---------- start ---------- */
(async function start() {
  if (state.token) {
    try { return enterApp(state.token, await api("/me")); } catch { /* fall through to sign-in */ }
  }
  showView("auth");
})();

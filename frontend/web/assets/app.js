/* BrickMatch AI — branded single-page interface for the local FastAPI service.
   No build step, no third-party runtime. All state stays in the browser. */
(() => {
  "use strict";

  /* ------------------------------------------------------------------ */
  /* API + small helpers                                                 */
  /* ------------------------------------------------------------------ */

  const query = new URLSearchParams(location.search);
  const storedApi = localStorage.getItem("brickmatch.api");
  const storedToken = () => localStorage.getItem("brickmatch.auth_token");
  const API_BASE = (query.get("api") || storedApi ||
    (location.protocol === "file:" ? "http://127.0.0.1:8000/api/v1" : "/api/v1")
  ).replace(/\/+$/, "");

  const docBase = API_BASE.replace(/\/api\/v1$/, "");
  const TITLES = {
    discover: "Discover",
    swipe: "Swipe",
    "for-you": "For You",
    preferences: "My Taste",
    "model-lab": "Model Lab",
    system: "System",
  };
  const ROUTES = Object.keys(TITLES);
  const MODE_LABELS = {
    cold_start: "Cold start · catalog order",
    metadata_profile: "Metadata profile",
    hybrid_profile: "Hybrid · visual + metadata",
    classifier_profile: "Personalized classifier",
  };
  const ACTION_LABELS = { like: "Liked", dislike: "Disliked", skip: "Skipped", undo: "Removed" };
  const USER_PATTERN = /^[A-Za-z0-9_-]{1,80}$/;

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]
  ));

  const formatNumber = (value) => {
    const number = Number(value);
    return Number.isFinite(number) ? new Intl.NumberFormat().format(number) : "—";
  };
  const formatMs = (value) => {
    const number = Number(value);
    if (!Number.isFinite(number)) return "—";
    return `${number < 10 ? number.toFixed(1) : Math.round(number)} ms`;
  };
  const initials = (value) => (String(value || "?").trim()[0] || "?").toUpperCase();
  const icon = (name) => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"/></svg>`;
  const imageUrl = (setId) => `${API_BASE}/images/${encodeURIComponent(setId)}`;

  async function api(path, options = {}) {
    const token = storedToken();
    const request = { headers: { Accept: "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}) }, ...options };
    if (options.body !== undefined && typeof options.body !== "string") {
      request.headers = { ...request.headers, "Content-Type": "application/json" };
      request.body = JSON.stringify(options.body);
    }
    const response = await fetch(`${API_BASE}${path}`, request);
    let payload = null;
    try { payload = await response.json(); } catch { payload = null; }
    if (!response.ok) {
      const detail = payload && (payload.detail || payload.message);
      const message = typeof detail === "string" ? detail
        : detail ? JSON.stringify(detail) : `Request failed (${response.status})`;
      throw new Error(message);
    }
    return payload;
  }

  /* ------------------------------------------------------------------ */
  /* State                                                               */
  /* ------------------------------------------------------------------ */

  const state = {
    user: "builder",
    route: "",
    boot: null,
    bootstrapError: null,
    themes: [],
    users: [],
    model: null,
    evaluation: null,
    feedback: { current: [], events: [] },
    summary: null,
    recommendations: null,
    discover: {
      q: "", theme: "", minYear: 1949, maxYear: 2200, maxParts: 100000,
      sort: "set_id", limit: 24, offset: 0, total: 0, items: [], rendered: 0,
      loading: false, error: null,
    },
    swipe: { queue: [], total: 0, loading: false, busy: false, error: null, last: null },
  };

  let discoverToken = 0;
  let searchTimer = null;

  const feedbackMap = () => {
    const map = new Map();
    state.feedback.current.forEach((row) => map.set(row.set_id, row.action));
    return map;
  };
  const feedbackAction = (setId) => feedbackMap().get(setId) || "";

  /* ------------------------------------------------------------------ */
  /* Toasts                                                              */
  /* ------------------------------------------------------------------ */

  function toast(message, type = "success") {
    const region = $("#toasts");
    if (!region) return;
    const node = document.createElement("div");
    node.className = `toast ${type}`;
    const glyph = type === "error" ? "alert" : type === "info" ? "info" : "check";
    node.innerHTML = `${icon(glyph)}<span>${escapeHtml(message)}</span>`;
    region.appendChild(node);
    const remove = () => {
      node.classList.add("leaving");
      setTimeout(() => node.remove(), 240);
    };
    const timer = setTimeout(remove, type === "error" ? 5200 : 3600);
    node.addEventListener("click", () => { clearTimeout(timer); remove(); });
  }

  /* ------------------------------------------------------------------ */
  /* Shared render fragments                                             */
  /* ------------------------------------------------------------------ */

  const skeletonGrid = (count = 8) => Array.from({ length: count }, () => `
    <div class="skeleton-card" aria-hidden="true">
      <div class="sk sk-media"></div>
      <div class="sk-body">
        <div class="sk sk-line"></div>
        <div class="sk sk-line short"></div>
        <div class="sk sk-line tiny"></div>
        <div class="sk sk-actions"></div>
      </div>
    </div>`).join("");

  function emptyState(title, message, cta = "") {
    return `<div class="state"><span class="state-icon">${icon("brick")}</span>
      <h3>${escapeHtml(title)}</h3><p>${escapeHtml(message)}</p>${cta}</div>`;
  }

  function errorState(message, retry = "discover") {
    return `<div class="state error"><span class="state-icon">${icon("alert")}</span>
      <h3>Could not load this view</h3><p>${escapeHtml(message)}</p>
      <button class="btn btn-ghost btn-sm" type="button" data-retry="${retry}">
        ${icon("refresh")} Try again</button></div>`;
  }

  function mediaHtml(item) {
    if (!item) return `<span class="placeholder">${icon("brick")}</span>`;
    if (item.image_available) {
      return `<img loading="lazy" src="${imageUrl(item.set_id)}"
        alt="${escapeHtml(item.name)} — LEGO set image">`;
    }
    return `<span class="placeholder">${icon("brick")}</span>`;
  }

  function actionButtons(item) {
    const action = feedbackAction(item.set_id);
    const config = [
      ["like", action === "like" ? "heart-fill" : "heart", "Like"],
      ["dislike", "x", "Dislike"],
      ["skip", "arrow-right", "Skip"],
    ];
    return config.map(([name, glyph, label]) => `
      <button class="action ${name} ${action === name ? "is-active" : ""}" type="button"
        data-action="${name}" data-set-id="${escapeHtml(item.set_id)}"
        aria-pressed="${action === name}" aria-label="${label} ${escapeHtml(item.name)}">
        ${icon(glyph)}<span>${label}</span>
      </button>`).join("");
  }

  function setCardHtml(item, options = {}) {
    if (!item) return "";
    const theme = item.theme || `Theme ${item.theme_id}`;
    const score = options.score !== undefined && options.score !== null
      ? `<span class="score-badge">${Math.round(Number(options.score) * 100)}%</span>` : "";
    return `<article class="set-card" data-set-id="${escapeHtml(item.set_id)}">
      <div class="card-media">
        ${mediaHtml(item)}
        <span class="badge">${escapeHtml(theme)}</span>
        ${score}
      </div>
      <div class="card-body">
        <h3 class="card-title">${escapeHtml(item.name)}</h3>
        <p class="card-meta"><strong>${escapeHtml(item.year)}</strong>
          · ${formatNumber(item.num_parts)} pieces · ${escapeHtml(item.set_id)}</p>
        ${options.extraHtml || ""}
        <div class="card-actions">${actionButtons(item)}</div>
      </div>
    </article>`;
  }

  function statTile(value, label, extraClass = "") {
    return `<div class="stat ${extraClass}">
      <div class="stat-value">${escapeHtml(value)}</div>
      <div class="stat-label">${escapeHtml(label)}</div>
    </div>`;
  }

  /* ------------------------------------------------------------------ */
  /* Profiles                                                            */
  /* ------------------------------------------------------------------ */

  function updateProfileChrome() {
    $("#profile-name").textContent = state.user;
    $("#profile-avatar").textContent = initials(state.user);
  }

  function renderProfileList() {
    const list = $("#profile-list");
    if (!list) return;
    const rows = state.users.length
      ? state.users
      : [{ user_id: state.user, ratings: state.feedback.current.length }];
    list.innerHTML = rows.map((row) => {
      const active = row.user_id === state.user;
      return `<button type="button" class="profile-row ${active ? "active" : ""}"
        data-profile="${escapeHtml(row.user_id)}">
        <span class="avatar">${escapeHtml(initials(row.user_id))}</span>
        <span><span class="p-name">${escapeHtml(row.user_id)}</span>
          <span class="p-count">${formatNumber(row.ratings)} rating${row.ratings === 1 ? "" : "s"}</span></span>
        ${active ? `<span class="p-check">${icon("check")}</span>` : ""}
      </button>`;
    }).join("");
  }

  async function openProfileDialog() {
    if (state.boot?.auth_required) {
      localStorage.removeItem("brickmatch.auth_token");
      await authenticateIfRequired();
      location.reload();
      return;
    }
    try {
      const data = await api("/users");
      state.users = data.items || [];
    } catch { /* keep the cached list */ }
    renderProfileList();
    const dialog = $("#profile-dialog");
    $("#profile-button").setAttribute("aria-expanded", "true");
    if (dialog.showModal) dialog.showModal(); else dialog.setAttribute("open", "");
  }

  function closeProfileDialog() {
    const dialog = $("#profile-dialog");
    if (dialog.open && dialog.close) dialog.close();
    else dialog.removeAttribute("open");
    $("#profile-button").setAttribute("aria-expanded", "false");
  }

  function switchUser(userId) {
    if (!USER_PATTERN.test(userId)) {
      toast("Use only letters, digits, underscore or hyphen (max 80).", "error");
      return;
    }
    state.user = userId;
    localStorage.setItem("brickmatch.user", userId);
    state.feedback = { current: [], events: [] };
    state.summary = null;
    state.recommendations = null;
    state.swipe = { queue: [], total: 0, loading: false, busy: false, error: null, last: null };
    updateProfileChrome();
    renderProfileList();
    closeProfileDialog();
    toast(`Switched to “${userId}”.`, "success");
    navigate(true);
  }

  /* ------------------------------------------------------------------ */
  /* Bootstrap                                                           */
  /* ------------------------------------------------------------------ */

  async function loadBootstrap() {
    const data = await api("/bootstrap");
    state.boot = data;
    state.themes = data.themes || [];
    state.users = data.users || [];
    state.model = data.model || null;
    state.evaluation = data.evaluation || null;
    renderThemeOptions();
    updateHeroStats();
    updateProfileChrome();
  }

  async function authenticateIfRequired() {
    if (!state.boot?.auth_required) return;
    const token = storedToken();
    if (token) {
      try {
        const me = await api("/auth/me");
        state.user = me.user_id;
        localStorage.setItem("brickmatch.user", state.user);
        return;
      } catch { localStorage.removeItem("brickmatch.auth_token"); }
    }
    const result = await new Promise((resolve) => {
      const dialog = document.createElement("dialog");
      dialog.className = "dialog";
      dialog.innerHTML = `<h2>Welcome to BrickMatch</h2>
        <p>Sign in to save your ratings and recommendations, or create an account.</p>
        <form><label class="field">Username<input name="username" autocomplete="username"
          pattern="[A-Za-z0-9_-]{1,80}" maxlength="80" required></label>
        <label class="field">Password<input name="password" type="password"
          autocomplete="current-password" minlength="10" maxlength="200" required></label>
        <p role="alert" class="fine-print"></p>
        <button class="btn btn-primary" type="submit" value="login">Sign in</button>
        <button class="btn" type="submit" value="register">Create account</button></form>`;
      dialog.addEventListener("cancel", (event) => event.preventDefault());
      dialog.querySelector("form").addEventListener("submit", async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        const buttons = Array.from(form.querySelectorAll("button"));
        const action = event.submitter?.value || "login";
        buttons.forEach((button) => { button.disabled = true; });
        try {
          const account = await api(`/auth/${action}`, { method: "POST", body: {
            user_id: form.elements.username.value, password: form.elements.password.value,
          } });
          dialog.close(); dialog.remove(); resolve(account);
        } catch (error) {
          form.querySelector('[role="alert"]').textContent = error.message;
        } finally { buttons.forEach((button) => { button.disabled = false; }); }
      });
      document.body.appendChild(dialog);
      dialog.showModal();
    });
    localStorage.setItem("brickmatch.auth_token", result.token);
    localStorage.setItem("brickmatch.user", result.user_id);
    state.user = result.user_id;
    state.users = [{ user_id: state.user, ratings: 0 }];
    state.boot.users = state.users;
    updateHeroStats();
    updateProfileChrome();
  }

  function updateHeroStats() {
    const boot = state.boot || {};
    const sets = $("#stat-sets");
    if (sets) sets.textContent = formatNumber(boot.catalog_count ?? 0);
    const images = $("#stat-images");
    if (images) images.textContent = formatNumber(boot.images_available ?? 0);
    const users = $("#stat-users");
    if (users) users.textContent = formatNumber((boot.users || []).length);
  }

  function renderThemeOptions() {
    const select = $("#filter-theme");
    if (!select) return;
    const current = state.discover.theme;
    select.innerHTML = `<option value="">All themes</option>` +
      state.themes.map((theme) => `<option value="${theme.theme_id}">${escapeHtml(theme.theme)} (${formatNumber(theme.count)})</option>`).join("");
    select.value = current || "";
  }

  /* ------------------------------------------------------------------ */
  /* Discover                                                            */
  /* ------------------------------------------------------------------ */

  function syncFilterInputs() {
    const d = state.discover;
    const q = $("#filter-q");
    if (q) q.value = d.q;
    const theme = $("#filter-theme");
    if (theme) theme.value = d.theme || "";
    const minYear = $("#filter-min-year");
    if (minYear) minYear.value = d.minYear;
    const maxYear = $("#filter-max-year");
    if (maxYear) maxYear.value = d.maxYear;
    const maxParts = $("#filter-max-parts");
    if (maxParts) maxParts.value = d.maxParts;
    const sort = $("#filter-sort");
    if (sort) sort.value = d.sort;
  }

  function readFilters() {
    const d = state.discover;
    d.q = ($("#filter-q")?.value || "").trim();
    d.theme = $("#filter-theme")?.value || "";
    d.minYear = clamp(parseInt($("#filter-min-year")?.value || "1949", 10) || 1949, 1949, 2200);
    d.maxYear = clamp(parseInt($("#filter-max-year")?.value || "2200", 10) || 2200, 1949, 2200);
    if (d.minYear > d.maxYear) [d.minYear, d.maxYear] = [d.maxYear, d.minYear];
    d.maxParts = clamp(parseInt($("#filter-max-parts")?.value || "100000", 10) || 0, 0, 100000);
    d.sort = $("#filter-sort")?.value || "set_id";
    syncFilterInputs();
  }

  function resetFilter(key) {
    const d = state.discover;
    if (key === "all") {
      d.q = ""; d.theme = ""; d.minYear = 1949; d.maxYear = 2200;
      d.maxParts = 100000; d.sort = "set_id";
    } else if (key === "q") d.q = "";
    else if (key === "theme") d.theme = "";
    else if (key === "minYear") d.minYear = 1949;
    else if (key === "maxYear") d.maxYear = 2200;
    else if (key === "maxParts") d.maxParts = 100000;
    else if (key === "sort") d.sort = "set_id";
    syncFilterInputs();
    loadDiscover(true);
  }

  function activeFilterChips() {
    const d = state.discover;
    const chips = [];
    if (d.q) chips.push(["q", `Search: ${d.q}`]);
    if (d.theme) {
      const match = state.themes.find((theme) => String(theme.theme_id) === String(d.theme));
      chips.push(["theme", `Theme: ${match ? match.theme : d.theme}`]);
    }
    if (d.minYear > 1949) chips.push(["minYear", `From ${d.minYear}`]);
    if (d.maxYear < 2200) chips.push(["maxYear", `To ${d.maxYear}`]);
    if (d.maxParts < 100000) chips.push(["maxParts", `≤ ${formatNumber(d.maxParts)} pieces`]);
    if (d.sort !== "set_id") {
      const label = $("#filter-sort")?.selectedOptions[0]?.textContent || d.sort;
      chips.push(["sort", `Sort: ${label}`]);
    }
    const wrap = $("#active-filters");
    if (!wrap) return;
    wrap.hidden = chips.length === 0;
    wrap.innerHTML = chips.map(([key, label]) => `<span class="chip">${escapeHtml(label)}
      <button type="button" data-clear="${key}" aria-label="Remove filter ${escapeHtml(label)}">
        ${icon("x")}</button></span>`).join("");
  }

  function updateCatalogCount() {
    const d = state.discover;
    const note = $("#catalog-count");
    if (note) {
      note.textContent = d.total
        ? `${formatNumber(d.total)} set${d.total === 1 ? "" : "s"} · showing ${formatNumber(d.items.length)}`
        : "No matching sets";
    }
    const loadMore = $("#load-more");
    if (loadMore) loadMore.hidden = d.items.length >= d.total || d.items.length === 0;
  }

  function renderDiscover(reset) {
    const d = state.discover;
    const grid = $("#discover-grid");
    if (!grid) return;
    if (d.error) {
      grid.innerHTML = errorState(d.error, "discover");
      updateCatalogCount();
      activeFilterChips();
      return;
    }
    if (!d.items.length) {
      const cta = `<button class="btn btn-ghost btn-sm" type="button" data-clear="all">Clear filters</button>`;
      grid.innerHTML = emptyState("No sets match those filters",
        "Try a wider year range, a different theme, or clear the search.", cta);
      updateCatalogCount();
      activeFilterChips();
      return;
    }
    const start = reset ? 0 : d.rendered;
    const html = d.items.slice(start).map((item) => setCardHtml(item)).join("");
    if (reset) grid.innerHTML = html;
    else grid.insertAdjacentHTML("beforeend", html);
    d.rendered = d.items.length;
    updateCatalogCount();
    activeFilterChips();
  }

  async function loadDiscover(reset) {
    const d = state.discover;
    if (!reset && d.loading) return;
    const token = ++discoverToken;
    d.loading = true;
    if (reset) {
      d.offset = 0;
      d.items = [];
      d.rendered = 0;
      d.error = null;
      const grid = $("#discover-grid");
      if (grid) grid.innerHTML = skeletonGrid(8);
      activeFilterChips();
    }
    const more = $("#load-more");
    if (!reset && more) { more.disabled = true; more.textContent = "Loading…"; }
    try {
      const params = new URLSearchParams({
        q: d.q,
        min_year: String(d.minYear),
        max_year: String(d.maxYear),
        max_parts: String(d.maxParts),
        sort: d.sort,
        offset: String(reset ? 0 : d.items.length),
        limit: String(d.limit),
      });
      if (d.theme) params.set("theme", d.theme);
      const data = await api(`/sets?${params.toString()}`);
      if (token !== discoverToken) return;
      d.items = reset ? (data.items || []) : d.items.concat(data.items || []);
      d.total = data.total || 0;
      d.offset = d.items.length;
      d.error = null;
      renderDiscover(reset);
    } catch (error) {
      if (token !== discoverToken) return;
      if (reset) {
        d.error = `${error.message}. API: ${API_BASE}`;
        renderDiscover(true);
      } else {
        toast(error.message, "error");
      }
    } finally {
      if (token === discoverToken) {
        d.loading = false;
        if (more) { more.disabled = false; more.textContent = "Load more sets"; }
        updateCatalogCount();
      }
    }
  }

  /* ------------------------------------------------------------------ */
  /* Feedback shared by cards                                            */
  /* ------------------------------------------------------------------ */

  function applyLocalFeedback(setId, action, item = null) {
    const existing = state.feedback.current.find((row) => row.set_id === setId);
    const set = item || existing?.set || state.discover.items.find((row) => row.set_id === setId) || null;
    state.feedback.current = state.feedback.current.filter((row) => row.set_id !== setId);
    if (action !== "undo") {
      state.feedback.current.push({
        user_id: state.user, set_id: setId, action, set,
        updated_at: new Date().toISOString(),
      });
    }
  }

  function refreshCardActions(card, setId) {
    if (!card) return;
    const action = feedbackAction(setId);
    $$(".action", card).forEach((button) => {
      const active = button.dataset.action === action;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
      if (button.dataset.action === "like") {
        const use = $("use", button);
        if (use) use.setAttribute("href", active ? "#i-heart-fill" : "#i-heart");
      }
    });
  }

  async function handleCardAction(button) {
    const setId = button.dataset.setId;
    const requested = button.dataset.action;
    const current = feedbackAction(setId);
    const action = current === requested ? "undo" : requested;
    const card = button.closest(".set-card");
    $$(".action", card || document.createElement("div")).forEach((node) => { node.disabled = true; });
    try {
      await api("/feedback", {
        method: "POST",
        body: { user_id: state.user, set_id: setId, action },
      });
      applyLocalFeedback(setId, action);
      refreshCardActions(card, setId);
      const name = $(".card-title", card || document.createElement("div"))?.textContent || setId;
      toast(action === "undo"
        ? `Rating removed for “${name}”.`
        : `${ACTION_LABELS[action]} “${name}”.`, "success");
    } catch (error) {
      toast(error.message, "error");
    } finally {
      $$(".action", card || document.createElement("div")).forEach((node) => { node.disabled = false; });
    }
  }

  async function undoRating(setId, button) {
    button.disabled = true;
    try {
      await api("/feedback", {
        method: "POST",
        body: { user_id: state.user, set_id: setId, action: "undo" },
      });
      applyLocalFeedback(setId, "undo");
      toast("Rating removed.", "success");
      await loadPreferences();
    } catch (error) {
      toast(error.message, "error");
      button.disabled = false;
    }
  }

  /* ------------------------------------------------------------------ */
  /* Swipe                                                               */
  /* ------------------------------------------------------------------ */

  async function fetchSwipeQueue() {
    const feedback = await api(`/users/${encodeURIComponent(state.user)}/feedback`);
    state.feedback.current = feedback.current || [];
    const rated = new Set(state.feedback.current.map((row) => row.set_id));
    const queue = [];
    let offset = 0;
    let total = 0;
    for (let page = 0; page < 6 && queue.length < 48; page += 1) {
      const data = await api(`/sets?limit=100&offset=${offset}&sort=set_id`);
      total = data.total || 0;
      queue.push(...(data.items || []).filter((item) => !rated.has(item.set_id)));
      offset += (data.items || []).length;
      if (!data.items || offset >= total) break;
    }
    state.swipe.queue = queue;
    state.swipe.total = total;
    state.swipe.error = null;
  }

  async function initSwipe() {
    if (state.swipe.queue.length || state.swipe.loading) {
      renderSwipe();
      return;
    }
    state.swipe.loading = true;
    state.swipe.error = null;
    renderSwipe();
    try {
      await fetchSwipeQueue();
    } catch (error) {
      state.swipe.error = `${error.message}. API: ${API_BASE}`;
    } finally {
      state.swipe.loading = false;
      renderSwipe();
    }
  }

  function swipeCardHtml(item) {
    if (!item) return "";
    const theme = item.theme || `Theme ${item.theme_id}`;
    return `<article class="swipe-card" data-set-id="${escapeHtml(item.set_id)}">
      <div class="card-media">${mediaHtml(item)}<span class="badge">${escapeHtml(theme)}</span></div>
      <div class="swipe-body">
        <h2>${escapeHtml(item.name)}</h2>
        <p class="card-meta"><strong>${escapeHtml(item.year)}</strong>
          · ${formatNumber(item.num_parts)} pieces · ${escapeHtml(item.set_id)}</p>
        <div class="swipe-tags">
          <span class="tag">${escapeHtml(theme)}</span>
          <span class="tag">${escapeHtml(item.year)}</span>
          <span class="tag">${formatNumber(item.num_parts)} pieces</span>
        </div>
      </div>
    </article>`;
  }

  function renderSwipe() {
    const stage = $("#swipe-stage");
    if (!stage) return;
    const controls = $("#swipe-controls");
    const bar = $("#swipe-bar");
    const progressText = $("#swipe-progress-text");
    const rated = state.feedback.current.length;
    const total = state.swipe.total || state.boot?.catalog_count || 0;
    const percent = total ? Math.min(100, (rated / total) * 100) : 0;
    if (bar) bar.style.width = `${percent}%`;
    if (progressText) progressText.textContent = total ? `${rated} of ${total} rated` : `${rated} rated`;

    if (state.swipe.error) {
      stage.innerHTML = errorState(state.swipe.error, "swipe");
      if (controls) controls.hidden = true;
      return;
    }
    if (state.swipe.loading) {
      stage.innerHTML = `<div class="skeleton-card" style="width:100%">
        <div class="sk sk-media"></div>
        <div class="sk-body"><div class="sk sk-line"></div><div class="sk sk-line short"></div>
        <div class="sk sk-line tiny"></div></div></div>`;
      if (controls) controls.hidden = true;
      return;
    }
    const item = state.swipe.queue[0];
    if (!item) {
      const cta = `<a class="btn btn-ghost btn-sm" href="#/preferences">Review my taste</a>`;
      stage.innerHTML = emptyState("You have rated every set",
        "Nothing left in the catalog for this profile. Undo a rating to bring a set back.", cta);
      if (controls) controls.hidden = true;
      return;
    }
    stage.innerHTML = swipeCardHtml(item);
    if (controls) controls.hidden = false;
  }

  async function swipeAction(action) {
    if (state.swipe.busy) return;
    const item = state.swipe.queue[0];
    if (!item) return;
    state.swipe.busy = true;
    const card = $("#swipe-stage .swipe-card");
    if (card) {
      card.classList.add(action === "like" ? "out-right" : action === "dislike" ? "out-left" : "out-down");
    }
    await sleep(200);
    try {
      await api("/feedback", {
        method: "POST",
        body: { user_id: state.user, set_id: item.set_id, action },
      });
      applyLocalFeedback(item.set_id, action, item);
      state.swipe.last = { item, action };
      state.swipe.queue.shift();
      toast(`${ACTION_LABELS[action]} “${item.name}”.`, "success");
    } catch (error) {
      toast(error.message, "error");
    } finally {
      state.swipe.busy = false;
      renderSwipe();
    }
  }

  async function undoSwipe() {
    const last = state.swipe.last;
    if (!last) {
      toast("No swipe to undo yet.", "info");
      return;
    }
    try {
      await api("/feedback", {
        method: "POST",
        body: { user_id: state.user, set_id: last.item.set_id, action: "undo" },
      });
      applyLocalFeedback(last.item.set_id, "undo");
      state.swipe.queue.unshift(last.item);
      state.swipe.last = null;
      toast(`Undid ${ACTION_LABELS[last.action].toLowerCase()} for “${last.item.name}”.`, "success");
    } catch (error) {
      toast(error.message, "error");
    }
    renderSwipe();
  }

  /* ------------------------------------------------------------------ */
  /* For You                                                             */
  /* ------------------------------------------------------------------ */

  function recommendationCard(row) {
    const item = row.set || state.discover.items.find((entry) => entry.set_id === row.set_id);
    if (!item) return "";
    const signals = row.signals || {};
    const labels = { metadata: "Metadata", visual: "Visual", classifier: "Classifier", catalog: "Catalog" };
    const bars = Object.keys(labels)
      .filter((name) => signals[name] !== undefined && Number.isFinite(Number(signals[name])))
      .map((name) => {
        const value = clamp(Number(signals[name]), 0, 1);
        return `<div class="signal ${name}"><span>${labels[name]}</span>
          <span class="track"><i style="width:${Math.round(value * 100)}%"></i></span>
          <b>${value.toFixed(2)}</b></div>`;
      }).join("");
    const explanations = (row.explanations || [])
      .map((text) => `<li>${escapeHtml(text)}</li>`).join("");
    const extra = bars
      ? `<div class="rec-panel"><div class="signals">${bars}</div>
         ${explanations ? `<ul class="explain">${explanations}</ul>` : ""}</div>`
      : "";
    return setCardHtml(item, { score: row.score, extraHtml: extra });
  }

  function renderRecommendationMeta(data) {
    const wrap = $("#for-you-meta");
    if (!wrap) return;
    const generated = data.generated_at ? new Date(data.generated_at) : null;
    const time = generated && !Number.isNaN(generated.getTime())
      ? generated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "";
    const pills = [
      `<span class="pill on"><span class="dot"></span>${escapeHtml(MODE_LABELS[data.mode] || data.mode || "unknown")}</span>`,
      `<span class="pill">model ${escapeHtml(data.model_version || "—")}</span>`,
      `<span class="pill">features ${escapeHtml(data.feature_version || "—")}</span>`,
      `<span class="pill">dataset ${escapeHtml(data.dataset_version || "—")}</span>`,
    ];
    if (time) pills.push(`<span class="pill">generated ${escapeHtml(time)}</span>`);
    wrap.innerHTML = pills.join("");
  }

  async function loadRecommendations() {
    const grid = $("#for-you-grid");
    if (!grid) return;
    grid.innerHTML = skeletonGrid(6);
    const meta = $("#for-you-meta");
    if (meta) meta.innerHTML = "";
    try {
      const data = await api(`/users/${encodeURIComponent(state.user)}/recommendations?k=12`);
      state.recommendations = data;
      renderRecommendationMeta(data);
      const cards = (data.items || []).map(recommendationCard).filter(Boolean);
      grid.innerHTML = cards.length
        ? cards.join("")
        : emptyState("No eligible sets remain",
            "Every catalog set has been rated. Undo a rating to bring sets back into the pool.",
            `<a class="btn btn-ghost btn-sm" href="#/preferences">Review my taste</a>`);
    } catch (error) {
      grid.innerHTML = errorState(`${error.message}. API: ${API_BASE}`, "for-you");
    }
  }

  /* ------------------------------------------------------------------ */
  /* Preferences                                                         */
  /* ------------------------------------------------------------------ */

  function renderPreferences() {
    const current = state.feedback.current;
    const counts = state.summary?.counts || { like: 0, dislike: 0, skip: 0 };
    const stats = $("#pref-stats");
    if (stats) {
      stats.innerHTML = [
        statTile(formatNumber(counts.like || 0), "Likes", "like"),
        statTile(formatNumber(counts.dislike || 0), "Dislikes", "dislike"),
        statTile(formatNumber(counts.skip || 0), "Skips", "skip"),
        statTile(formatNumber(current.length), "Stored ratings"),
      ].join("");
    }
    const count = $("#pref-count");
    if (count) count.textContent = `${formatNumber(current.length)} stored`;

    const themes = state.summary?.top_themes || [];
    const themeWrap = $("#pref-themes");
    if (themeWrap) {
      if (!themes.length) {
        themeWrap.innerHTML = `<p class="fine-print">Like a few sets and your theme mix will appear here.</p>`;
      } else {
        const max = Math.max(...themes.map((theme) => theme.count), 1);
        themeWrap.innerHTML = themes.map((theme) => `
          <div class="affinity">
            <span>${escapeHtml(theme.theme)}</span>
            <span class="count">${formatNumber(theme.count)} like${theme.count === 1 ? "" : "s"}</span>
            <div class="bar"><i style="width:${Math.round((theme.count / max) * 100)}%"></i></div>
          </div>`).join("");
      }
    }

    const list = $("#pref-list");
    if (!list) return;
    if (!current.length) {
      list.innerHTML = `<p class="fine-print">No ratings yet. Swipe or like a set to start your profile.</p>`;
      return;
    }
    const rows = [...current].sort((a, b) => String(b.updated_at || "").localeCompare(String(a.updated_at || "")));
    list.innerHTML = rows.map((row) => {
      const item = row.set || {};
      const name = item.name || row.set_id;
      const meta = [item.set_id || row.set_id, item.theme, item.year].filter(Boolean).join(" · ");
      const thumb = item.image_available
        ? `<img loading="lazy" src="${imageUrl(row.set_id)}" alt="${escapeHtml(name)}">`
        : icon("brick");
      return `<div class="rating-row">
        <div class="rating-thumb">${thumb}</div>
        <div><h3>${escapeHtml(name)}</h3><p>${escapeHtml(meta)}</p></div>
        <div class="rating-actions">
          <span class="action-chip ${escapeHtml(row.action)}">${escapeHtml(row.action)}</span>
          <button class="icon-btn" type="button" data-undo-set="${escapeHtml(row.set_id)}"
            aria-label="Undo rating for ${escapeHtml(name)}">${icon("undo")}</button>
        </div>
      </div>`;
    }).join("");
  }

  async function loadPreferences() {
    const list = $("#pref-list");
    if (list) list.innerHTML = `<div class="sk sk-line"></div><div class="sk sk-line"></div>`.repeat(3);
    try {
      const [feedback, summary] = await Promise.all([
        api(`/users/${encodeURIComponent(state.user)}/feedback`),
        api(`/users/${encodeURIComponent(state.user)}/summary`),
      ]);
      state.feedback.current = feedback.current || [];
      state.feedback.events = feedback.events || [];
      state.summary = summary;
      renderPreferences();
    } catch (error) {
      const themes = $("#pref-themes");
      if (themes) themes.innerHTML = "";
      if (list) list.innerHTML = errorState(`${error.message}. API: ${API_BASE}`, "preferences");
    }
  }

  /* ------------------------------------------------------------------ */
  /* Model Lab                                                           */
  /* ------------------------------------------------------------------ */

  const statusBadge = (on) => `<span class="badge-status ${on ? "on" : "off"}">${on ? "Active" : "Inactive"}</span>`;
  const valueRow = (label, value) => `<div class="value-row"><span>${escapeHtml(label)}</span><b>${value}</b></div>`;

  function renderModelLab(model, metrics, evaluation) {
    const modelWrap = $("#lab-model");
    if (modelWrap) {
      if (!model) {
        modelWrap.innerHTML = errorState("Model information is unavailable.", "model-lab");
      } else {
        const serving = [
          valueRow("Serving mode", escapeHtml(model.mode || "—")),
          valueRow("Classifier", statusBadge(Boolean(model.classifier_active))),
          valueRow("Visual features", statusBadge(Boolean(model.visual_features_active))),
          valueRow("Catalog", `${formatNumber(model.catalog_count)} sets`),
          valueRow("Local images", formatNumber(model.images_available)),
        ].join("");
        const identity = [
          valueRow("Model version", escapeHtml(model.model_version || "—")),
          valueRow("Feature version", escapeHtml(model.feature_version || "—")),
          valueRow("Dataset version", escapeHtml(model.dataset_version || "—")),
          valueRow("API base", escapeHtml(API_BASE)),
        ].join("");
        const runtime = [
          valueRow("Recommendation requests", formatNumber(metrics?.recommendation_requests ?? 0)),
          valueRow("Last latency", formatMs(metrics?.last_recommendation_ms)),
          valueRow("Profiles", formatNumber(state.users.length)),
          valueRow("Themes", formatNumber(state.themes.length)),
        ].join("");
        modelWrap.innerHTML = `
          <div class="model-tile"><h3>Serving</h3>${serving}</div>
          <div class="model-tile"><h3>Identity</h3>${identity}</div>
          <div class="model-tile"><h3>Runtime</h3>${runtime}</div>`;
      }
    }

    const metricsWrap = $("#lab-metrics");
    if (metricsWrap) {
      metricsWrap.innerHTML = [
        statTile(formatNumber(metrics?.recommendation_requests ?? 0), "Requests"),
        statTile(formatMs(metrics?.last_recommendation_ms), "Last latency"),
        statTile(formatNumber(state.users.length), "Local profiles"),
      ].join("");
    }

    const evalWrap = $("#lab-eval");
    if (!evalWrap) return;
    const payload = evaluation && evaluation.available ? evaluation.data : null;
    if (!payload || !Array.isArray(payload.rows) || !payload.rows.length) {
      evalWrap.innerHTML = emptyState("No measured evaluation available",
        "The offline evaluation report has not been generated for this build.");
      return;
    }
    const best = Math.max(...payload.rows.map((row) => Number(row.precision_at_10) || 0));
    const body = payload.rows.map((row) => {
      const isBest = (Number(row.precision_at_10) || 0) === best;
      return `<tr class="${isBest ? "best" : ""}">
        <td>${escapeHtml(row.approach)}</td>
        <td class="num">${Number(row.precision_at_10).toFixed(4)}</td>
        <td class="num">${Number(row.hit_rate_at_10).toFixed(4)}</td>
        <td class="num">${formatNumber(row.n)}</td>
      </tr>`;
    }).join("");
    const limitations = (payload.limitations || []).map((text) => `<li>${escapeHtml(text)}</li>`).join("");
    evalWrap.innerHTML = `
      <p class="fine-print">${formatNumber(payload.users)} profiles · ${formatNumber(payload.test_likes)}
        held-out likes · K = ${escapeHtml(payload.k)} · ${escapeHtml(payload.generated_at || "")}</p>
      <div class="table-wrap">
        <table class="eval">
          <thead><tr><th>Approach</th><th class="num">P@10</th><th class="num">HR@10</th><th class="num">n</th></tr></thead>
          <tbody>${body}</tbody>
        </table>
      </div>
      <div class="caveat">${icon("alert")}<div>
        <strong>Read with care.</strong>
        ${payload.simulated_personas ? " These results come from simulated theme-based personas, not real consented users." : ""}
        ${limitations ? `<ul>${limitations}</ul>` : ""}
      </div></div>`;
  }

  async function loadModelLab() {
    const modelWrap = $("#lab-model");
    if (modelWrap) modelWrap.innerHTML = skeletonGrid(3);
    const safe = async (path) => {
      try { return await api(path); } catch { return null; }
    };
    const [model, metrics, evaluation] = await Promise.all([
      safe("/models/current"), safe("/metrics"), safe("/evaluation"),
    ]);
    state.model = model || state.model;
    state.evaluation = evaluation?.data || state.evaluation;
    renderModelLab(model, metrics, evaluation);
  }

  /* ------------------------------------------------------------------ */
  /* System                                                              */
  /* ------------------------------------------------------------------ */

  function renderSystem(results) {
    const statusWrap = $("#sys-status");
    if (statusWrap) {
      statusWrap.innerHTML = [
        statTile(results.live ? "Live" : "Down", "Liveness", results.live ? "ok" : "bad"),
        statTile(results.ready ? "Ready" : "Down", "Readiness", results.ready ? "ok" : "bad"),
        statTile(formatMs(results.latency), "API round-trip", ""),
      ].join("");
    }
    const details = $("#sys-details");
    if (details) {
      const model = results.model || {};
      const boot = state.boot || {};
      const rows = [
        ["Dataset version", boot.dataset_version || model.dataset_version || "—"],
        ["Catalog sets", formatNumber(boot.catalog_count ?? model.catalog_count ?? 0)],
        ["Local images", formatNumber(boot.images_available ?? model.images_available ?? 0)],
        ["Themes", formatNumber(state.themes.length)],
        ["Model version", model.model_version || "—"],
        ["Feature version", model.feature_version || "—"],
        ["Profiles", formatNumber(state.users.length)],
        ["API base", API_BASE],
      ];
      details.innerHTML = rows.map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`).join("");
    }
    const endpoints = $("#sys-endpoints");
    if (endpoints) {
      const rows = [
        ["GET", "/api/v1/health/live"], ["GET", "/api/v1/health/ready"],
        ["GET", "/api/v1/bootstrap"], ["GET", "/api/v1/sets"],
        ["GET", "/api/v1/users/{user_id}/recommendations"],
        ["POST", "/api/v1/feedback"], ["GET", "/api/v1/models/current"],
        ["GET", "/api/v1/evaluation"], ["GET", "/api/v1/metrics"],
      ];
      endpoints.innerHTML = rows.map(([method, path]) => `<li>
        <span class="method ${method === "POST" ? "post" : ""}">${method}</span>
        <code>${escapeHtml(path)}</code></li>`).join("");
    }
  }

  async function loadSystem() {
    const started = performance.now();
    const safe = async (path) => {
      try { return await api(path); } catch { return null; }
    };
    const [live, ready, model] = await Promise.all([
      safe("/health/live"), safe("/health/ready"), safe("/models/current"),
    ]);
    const latency = performance.now() - started;
    renderSystem({
      live: Boolean(live && live.status === "live"),
      ready: Boolean(ready && ready.status === "ready"),
      model,
      latency,
    });
  }

  /* ------------------------------------------------------------------ */
  /* Routing                                                             */
  /* ------------------------------------------------------------------ */

  function currentRoute() {
    const raw = (location.hash || "").replace(/^#\/?/, "").split("?")[0].trim();
    return ROUTES.includes(raw) ? raw : "discover";
  }

  function navigate() {
    const hash = location.hash || "";
    const route = currentRoute();
    if (route === "discover" && hash && !hash.startsWith("#/")) {
      // In-page anchor such as #catalog: let the browser keep its scroll position.
      return;
    }
    state.route = route;
    $$(".page[data-page]").forEach((page) => { page.hidden = page.dataset.page !== route; });
    $$(".nav-link").forEach((link) => link.classList.toggle("active", link.dataset.route === route));
    document.title = `${TITLES[route]} — BrickMatch AI`;
    window.scrollTo(0, 0);
    if (route === "discover") { syncFilterInputs(); loadDiscover(true); }
    else if (route === "swipe") initSwipe();
    else if (route === "for-you") loadRecommendations();
    else if (route === "preferences") loadPreferences();
    else if (route === "model-lab") loadModelLab();
    else if (route === "system") loadSystem();
  }

  function retryLoad(target) {
    if (target === "discover") loadDiscover(true);
    else if (target === "swipe") { state.swipe.error = null; state.swipe.queue = []; initSwipe(); }
    else if (target === "for-you") loadRecommendations();
    else if (target === "preferences") loadPreferences();
    else if (target === "model-lab") loadModelLab();
    else if (target === "system") loadSystem();
  }

  /* ------------------------------------------------------------------ */
  /* Event wiring                                                        */
  /* ------------------------------------------------------------------ */

  function bindEvents() {
    window.addEventListener("hashchange", () => navigate());

    $("#profile-button")?.addEventListener("click", openProfileDialog);
    $("#profile-dialog")?.addEventListener("close", () => {
      $("#profile-button").setAttribute("aria-expanded", "false");
    });
    $("#profile-dialog")?.addEventListener("click", (event) => {
      if (event.target === event.currentTarget) closeProfileDialog();
    });
    $("#new-profile-form")?.addEventListener("submit", (event) => {
      event.preventDefault();
      const input = $("#new-profile-name");
      const name = (input?.value || "").trim();
      if (!USER_PATTERN.test(name)) {
        toast("Use only letters, digits, underscore or hyphen (max 80).", "error");
        input?.focus();
        return;
      }
      if (!state.users.some((row) => row.user_id === name)) {
        state.users.push({ user_id: name, ratings: 0 });
      }
      if (input) input.value = "";
      switchUser(name);
    });

    $("#filters")?.addEventListener("submit", (event) => {
      event.preventDefault();
      readFilters();
      loadDiscover(true);
    });
    $("#filter-q")?.addEventListener("input", () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => { readFilters(); loadDiscover(true); }, 320);
    });
    ["#filter-theme", "#filter-min-year", "#filter-max-year", "#filter-max-parts", "#filter-sort"]
      .forEach((selector) => {
        $(selector)?.addEventListener("change", () => { readFilters(); loadDiscover(true); });
      });
    $("#filter-reset")?.addEventListener("click", () => resetFilter("all"));
    $("#load-more")?.addEventListener("click", () => loadDiscover(false));

    $("#for-you-refresh")?.addEventListener("click", loadRecommendations);
    $("#swipe-undo")?.addEventListener("click", undoSwipe);

    document.addEventListener("click", (event) => {
      const profile = event.target.closest("[data-profile]");
      if (profile) { switchUser(profile.dataset.profile); return; }
      const undo = event.target.closest("[data-undo-set]");
      if (undo) { undoRating(undo.dataset.undoSet, undo); return; }
      const clear = event.target.closest("[data-clear]");
      if (clear) { resetFilter(clear.dataset.clear); return; }
      const retry = event.target.closest("[data-retry]");
      if (retry) { retryLoad(retry.dataset.retry); return; }
      const swipe = event.target.closest("[data-swipe]");
      if (swipe) { swipeAction(swipe.dataset.swipe); return; }
      const action = event.target.closest("[data-action][data-set-id]");
      if (action && !action.closest("#swipe-stage")) { handleCardAction(action); }
    });

    document.addEventListener("error", (event) => {
      const image = event.target;
      if (!(image instanceof HTMLImageElement) || image.dataset.fallback === "done") return;
      image.dataset.fallback = "done";
      const host = image.closest(".card-media") || image.closest(".rating-thumb");
      if (host) host.innerHTML = `<span class="placeholder">${icon("brick")}</span>`;
    }, true);

    document.addEventListener("keydown", (event) => {
      if (event.defaultPrevented) return;
      if (state.route !== "swipe") return;
      const tag = (event.target.tagName || "").toLowerCase();
      if (["input", "select", "textarea"].includes(tag) || event.target.isContentEditable) return;
      if (event.key === "ArrowLeft") { event.preventDefault(); swipeAction("dislike"); }
      else if (event.key === "ArrowDown") { event.preventDefault(); swipeAction("skip"); }
      else if (event.key === "ArrowRight") { event.preventDefault(); swipeAction("like"); }
      else if (event.key.toLowerCase() === "u") { event.preventDefault(); undoSwipe(); }
    });
  }

  /* ------------------------------------------------------------------ */
  /* Boot                                                                */
  /* ------------------------------------------------------------------ */

  function fixDocLinks() {
    $$('a[href="/docs"]').forEach((anchor) => { anchor.href = `${docBase}/docs`; });
    $$('a[href^="/api/v1/"]').forEach((anchor) => {
      const suffix = anchor.getAttribute("href").slice("/api/v1".length);
      anchor.href = `${API_BASE}${suffix}`;
    });
  }

  async function boot() {
    const stored = localStorage.getItem("brickmatch.user");
    state.user = stored && USER_PATTERN.test(stored) ? stored : "builder";
    updateProfileChrome();
    bindEvents();
    fixDocLinks();
    try {
      await loadBootstrap();
      await authenticateIfRequired();
    } catch (error) {
      state.bootstrapError = error.message;
      toast(`Could not finish loading: ${error.message}`, "error");
    }
    if (!location.hash) {
      history.replaceState(null, "", "#/discover");
    }
    navigate(true);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();

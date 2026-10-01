const ICONS = {
  Tomato: "🍅",
  Pepper: "🌶️",
  Basil: "🌿",
  Bean: "🫘",
  Corn: "🌽",
  Zucchini: "🥒",
  Cucumber: "🥒",
  Lettuce: "🥬",
  Spinach: "🌱",
  Kale: "🥬",
  Broccoli: "🥦",
  Cabbage: "🥬",
  Carrot: "🥕",
  Pea: "🟢",
  Potato: "🥔",
  Radish: "🌸",
  Onion: "🧅",
  Marigold: "🌼",
  Chamomile: "🌼",
  Nasturtium: "🌺",
  Thyme: "🌿",
  Dill: "🌿",
  Rosemary: "🌿",
  Oregano: "🌿",
  Borage: "💠",
  Lavender: "💜",
  Mint: "🌱",
};

const state = {
  garden: null,
  plants: [],
  plantings: [],
  forecast: null,
  frost: null,
  view: "today",
  status: "",
  editing: null,
  pageEdit: false,
  editSnapshot: null,
  setupStep: 1,
  setupPlaces: [],
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json();
  if (!data.ok) {
    const err = new Error(data.hint || data.error || "Something went wrong");
    err.payload = data;
    throw err;
  }
  return data;
}

function fmtDate(iso) {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function weekday(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", { weekday: "short" });
}

function showAlert(message, show = true) {
  const el = $("alert");
  el.hidden = !show;
  el.textContent = message || "";
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function frostCopy(g) {
  const days = g.days_until_fall_frost;
  if (days > 0) return `${days} days until the usual first fall frost.`;
  if (days === 0) return "Average first fall frost is today.";
  return `${Math.abs(days)} days past the usual first fall frost.`;
}

function syncEditChrome() {
  const editing = state.pageEdit;
  document.body.classList.toggle("is-page-edit", editing);
  $("edit-toggle").textContent = editing ? "Save" : "Edit";
  $("edit-toggle").classList.toggle("primary", editing);
  $("edit-toggle").classList.toggle("ghost", !editing);
  $("edit-cancel").hidden = !editing;
  $("plot-read").hidden = editing;
  $("plot-form").hidden = !editing;
}

function cloneRow(row) {
  return { ...row };
}

function plantingChanged(before, after) {
  const norm = (value) => (value == null ? "" : String(value));
  return (
    before.plant_name !== after.plant_name ||
    norm(before.variety) !== norm(after.variety) ||
    before.planted_on !== after.planted_on ||
    norm(before.bed) !== norm(after.bed) ||
    norm(before.quantity) !== norm(after.quantity) ||
    before.status !== after.status ||
    norm(before.notes) !== norm(after.notes)
  );
}

function applyDraftsToState() {
  const form = $("plot-form");
  if (state.garden && form) {
    const threshold = form.frost_threshold_f.value;
    state.garden = {
      ...state.garden,
      place: form.place.value,
      aspect: form.aspect.value,
      sun: form.sun.value,
      last_spring_frost: form.last_spring_frost.value,
      first_fall_frost: form.first_fall_frost.value,
      frost_threshold_f: threshold === "" ? state.garden.frost_threshold_f : Number(threshold),
    };
  }
  for (const [id, payload] of collectPlantingDrafts()) {
    const idx = state.plantings.findIndex((p) => String(p.id) === String(id));
    if (idx < 0) continue;
    const quantity = payload.quantity === "" || payload.quantity == null ? null : Number(payload.quantity);
    state.plantings[idx] = {
      ...state.plantings[idx],
      plant_name: payload.plant_name,
      variety: payload.variety || null,
      planted_on: payload.planted_on,
      bed: payload.bed || null,
      quantity: Number.isFinite(quantity) ? quantity : null,
      status: payload.status,
      notes: payload.notes || null,
    };
  }
}

function setPageEdit(on) {
  if (on) {
    state.editSnapshot = state.plantings.map(cloneRow);
    if (state.view === "catalog") {
      state.view = "today";
      document.querySelectorAll(".nav-btn").forEach((btn) => {
        btn.classList.toggle("is-active", btn.dataset.view === "today");
      });
      document.querySelectorAll(".view").forEach((view) => {
        view.classList.toggle("is-visible", view.id === "view-today");
      });
      $("page-title").textContent = "Today in the beds";
    }
  } else {
    state.editSnapshot = null;
  }
  state.pageEdit = on;
  syncEditChrome();
  renderSeason();
  renderPlantings();
}

function renderSeason() {
  const g = state.garden;
  if (!g) return;
  $("season-kicker").textContent = `${g.place} · ${g.aspect || g.season}`;
  const rail = $("rail-place");
  if (rail) rail.textContent = g.place || "Home garden";
  $("plot-season").textContent = g.season;
  $("frost-countdown").textContent = frostCopy(g);
  $("plot-read").innerHTML = `
    <h3 class="plot-season">${esc(g.season)}</h3>
    <p>${esc(g.sun || "")} ${esc(frostCopy(g))}</p>
    <div class="stat-row">
      <div class="stat"><span class="muted">Last spring frost</span><b>${fmtDate(g.last_spring_frost)}</b></div>
      <div class="stat"><span class="muted">First fall frost</span><b>${fmtDate(g.first_fall_frost)}</b></div>
      <div class="stat"><span class="muted">Garden frost</span><b>${g.frost_threshold_f}°F</b></div>
    </div>
  `;
  const form = $("plot-form");
  form.place.value = g.place || "";
  form.aspect.value = g.aspect || "";
  form.sun.value = g.sun || "";
  form.last_spring_frost.value = g.last_spring_frost || "";
  form.first_fall_frost.value = g.first_fall_frost || "";
  form.frost_threshold_f.value = g.frost_threshold_f ?? "";
}

function setView(name) {
  if (state.pageEdit) applyDraftsToState();
  state.view = name;
  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.view === name);
  });
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("is-visible", view.id === `view-${name}`);
  });
  const titles = {
    today: "Today in the beds",
    beds: "What you have growing",
    catalog: "The kitchen catalog",
  };
  $("page-title").textContent = titles[name];
  if (state.pageEdit) renderPlantings();
}

function renderForecast() {
  const wrap = $("forecast-strip");
  const days = state.forecast?.days || [];
  $("forecast-meta").textContent = days.length ? "Lows and highs in Fahrenheit" : "";
  if (!days.length) {
    wrap.innerHTML = `<p class="empty">Weather is taking a rest. Try again in a moment.</p>`;
    return;
  }
  const lows = days.map((d) => d.low_f);
  const highs = days.map((d) => d.high_f);
  const min = Math.min(...lows) - 4;
  const max = Math.max(...highs) + 4;
  const span = Math.max(max - min, 1);
  wrap.innerHTML = days
    .map((day) => {
      const frost = day.low_f <= 32;
      const bottom = ((day.low_f - min) / span) * 100;
      const height = Math.max(((day.high_f - day.low_f) / span) * 100, 10);
      return `
        <div class="day ${frost ? "is-frost" : ""}">
          <div class="wd">${weekday(day.date)}</div>
          <div class="track"><div class="bar" style="bottom:${bottom}%;height:${height}%"></div></div>
          <div class="temps">
            <div class="hi">${Math.round(day.high_f)}°</div>
            <div class="lo">${Math.round(day.low_f)}°</div>
          </div>
        </div>`;
    })
    .join("");
}

function renderFrost() {
  const card = $("frost-card");
  const frost = state.frost;
  if (!frost) return;
  const nights = frost.frost_nights || [];
  const risk = frost.at_risk || [];
  card.classList.toggle("is-alert", nights.length > 0 || risk.length > 0);
  if (!nights.length && !risk.length) {
    $("frost-body").innerHTML = `
      <h3>Nights look kind</h3>
      <p>No garden-wide frost in the next ${frost.n_days} days. ${frost.n_plantings} planting${frost.n_plantings === 1 ? "" : "s"} checked.</p>
    `;
    return;
  }
  const nightList = nights.map((n) => `${fmtDate(n.date)} · ${n.low_f}°F`).join("<br>");
  const riskList = risk
    .map((r) => `${r.plant_name} on ${fmtDate(r.date)} (${r.low_f}°F, hurt at ${r.damage_at_or_below_f}°F)`)
    .join("<br>");
  $("frost-body").innerHTML = `
    <h3>${nights.length ? "Cover the tender things" : "Watch the beds"}</h3>
    <p>${nightList || "No night at or below 32°F, but a planting is near its limit."}</p>
    ${risk.length ? `<p class="muted">${riskList}</p>` : ""}
  `;
}

function plantOptions(selected) {
  return state.plants
    .map(
      (plant) =>
        `<option value="${esc(plant.name)}" ${plant.name === selected ? "selected" : ""}>${esc(plant.name)}</option>`
    )
    .join("");
}

function statusOptions(selected) {
  return ["planted", "planned", "harvested", "failed"]
    .map((status) => `<option value="${status}" ${status === selected ? "selected" : ""}>${status}</option>`)
    .join("");
}

function plantingCard(row, editable = state.pageEdit) {
  const icon = ICONS[row.plant_name] || "🌿";
  if (!editable) {
    return `
      <article class="card">
        <div class="glyph">${icon}</div>
        <h3>${esc(row.plant_name)}</h3>
        <p class="muted">${esc(row.variety || "Open-pollinated mix")} · ${fmtDate(row.planted_on)}</p>
        <p class="muted">${esc(row.bed || "Unassigned bed")}${row.quantity ? ` · ${row.quantity}` : ""}</p>
        ${row.notes ? `<p class="muted note">${esc(row.notes)}</p>` : ""}
        <span class="badge ${row.status}">${esc(row.status)}</span>
        <span class="badge ${row.hardiness}">ok to ${row.min_temp_f}°F</span>
      </article>
    `;
  }
  return `
    <form class="card card-edit" data-planting-id="${row.id}">
      <div class="card-top">
        <div class="glyph">${icon}</div>
        <select name="plant_name" class="inline title-input" aria-label="Plant">${plantOptions(row.plant_name)}</select>
      </div>
      <label>Variety
        <input name="variety" class="inline" type="text" value="${esc(row.variety || "")}" placeholder="Variety">
      </label>
      <label>Date planted
        <input name="planted_on" class="inline" type="text" value="${esc(row.planted_on || "")}" placeholder="May 1, 2026">
      </label>
      <div class="split">
        <label>Bed
          <input name="bed" class="inline" type="text" value="${esc(row.bed || "")}" placeholder="Unassigned bed">
        </label>
        <label>Quantity
          <input name="quantity" class="inline" type="number" min="1" step="1" value="${esc(row.quantity ?? "")}">
        </label>
      </div>
      <label>Status
        <select name="status" class="inline">${statusOptions(row.status)}</select>
      </label>
      <label>Notes
        <textarea name="notes" class="inline" rows="2" placeholder="Companions, spacing…">${esc(row.notes || "")}</textarea>
      </label>
      <p class="muted note hardiness-hint">Nights to ${row.min_temp_f}°F · ${row.hardiness}</p>
    </form>
  `;
}

function groupByBed(rows) {
  const groups = new Map();
  for (const row of rows) {
    const key = row.bed || "Unassigned bed";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  }
  return groups;
}

function bedSections(rows, editable = state.pageEdit) {
  return [...groupByBed(rows).entries()]
    .map(([bed, group]) => {
      const title = editable
        ? `<input class="bed-title-input" data-bed-from="${esc(bed)}" value="${esc(bed)}" aria-label="Bed name">`
        : `<h3 class="bed-title">${esc(bed)}</h3>`;
      return `
        <section class="bed-group">
          ${title}
          <div class="planting-grid">${group.map((row) => plantingCard(row, editable)).join("")}</div>
        </section>`;
    })
    .join("");
}

function glanceSections(rows) {
  return [...groupByBed(rows).entries()]
    .map(
      ([bed, group]) => `
        <article class="bed-summary">
          <h3>${esc(bed)}</h3>
          <p class="muted">${group
            .map((r) => (r.variety ? `${esc(r.plant_name)} (${esc(r.variety)})` : esc(r.plant_name)))
            .join(" · ")}</p>
        </article>`
    )
    .join("");
}

function renderPlantings() {
  const today = $("today-plantings");
  const beds = $("beds-grid");
  const active = state.plantings.filter((p) => p.status === "planned" || p.status === "planted");
  const filtered = state.status
    ? state.plantings.filter((p) => p.status === state.status)
    : state.plantings;
  const editToday = state.pageEdit && state.view === "today";
  const editBeds = state.pageEdit && state.view === "beds";
  today.className = editToday ? "beds-stack" : "bed-summaries";
  today.innerHTML = active.length
    ? editToday
      ? bedSections(active, true)
      : glanceSections(active)
    : `<p class="empty">Nothing in the ground yet. Log your first planting.</p>`;
  beds.innerHTML = filtered.length
    ? bedSections(filtered, editBeds)
    : `<p class="empty">No plantings for this filter.</p>`;
}

function renderCatalog() {
  $("catalog-grid").innerHTML = state.plants
    .map((plant) => {
      const icon = ICONS[plant.name] || "🌿";
      return `
        <button class="cat" type="button" data-plant="${plant.name}">
          <div class="glyph">${icon}</div>
          <h3>${plant.name}</h3>
          <p class="muted">${plant.days_to_maturity} days · nights to ${plant.min_temp_f}°F</p>
          <span class="badge ${plant.hardiness}">${plant.hardiness}</span>
        </button>`;
    })
    .join("");
}

function renderPlantPicker(selected) {
  $("plant-picker").innerHTML = state.plants
    .map((plant) => {
      const on = selected === plant.name ? "is-on" : "";
      return `<button class="pick ${on}" type="button" data-pick="${plant.name}">${ICONS[plant.name] || "🌿"} ${plant.name}</button>`;
    })
    .join("");
}

function openDrawer(planting = null) {
  state.editing = planting;
  const form = $("planting-form");
  form.reset();
  $("form-error").hidden = true;
  $("harvest-field").hidden = !planting;
  $("drawer-kicker").textContent = planting ? "Edit entry" : "New entry";
  $("drawer-title").textContent = planting ? `Update ${planting.plant_name}` : "Log a planting";
  renderPlantPicker(planting?.plant_name);
  form.plant_name.value = planting?.plant_name || "";
  form.planted_on.value = planting?.planted_on || "";
  form.variety.value = planting?.variety || "";
  form.quantity.value = planting?.quantity || "";
  form.bed.value = planting?.bed || "";
  form.status.value = planting?.status || "planted";
  form.notes.value = planting?.notes || "";
  form.harvested_on.value = planting?.harvested_on || "";
  form.id.value = planting?.id || "";
  $("drawer").hidden = false;
  $("drawer-backdrop").hidden = false;
}

function closeDrawer() {
  $("drawer").hidden = true;
  $("drawer-backdrop").hidden = true;
  state.editing = null;
}

async function showWindow(plantName) {
  const card = $("window-card");
  card.hidden = false;
  $("window-title").textContent = plantName;
  $("window-body").textContent = "Finding the window…";
  try {
    const data = await api(`/api/window?plant=${encodeURIComponent(plantName)}`);
    $("window-body").innerHTML = `
      <div class="timeline">
        <div><span class="muted">Plant in spring</span><b>${fmtDate(data.plant_in_spring)}</b></div>
        <div><span class="muted">Last fall sowing</span><b>${fmtDate(data.last_fall_planting)}</b></div>
        <div><span class="muted">Last spring frost</span><b>${fmtDate(data.last_spring_frost)}</b></div>
        <div><span class="muted">First fall frost</span><b>${fmtDate(data.first_fall_frost)}</b></div>
      </div>
      <p class="muted">${data.hardiness} · ${data.days_to_maturity} days to maturity · nights to ${data.min_temp_f}°F</p>
    `;
  } catch (err) {
    $("window-body").textContent = err.message;
  }
}

async function savePlot() {
  if (!state.garden) return;
  const form = $("plot-form");
  const garden = await api("/api/garden", {
    method: "PATCH",
    body: JSON.stringify(Object.fromEntries(new FormData(form).entries())),
  });
  state.garden = garden;
}

function collectPlantingDrafts() {
  document.querySelectorAll(".bed-group").forEach((group) => {
    const title = group.querySelector(".bed-title-input");
    if (!title) return;
    const next = title.value.trim() || "Unassigned bed";
    if (next === title.dataset.bedFrom) return;
    const dest = next === "Unassigned bed" ? "" : next;
    group.querySelectorAll("input[name=bed]").forEach((input) => {
      input.value = dest;
    });
  });
  const byId = new Map();
  document.querySelectorAll("form.card-edit").forEach((form) => {
    const id = form.dataset.plantingId;
    if (!byId.has(id)) byId.set(id, Object.fromEntries(new FormData(form).entries()));
  });
  document.querySelector(".view.is-visible")?.querySelectorAll("form.card-edit").forEach((form) => {
    byId.set(form.dataset.plantingId, Object.fromEntries(new FormData(form).entries()));
  });
  return byId;
}

async function saveAllEdits() {
  const btn = $("edit-toggle");
  btn.disabled = true;
  try {
    showAlert("", false);
    applyDraftsToState();
    await savePlot();
    const original = new Map((state.editSnapshot || []).map((row) => [row.id, row]));
    for (const row of state.plantings) {
      const prev = original.get(row.id);
      if (prev && !plantingChanged(prev, row)) continue;
      await api(`/api/plantings/${row.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          plant_name: row.plant_name,
          variety: row.variety || "",
          planted_on: row.planted_on,
          bed: row.bed || "",
          quantity: row.quantity ?? "",
          status: row.status,
          notes: row.notes || "",
        }),
      });
    }
    state.pageEdit = false;
    state.editSnapshot = null;
    await refresh();
  } catch (err) {
    showAlert(err.message);
  } finally {
    btn.disabled = false;
  }
}

async function cancelEdits() {
  state.pageEdit = false;
  state.editSnapshot = null;
  await refresh();
}

async function refresh() {
  showAlert("", false);
  try {
    const garden = await api("/api/garden");
    if (garden.needs_setup) {
      await openSetup();
      return;
    }
    const [plants, plantings, forecast, frost] = await Promise.all([
      api("/api/plants"),
      api("/api/plantings"),
      api("/api/forecast?days=7"),
      api("/api/frost?days=7"),
    ]);
    state.garden = garden;
    state.plants = plants.plants;
    state.plantings = plantings.plantings;
    state.forecast = forecast;
    state.frost = frost;
    renderSeason();
    renderForecast();
    renderFrost();
    renderPlantings();
    renderCatalog();
    syncEditChrome();
  } catch (err) {
    showAlert(err.message);
  }
}

function setupPlantOptions() {
  return state.plants
    .map((plant) => `<option value="${esc(plant.name)}">${esc(plant.name)}</option>`)
    .join("");
}

function addSetupPlantingRow() {
  const wrap = $("setup-plantings");
  const row = document.createElement("div");
  row.className = "setup-row";
  row.innerHTML = `
    <select name="plant_name" aria-label="Plant">${setupPlantOptions()}</select>
    <input name="variety" type="text" placeholder="Variety">
    <input name="bed" type="text" placeholder="Bed or container">
    <input name="planted_on" type="text" placeholder="Date planted, e.g. May 1, 2026">
    <div class="split">
      <input name="quantity" type="number" min="1" step="1" placeholder="Qty">
      <select name="status">
        <option value="planted">Planted</option>
        <option value="planned">Planned</option>
      </select>
    </div>
    <input name="notes" type="text" placeholder="Notes">
  `;
  wrap.appendChild(row);
}

function showSetupStep(step) {
  state.setupStep = step;
  document.querySelectorAll("[data-setup-step]").forEach((el) => {
    el.hidden = Number(el.dataset.setupStep) !== step;
  });
  $("setup-back").hidden = step === 1;
  $("setup-next").textContent = step === 3 ? "Save my garden" : "Next";
  const copy = {
    1: ["Where is your garden?", "Weather and frost dates stay on this computer. Search a city or ZIP, then tell us about the beds."],
    2: ["Describe the plot", "Name, sun, and typical frost dates. Guess is fine — you can edit later."],
    3: ["What is growing?", "One row per planting. Skip this if the beds are empty."],
  };
  $("setup-title").textContent = copy[step][0];
  $("setup-lede").textContent = copy[step][1];
}

async function openSetup() {
  $("setup-overlay").hidden = false;
  const status = await api("/api/setup");
  state.plants = (status.plants || []).map((name) => ({ name }));
  if (!$("setup-plantings").children.length) addSetupPlantingRow();
  showSetupStep(1);
}

async function searchSetupPlaces() {
  const query = $("setup-query").value.trim();
  $("setup-error").hidden = true;
  if (!query) {
    $("setup-error").hidden = false;
    $("setup-error").textContent = "Enter a city, town, or ZIP first.";
    return;
  }
  try {
    const data = await api(`/api/places?q=${encodeURIComponent(query)}`);
    $("setup-places").innerHTML = data.places
      .map(
        (place, i) =>
          `<button class="place-pick" type="button" data-place-index="${i}">${esc(place.label)}</button>`
      )
      .join("");
    state.setupPlaces = data.places;
  } catch (err) {
    $("setup-error").hidden = false;
    $("setup-error").textContent = err.message;
  }
}

function pickSetupPlace(index) {
  const place = state.setupPlaces[index];
  if (!place) return;
  const form = $("setup-form");
  form.latitude.value = place.latitude;
  form.longitude.value = place.longitude;
  form.timezone.value = place.timezone;
  if (!form.place.value) form.place.value = place.name;
  if (!form.last_spring_frost.value) form.last_spring_frost.value = place.last_spring || "";
  if (!form.first_fall_frost.value) form.first_fall_frost.value = place.first_fall || "";
  $("setup-picked").textContent = `Using ${place.label} (${place.timezone}).`;
  document.querySelectorAll(".place-pick").forEach((btn, i) => {
    btn.classList.toggle("is-on", i === index);
  });
}

function collectSetupPlantings() {
  return [...$("setup-plantings").querySelectorAll(".setup-row")]
    .map((row) => {
      const planted = row.querySelector("[name=planted_on]").value.trim();
      const plantName = row.querySelector("[name=plant_name]").value;
      if (!planted || !plantName) return null;
      return {
        plant_name: plantName,
        variety: row.querySelector("[name=variety]").value,
        bed: row.querySelector("[name=bed]").value,
        planted_on: planted,
        quantity: row.querySelector("[name=quantity]").value,
        status: row.querySelector("[name=status]").value,
        notes: row.querySelector("[name=notes]").value,
      };
    })
    .filter(Boolean);
}

async function advanceSetup() {
  $("setup-error").hidden = true;
  const form = $("setup-form");
  if (state.setupStep === 1) {
    if (!form.latitude.value || !form.longitude.value) {
      $("setup-error").hidden = false;
      $("setup-error").textContent = "Search and pick your place so weather knows where to look.";
      return;
    }
    showSetupStep(2);
    return;
  }
  if (state.setupStep === 2) {
    if (!form.place.value.trim()) {
      $("setup-error").hidden = false;
      $("setup-error").textContent = "Give the garden a name, even a short one.";
      return;
    }
    showSetupStep(3);
    return;
  }
  try {
    await api("/api/setup", {
      method: "POST",
      body: JSON.stringify({
        latitude: form.latitude.value,
        longitude: form.longitude.value,
        timezone: form.timezone.value,
        place: form.place.value,
        aspect: form.aspect.value,
        sun: form.sun.value,
        last_spring_frost: form.last_spring_frost.value,
        first_fall_frost: form.first_fall_frost.value,
        frost_threshold_f: form.frost_threshold_f.value,
        plantings: collectSetupPlantings(),
      }),
    });
    $("setup-overlay").hidden = true;
    await refresh();
  } catch (err) {
    $("setup-error").hidden = false;
    $("setup-error").textContent = err.message;
  }
}

function bind() {
  document.querySelectorAll("[data-view]").forEach((btn) => {
    btn.addEventListener("click", () => setView(btn.dataset.view));
  });
  $("add-open").addEventListener("click", () => openDrawer());
  $("edit-toggle").addEventListener("click", () => {
    if (state.pageEdit) saveAllEdits();
    else setPageEdit(true);
  });
  $("edit-cancel").addEventListener("click", cancelEdits);
  $("setup-search").addEventListener("click", searchSetupPlaces);
  $("setup-query").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      searchSetupPlaces();
    }
  });
  $("setup-places").addEventListener("click", (event) => {
    const btn = event.target.closest("[data-place-index]");
    if (btn) pickSetupPlace(Number(btn.dataset.placeIndex));
  });
  $("setup-add-planting").addEventListener("click", addSetupPlantingRow);
  $("setup-back").addEventListener("click", () => showSetupStep(Math.max(1, state.setupStep - 1)));
  $("setup-next").addEventListener("click", advanceSetup);
  $("setup-form").addEventListener("submit", (event) => event.preventDefault());
  $("drawer-close").addEventListener("click", closeDrawer);
  $("drawer-cancel").addEventListener("click", closeDrawer);
  $("drawer-backdrop").addEventListener("click", closeDrawer);
  $("status-chips").addEventListener("click", (event) => {
    const chip = event.target.closest("[data-status]");
    if (!chip) return;
    if (state.pageEdit) applyDraftsToState();
    state.status = chip.dataset.status;
    document.querySelectorAll("#status-chips .chip").forEach((el) => {
      el.classList.toggle("is-on", el === chip);
    });
    renderPlantings();
  });
  document.body.addEventListener("click", (event) => {
    const cat = event.target.closest("[data-plant]");
    if (cat) {
      setView("catalog");
      showWindow(cat.dataset.plant);
      return;
    }
    const pick = event.target.closest("[data-pick]");
    if (pick) {
      $("planting-form").plant_name.value = pick.dataset.pick;
      renderPlantPicker(pick.dataset.pick);
    }
  });
  document.body.addEventListener("submit", (event) => {
    if (event.target.matches("form.card-edit, #plot-form")) event.preventDefault();
  });
  $("planted-picker").addEventListener("change", (event) => {
    $("planting-form").planted_on.value = event.target.value;
  });
  $("planting-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = Object.fromEntries(new FormData(form).entries());
    const id = payload.id;
    delete payload.id;
    if (!payload.plant_name) {
      $("form-error").hidden = false;
      $("form-error").textContent = "Choose a plant from the catalog.";
      return;
    }
    try {
      $("form-error").hidden = true;
      if (id) await api(`/api/plantings/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
      else await api("/api/plantings", { method: "POST", body: JSON.stringify(payload) });
      closeDrawer();
      await refresh();
      setView("beds");
    } catch (err) {
      $("form-error").hidden = false;
      $("form-error").textContent = err.message;
    }
  });
}

bind();
refresh();

const API_BASE = "/api/macro";

// ================== Helpers génériques ==================

function pctClass(v) {
  if (v > 0) return "pos";
  if (v < 0) return "neg";
  return "neu";
}

function formatPct(v) {
  if (v === null || v === undefined) return "—";
  const num = Number(v);
  if (Number.isNaN(num)) return "—";
  const rounded = Math.round(num * 10) / 10;
  return (rounded > 0 ? "+" : "") + rounded + "%";
}

function formatDateTimeISO(iso) {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    const day = d.toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
    });
    const time = d.toLocaleTimeString("fr-FR", {
      hour: "2-digit",
      minute: "2-digit",
    });
    return `${day} ${time}`;
  } catch {
    return "—";
  }
}

function biasLabel(value) {
  if (!value) return "—";
  if (value === "bullish") return "Haussier";
  if (value === "bearish") return "Baissier";
  return "Neutre";
}

function biasClass(value) {
  if (value === "bullish") return "bias-bullish";
  if (value === "bearish") return "bias-bearish";
  return "bias-neutral";
}

// ================== Helpers sentiment grid ==================

// seuils plus sensibles pour voir des couleurs
function sentimentClass(v) {
  if (v === null || v === undefined) return "sentiment-neutral";
  if (v > 0.05) return "sentiment-pos";
  if (v < -0.05) return "sentiment-neg";
  return "sentiment-neutral";
}

function sentimentLabel(v) {
  if (v === null || v === undefined) return "—";
  if (v > 0.05) return "+";
  if (v < -0.05) return "−";
  return "•"; // neutre mais il y a eu du mouvement
}

// ================== SNAPSHOT ==================

async function loadSnapshot() {
  try {
    const res = await fetch(`${API_BASE}/snapshot`);
    const data = await res.json();

    const pill = document.getElementById("snapshot-pill");
    const commentEl = document.getElementById("snapshot-comment");
    const metaEl = document.getElementById("snapshot-meta");

    const biasEquities = document.getElementById("bias-equities");
    const biasRates = document.getElementById("bias-rates");
    const biasUsd = document.getElementById("bias-usd");
    const biasCredit = document.getElementById("bias-credit");
    const biasCommodities = document.getElementById("bias-commodities");
    const biasCrypto = document.getElementById("bias-crypto");

    const bias = data.bias || {};

    function setBias(el, value) {
      el.textContent = biasLabel(value);
      el.className = `bias-value ${biasClass(value)}`;
    }

    setBias(biasEquities, bias.equities);
    setBias(biasRates, bias.rates);
    setBias(biasUsd, bias.usd);
    setBias(biasCredit, bias.credit);
    setBias(biasCommodities, bias.commodities);
    setBias(biasCrypto, bias.crypto);

    const riskMode = data.risk_mode || "neutral";
    const riskClass =
      riskMode === "risk_on"
        ? "risk-on"
        : riskMode === "risk_off"
        ? "risk-off"
        : "risk-neutral";

    const riskLabel =
      riskMode === "risk_on"
        ? "RISK-ON"
        : riskMode === "risk_off"
        ? "RISK-OFF"
        : "NEUTRE";

    pill.innerHTML = `<span class="badge-risk ${riskClass}">${riskLabel}</span>`;

    commentEl.textContent =
      data.comment || "Lecture macro globale non disponible.";

    const vol = data.volatility || "—";
    const ts = data.timestamp ? formatDateTimeISO(data.timestamp) : "—";

    metaEl.innerHTML = `
      Volatilité : <span class="badge-vol">${vol}</span>
      · Dernière mise à jour : ${ts}
    `;
  } catch (err) {
    console.error("snapshot error", err);
    document.getElementById("snapshot-comment").textContent =
      "Impossible de récupérer la vue macro globale.";
    document.getElementById("snapshot-meta").textContent = "";
  }
}

// ================== ORIENTATION ==================

async function loadOrientation() {
  try {
    const res = await fetch(`${API_BASE}/orientation`);
    const data = await res.json();

    const container = document.getElementById("orientation-content");

    const risk = (data.risk || "neutral").toUpperCase();
    const conf =
      data.confidence != null
        ? Math.round(data.confidence * 100) + "%"
        : "—";

    const comment = data.comment || "";
    const notes = Array.isArray(data.notes) ? data.notes : [];

    container.innerHTML = `
      <div class="orientation-title">
        Biais global : ${risk}
      </div>
      <div class="orientation-meta">
        Confiance : ${conf}
      </div>
      ${
        comment
          ? `<p style="margin: 0 0 6px;">${comment}</p>`
          : ""
      }
      ${
        notes.length
          ? `
        <div style="font-size: 12px; color: var(--muted); margin-bottom: 2px;">
          Éléments marquants :
        </div>
        <ul class="orientation-list">
          ${notes.map((n) => `<li>${n}</li>`).join("")}
        </ul>
      `
          : ""
      }
    `;
  } catch (err) {
    console.error("orientation error", err);
    document.getElementById("orientation-content").textContent =
      "Impossible de récupérer l’orientation de marché.";
  }
}

// ================== INDICES ==================

async function loadIndices() {
  try {
    const res = await fetch(`${API_BASE}/indices`);
    const data = await res.json();
    const tbody = document.getElementById("indices-body");

    if (!Array.isArray(data) || data.length === 0) {
      tbody.innerHTML =
        `<tr><td colspan="4" class="muted">Aucune donnée d’indice disponible.</td></tr>`;
      return;
    }

    tbody.innerHTML = "";
    data.forEach((row) => {
      const daily = Number(row.daily);
      const weekly = Number(row.weekly);
      const monthly = Number(row.monthly);

      tbody.innerHTML += `
        <tr>
          <td>
            <div class="td-name">${row.name || row.symbol}</div>
            <div class="td-symbol">${row.symbol}</div>
          </td>
          <td class="${pctClass(daily)}">${formatPct(daily)}</td>
          <td class="${pctClass(weekly)}">${formatPct(weekly)}</td>
          <td class="${pctClass(monthly)}">${formatPct(monthly)}</td>
        </tr>
      `;
    });
  } catch (err) {
    console.error("indices error", err);
    document.getElementById("indices-body").innerHTML =
      `<tr><td colspan="4" class="muted">Erreur lors du chargement des performances.</td></tr>`;
  }
}

// ================== CALENDRIER ==================

async function loadCalendar() {
  try {
    const res = await fetch(`${API_BASE}/calendar?days_ahead=2`);
    const data = await res.json();
    const container = document.getElementById("calendar-list");

    if (!Array.isArray(data) || data.length === 0) {
      container.innerHTML = `<div class="muted" style="padding-top:6px;">
        Aucune publication majeure enregistrée sur l’horizon sélectionné.
      </div>`;
      return;
    }

    container.innerHTML = "";
    data.forEach((ev) => {
      const impact = (ev.impact || "medium").toLowerCase();
      const impactClass =
        impact === "high"
          ? "impact-high"
          : impact === "low"
          ? "impact-low"
          : "impact-medium";

      const dateLabel = ev.date || "";
      const timeLabel = ev.time || "";
      const country = ev.country || ev.currency || "";
      const title = ev.event || "";

      container.innerHTML += `
        <div class="calendar-item">
          <div class="calendar-date">${dateLabel} ${timeLabel}</div>
          <div>
            <div class="calendar-title">${title}</div>
            <div class="calendar-country">${country}</div>
          </div>
          <div style="text-align:right;">
            <span class="impact-badge ${impactClass}">${impact}</span>
          </div>
        </div>
      `;
    });
  } catch (err) {
    console.error("calendar error", err);
    document.getElementById("calendar-list").innerHTML =
      `<div class="muted" style="padding-top:6px;">Erreur lors du chargement du calendrier économique.</div>`;
  }
}

// ================== SENTIMENT GRID ==================

async function loadSentimentGrid() {
  try {
    const res = await fetch("/api/macro/sentiment_grid");
    const data = await res.json();
    const grid = data.grid || [];

    // date -> bucket -> sentiment
    const map = {};
    grid.forEach((row) => {
      if (!map[row.date]) map[row.date] = {};
      map[row.date][row.bucket] = row.sentiment;
    });

    const buckets = [
      "macro_us",
      "macro_europe",
      "companies",
      "geopolitics",
      "tech",
    ];

    const table = document.querySelector(".sentiment-table tbody");
    if (!table) return;

    table.innerHTML = "";

    Object.keys(map)
      .sort()
      .forEach((date) => {
        const tr = document.createElement("tr");

        const dayLabel = new Date(date).toLocaleDateString("fr-FR", {
          weekday: "short",
          day: "2-digit",
          month: "2-digit",
        });

        tr.innerHTML = `<td class="sentiment-day">${dayLabel}</td>`;

        buckets.forEach((b) => {
          const v = map[date][b];
          tr.innerHTML += `
            <td>
              <span class="sentiment-dot ${sentimentClass(v)}">
                ${sentimentLabel(v)}
              </span>
            </td>
          `;
        });

        table.appendChild(tr);
      });
  } catch (err) {
    console.error("sentiment grid error", err);
    // on laisse simplement la table vide si erreur
  }
}

// ================== HEALTH ==================

async function checkHealth() {
  try {
    const res = await fetch("/health");
    if (!res.ok) throw new Error("bad status");
    const data = await res.json();
    document.getElementById("health-status").textContent =
      data.status === "ok" ? "OK" : "statut inattendu";
  } catch {
    document.getElementById("health-status").textContent = "indisponible";
  }
}

// ================== GLOBAL REFRESH ==================

async function refreshAll() {
  await Promise.all([
    loadSnapshot(),
    loadOrientation(),
    loadIndices(),
    loadCalendar(),
    loadSentimentGrid(),
    checkHealth(),
  ]);
}

// bouton
document.getElementById("btn-refresh").addEventListener("click", refreshAll);

// premier chargement
refreshAll();

// refresh auto
setInterval(refreshAll, 60000);

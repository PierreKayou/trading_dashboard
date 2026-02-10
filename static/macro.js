const API_BASE = "/api/macro";

function sentimentClass(v) {
  if (v === null || v === undefined) return "sentiment-neutral";
  if (v > 0.2) return "sentiment-pos";
  if (v < -0.2) return "sentiment-neg";
  return "sentiment-neutral";
}

function sentimentLabel(v) {
  if (v === null || v === undefined) return "—";
  if (v > 0.2) return "+";
  if (v < -0.2) return "−";
  return "•";
}

async function loadSentimentGrid() {
  const res = await fetch("/api/macro/sentiment_grid");
  const data = await res.json();
  const grid = data.grid || [];

  const map = {};
  grid.forEach(row => {
    if (!map[row.date]) map[row.date] = {};
    map[row.date][row.bucket] = row.sentiment;
  });

  const buckets = ["macro_us", "macro_europe", "companies", "geopolitics", "tech"];
  const table = document.querySelector(".sentiment-table tbody");
  if (!table) return;

  table.innerHTML = "";

  Object.keys(map).sort().forEach(date => {
    const tr = document.createElement("tr");
    const label = new Date(date).toLocaleDateString("fr-FR", {
      weekday: "short",
      day: "2-digit",
      month: "2-digit",
    });

    tr.innerHTML = `<td class="sentiment-day">${label}</td>`;

    buckets.forEach(b => {
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
}

async function refreshAll() {
  await loadSentimentGrid();
}

refreshAll();
setInterval(refreshAll, 60000);

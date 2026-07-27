const PALETTE = [
  "#ffffff", "#cccccc", "#999999", "#666666", "#333333", "#000000",
  "#e53aa3", "#ff7bcc", "#f93c31", "#1e93ff", "#88d8f1", "#ffdc00",
  "#ff851b", "#921231", "#4fcc30", "#a356d6"
];

const state = { runs: [], timeline: [], runId: null, liveRunId: null };
const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {"Content-Type": "application/json"},
    ...options
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function latestFrame(observation) {
  const frames = observation?.frames || observation?.frame || [];
  return frames[frames.length - 1] || null;
}

function drawGrid(canvas, grid, comparison = null) {
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!grid) return;
  const rows = grid.length, cols = grid[0].length;
  const cell = Math.min(canvas.width / cols, canvas.height / rows);
  const ox = (canvas.width - cols * cell) / 2, oy = (canvas.height - rows * cell) / 2;
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      if (comparison) {
        const changed = comparison[y]?.[x] !== grid[y][x];
        ctx.fillStyle = changed ? "#ef6a6a" : "#1a1e21";
      } else {
        ctx.fillStyle = PALETTE[grid[y][x]] || "#000";
      }
      ctx.fillRect(ox + x * cell, oy + y * cell, Math.ceil(cell), Math.ceil(cell));
    }
  }
}

function normalizeEvent(event) {
  let payload = event.payload || {};
  if (event.kind === "transition_analysis") {
    const index = payload.transition_index;
    const raw = state.timeline.find((candidate) =>
      candidate.kind === "transition_raw" &&
      candidate.payload?.transition?.index === index
    );
    if (raw) payload = {...raw.payload, ...payload};
  }
  const transition = payload.transition || {};
  const actual = payload.actual || transition.after || payload.observation || payload;
  const predicted = payload.predicted || actual;
  const action = payload.action || transition.action || {};
  return {actual, predicted, action, payload};
}

async function showEvent(index) {
  const event = state.timeline[index];
  if (!event) return;
  document.querySelectorAll("#timeline button").forEach((button, i) => {
    button.classList.toggle("active", i === index);
  });
  const {actual, predicted, action, payload} = normalizeEvent(event);
  $("step-label").textContent = `${event.sequence} · ${event.kind}`;
  $("action-label").textContent = action.id === undefined ? "—" : `ACTION${action.id}`;
  $("model-label").textContent = payload.model_digest?.slice(0, 16) || "—";
  const diff = payload.diff;
  $("verdict-label").textContent = diff ? (diff.exact ? "match" : "mismatch") : "observation";
  $("verdict-label").style.color = diff && !diff.exact ? "var(--danger)" : "var(--ok)";
  const actualGrid = latestFrame(actual), predictedGrid = latestFrame(predicted);
  drawGrid($("actual-grid"), actualGrid);
  drawGrid($("predicted-grid"), predictedGrid);
  drawGrid($("diff-grid"), actualGrid, predictedGrid);
  $("raw-event").textContent = JSON.stringify(event, null, 2);

  if (actualGrid && predictedGrid) {
    const inspection = await api("/api/inspect", {
      method: "POST", body: JSON.stringify({actual, predicted})
    });
    renderInspection(inspection);
  } else {
    renderInspection(null);
  }
}

function renderInspection(value) {
  const scene = value?.actual_scene;
  $("objects").innerHTML = (scene?.objects || []).map((object) =>
    `<tr><td>${object.id}</td><td>${object.color}</td><td>${object.area}</td>` +
    `<td>${object.bbox.x},${object.bbox.y} · ${object.bbox.width}×${object.bbox.height}</td>` +
    `<td>${object.holes}</td></tr>`
  ).join("");
  $("relations").innerHTML = (scene?.relations || []).map((relation) =>
    `<li>${relation.subject} <span>${relation.predicate}</span> ${relation.object}</li>`
  ).join("");
  const diff = value?.diff;
  const metrics = diff ? [
    ["Changed pixels", diff.pixels.changed],
    ["Frame ratio", `${(diff.pixels.ratio * 100).toFixed(2)}%`],
    ["Object deltas", diff.scene.deltas.length],
    ["Diff regions", diff.pixels.regions.length],
    ["Status", diff.status_match ? "match" : "different"],
    ["Levels", diff.level_match ? "match" : "different"]
  ] : [];
  $("mismatch").innerHTML = metrics.map(([name, metric]) =>
    `<div class="metric">${name}<strong>${metric}</strong></div>`
  ).join("");
}

async function loadRun(runId) {
  const data = await api(`/api/runs/${runId}`);
  state.runId = runId;
  state.timeline = data.timeline;
  $("run-meta").textContent = `${data.run.label} · ${data.run.started_at} · ${data.timeline.length} events`;
  $("timeline").innerHTML = data.timeline.map((event, index) =>
    `<li><button data-index="${index}">${String(event.sequence).padStart(3, "0")} · ${event.kind}</button></li>`
  ).join("");
  document.querySelectorAll("#timeline button").forEach((button) => {
    button.addEventListener("click", () => showEvent(Number(button.dataset.index)));
  });
  if (state.timeline.length) {
    let index = state.timeline.length - 1;
    while (index > 0 && !latestFrame(normalizeEvent(state.timeline[index]).actual)) index--;
    showEvent(index);
  }
}

async function refreshRuns(selectRun = null) {
  state.runs = await api("/api/runs");
  $("run-select").innerHTML = state.runs.map((run) =>
    `<option value="${run.id}">${run.label} · ${run.event_count}</option>`
  ).join("");
  const runId = selectRun || state.runs[0]?.id;
  if (runId) {
    $("run-select").value = runId;
    await loadRun(runId);
  }
}

$("run-select").addEventListener("change", (event) => loadRun(event.target.value));
$("start-toy").addEventListener("click", async () => {
  const result = await api("/api/live/toy", {method: "POST", body: "{}"});
  state.liveRunId = result.run_id;
  await refreshRuns(result.run_id);
});
document.querySelectorAll("[data-action]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (!state.liveRunId) return;
    await api(`/api/live/${state.liveRunId}/action`, {
      method: "POST",
      body: JSON.stringify({id: Number(button.dataset.action)})
    });
    await refreshRuns(state.liveRunId);
  });
});

(async () => {
  try {
    await api("/api/health");
    $("health").textContent = "local · ready";
    $("health").classList.add("ok");
    await refreshRuns();
  } catch (error) {
    $("health").textContent = `error · ${error.message}`;
  }
})();

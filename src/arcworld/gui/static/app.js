const PALETTE = [
  "#ffffff", "#cccccc", "#999999", "#666666", "#333333", "#000000",
  "#e53aa3", "#ff7bcc", "#f93c31", "#1e93ff", "#88d8f1", "#ffdc00",
  "#ff851b", "#921231", "#4fcc30", "#a356d6"
];

const state = {
  capabilities: null,
  runs: [],
  sessions: new Map(),
  timeline: [],
  runRecord: null,
  runId: null,
  desiredRunId: null,
  sessionId: null,
  session: null,
  audit: null,
  auditState: "not_applicable",
  chainValid: null,
  eventCursor: -1,
  selectedSequence: null,
  followLatest: true,
  autoRun: false,
  permissionSessionId: null,
  commandPending: false,
  loadToken: 0,
  polling: false,
  pollCount: 0,
  completedRunReloaded: false
};

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {"Content-Type": "application/json"},
    ...options
  });
  const contentType = response.headers.get("content-type") || "";
  const value = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const detail = typeof value === "object" && value?.detail
      ? value.detail
      : typeof value === "string"
        ? value
        : JSON.stringify(value);
    throw new Error(detail || `HTTP ${response.status}`);
  }
  return value;
}

function latestFrame(observation) {
  const frames = observation?.frames || observation?.frame || [];
  return frames[frames.length - 1] || null;
}

function drawGrid(canvas, grid, comparison = null) {
  const ctx = canvas.getContext("2d");
  const baseLabel = canvas.dataset.label || "Game grid";
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#090a0b";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  if (!grid?.length || !grid[0]?.length) {
    canvas.setAttribute("aria-label", `${baseLabel}; no grid is available`);
    return;
  }
  const rows = grid.length;
  const cols = grid[0].length;
  const counts = new Map();
  let changedCells = 0;
  const cell = Math.min(canvas.width / cols, canvas.height / rows);
  const ox = (canvas.width - cols * cell) / 2;
  const oy = (canvas.height - rows * cell) / 2;
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      if (comparison) {
        const changed = comparison[y]?.[x] !== grid[y][x];
        if (changed) changedCells += 1;
        ctx.fillStyle = changed ? "#ef6a6a" : "#20262a";
      } else {
        counts.set(grid[y][x], (counts.get(grid[y][x]) || 0) + 1);
        ctx.fillStyle = PALETTE[grid[y][x]] || "#000000";
      }
      ctx.fillRect(ox + x * cell, oy + y * cell, Math.ceil(cell), Math.ceil(cell));
    }
  }
  const detail = comparison
    ? `${changedCells} changed cell${changedCells === 1 ? "" : "s"}`
    : `color counts ${[...counts.entries()]
      .sort(([left], [right]) => left - right)
      .map(([color, count]) => `${color}: ${count}`)
      .join(", ")}`;
  canvas.setAttribute("aria-label", `${baseLabel}; ${cols} by ${rows}; ${detail}`);
}

function normalizeEvent(event) {
  let payload = event?.payload || {};
  if (event?.kind === "transition_analysis") {
    const index = payload.transition_index;
    const raw = state.timeline.find((candidate) =>
      candidate.kind === "transition_raw" &&
      candidate.payload?.transition?.index === index
    );
    if (raw) payload = {...raw.payload, ...payload};
  }
  const transition = payload.transition || {};
  const actual = payload.actual || transition.after || payload.observation || payload;
  const predicted = payload.predicted || null;
  const action = payload.action || transition.action || {};
  return {actual, predicted, action, payload};
}

async function showEvent(sequence, {userSelected = false} = {}) {
  const event = state.timeline.find((item) => item.sequence === sequence);
  if (!event) return;
  const requestedRunId = state.runId;
  state.selectedSequence = sequence;
  if (userSelected) {
    state.followLatest = sequence === state.eventCursor;
    $("new-events").textContent = state.followLatest ? "" : "following paused";
  }
  document.querySelectorAll("#timeline button").forEach((button) => {
    const active = Number(button.dataset.sequence) === sequence;
    button.classList.toggle("active", active);
    button.tabIndex = active ? 0 : -1;
    if (active) button.setAttribute("aria-current", "step");
    else button.removeAttribute("aria-current");
  });

  const {actual, predicted, action, payload} = normalizeEvent(event);
  $("step-label").textContent = `${event.sequence} · ${friendlyEvent(event.kind)}`;
  $("action-label").textContent = formatAction(action);
  $("model-label").textContent = payload.model_digest?.slice(0, 16) || "—";
  const diff = payload.diff;
  $("verdict-label").textContent = diff ? (diff.exact ? "match" : "mismatch") : "not evaluated";
  $("verdict-label").className = diff ? (diff.exact ? "verdict-ok" : "verdict-bad") : "";
  const actualGrid = latestFrame(actual);
  const predictedGrid = latestFrame(predicted);
  drawGrid($("actual-grid"), actualGrid);
  drawGrid($("predicted-grid"), predictedGrid);
  drawGrid($("diff-grid"), predictedGrid ? actualGrid : null, predictedGrid);
  $("raw-event").textContent = JSON.stringify(event, null, 2);
  $("source-code").textContent = artifactText(event, payload);

  if (actualGrid) {
    const inspectionSequence = sequence;
    try {
      const inspection = await api("/api/inspect", {
        method: "POST",
        body: JSON.stringify({actual, predicted: predicted || actual})
      });
      if (
        state.runId === requestedRunId &&
        state.selectedSequence === inspectionSequence
      ) {
        renderInspection(inspection, Boolean(predictedGrid));
      }
    } catch (error) {
      if (
        state.runId === requestedRunId &&
        state.selectedSequence === inspectionSequence
      ) {
        renderInspection(null, false);
      }
    }
  } else {
    renderInspection(null, false);
  }
}

function artifactText(event, payload) {
  if (typeof payload.source === "string" && payload.source) return payload.source;
  if (event.kind === "reasoner_response" && typeof payload.response === "string") {
    return payload.response;
  }
  if (event.kind === "reasoner_request") {
    return [
      "INSTRUCTIONS",
      payload.instructions || "",
      "",
      "SANITIZED INPUT",
      payload.input || ""
    ].join("\n");
  }
  if (event.kind === "model_executed") {
    return `Sandbox model execution receipt\n${JSON.stringify(payload, null, 2)}`;
  }
  if (event.kind === "plan_simulated") {
    return `Complete simulator rollout receipt\n${JSON.stringify(payload, null, 2)}`;
  }
  return "This event has no model-output artifact.";
}

function renderInspection(value, showDiff) {
  const objects = $("objects");
  objects.replaceChildren();
  for (const object of value?.actual_scene?.objects || []) {
    const row = document.createElement("tr");
    for (const text of [
      object.id,
      object.color,
      object.area,
      `${object.bbox.x},${object.bbox.y} · ${object.bbox.width}×${object.bbox.height}`,
      object.holes
    ]) {
      const cell = document.createElement("td");
      cell.textContent = String(text);
      row.append(cell);
    }
    objects.append(row);
  }

  const relations = $("relations");
  relations.replaceChildren();
  for (const relation of value?.actual_scene?.relations || []) {
    const item = document.createElement("li");
    item.textContent = `${relation.subject} ${relation.predicate} ${relation.object}`;
    relations.append(item);
  }

  const metrics = $("mismatch");
  metrics.replaceChildren();
  const diff = showDiff ? value?.diff : null;
  const values = diff ? [
    ["Changed pixels", diff.pixels.changed],
    ["Frame ratio", `${(diff.pixels.ratio * 100).toFixed(2)}%`],
    ["Object deltas", diff.scene.deltas.length],
    ["Diff regions", diff.pixels.regions.length],
    ["Status", diff.status_match ? "match" : "different"],
    ["Levels", diff.level_match ? "match" : "different"]
  ] : [];
  for (const [name, metric] of values) {
    const item = document.createElement("div");
    item.className = "metric";
    item.textContent = name;
    const strong = document.createElement("strong");
    strong.textContent = String(metric);
    item.append(strong);
    metrics.append(item);
  }
}

function renderTimeline({newCount = 0} = {}) {
  const timeline = $("timeline");
  const focusedSequence = timeline.contains(document.activeElement)
    ? document.activeElement?.dataset?.sequence
    : null;
  const tabSequence = state.selectedSequence ??
    state.timeline[state.timeline.length - 1]?.sequence;
  timeline.replaceChildren();
  for (const event of state.timeline) {
    const item = document.createElement("li");
    item.className = eventClass(event.kind);
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.sequence = String(event.sequence);
    button.tabIndex = event.sequence === tabSequence ? 0 : -1;
    button.textContent =
      `${String(event.sequence).padStart(3, "0")} · ${friendlyEvent(event.kind)}`;
    button.addEventListener("click", () => showEvent(event.sequence, {userSelected: true}));
    button.addEventListener("keydown", timelineKeydown);
    item.append(button);
    timeline.append(item);
  }
  if (state.selectedSequence !== null) {
    const selected = timeline.querySelector(
      `button[data-sequence="${state.selectedSequence}"]`
    );
    if (selected) {
      selected.classList.add("active");
      selected.setAttribute("aria-current", "step");
    }
  }
  if (focusedSequence !== null) {
    timeline.querySelector(`button[data-sequence="${focusedSequence}"]`)
      ?.focus({preventScroll: true});
  }
  if (newCount > 0 && !state.followLatest) {
    $("new-events").textContent = `${newCount} new event${newCount === 1 ? "" : "s"}`;
  }
}

function timelineKeydown(event) {
  if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const buttons = [...document.querySelectorAll("#timeline button")];
  const current = buttons.indexOf(event.currentTarget);
  const target = event.key === "Home"
    ? 0
    : event.key === "End"
      ? buttons.length - 1
      : event.key === "ArrowDown"
        ? Math.min(buttons.length - 1, current + 1)
        : Math.max(0, current - 1);
  const targetButton = buttons[target];
  targetButton?.focus();
  if (targetButton) {
    void showEvent(Number(targetButton.dataset.sequence), {userSelected: true});
  }
}

async function loadRun(runId, {preserveSelection = false} = {}) {
  state.desiredRunId = runId;
  const loadToken = ++state.loadToken;
  const data = await api(`/api/runs/${encodeURIComponent(runId)}`);
  if (loadToken !== state.loadToken || state.desiredRunId !== runId) return;
  const previousSelection = preserveSelection ? state.selectedSequence : null;
  state.runId = runId;
  state.runRecord = data.run;
  state.timeline = data.timeline;
  state.audit = data.audit;
  state.auditState = data.audit_state;
  state.chainValid = data.event_chain_valid;
  state.eventCursor = data.timeline.length
    ? data.timeline[data.timeline.length - 1].sequence
    : -1;
  state.selectedSequence = previousSelection;
  state.followLatest = previousSelection === null || previousSelection === state.eventCursor;
  const trackedSession = state.sessions.get(runId);
  const workerSettled = !trackedSession ||
    (!trackedSession.busy && !trackedSession.active_phase);
  state.completedRunReloaded = workerSettled && data.timeline.some(
    (event) => event.kind === "run_finished" || event.kind === "run_error"
  );
  renderRunMeta();
  renderTimeline();
  if (previousSelection !== null && state.timeline.some(
    (event) => event.sequence === previousSelection
  )) {
    await showEvent(previousSelection);
  } else {
    await followLatestDisplayable();
  }
  if (
    loadToken !== state.loadToken ||
    state.desiredRunId !== runId ||
    state.runId !== runId
  ) return;
  state.sessionId = state.sessions.has(runId) ? runId : null;
  state.session = state.sessions.get(runId) || null;
  renderSession();
}

function renderRunMeta() {
  if (!state.runRecord) return;
  const data = state.runRecord;
  const experiment = data.config?.experiment || {};
  const environment = experiment.environment || {};
  const real = experiment.run_kind === "official-public-game-live-llm";
  $("run-meta").textContent =
    `${data.label} · ${data.started_at} · ${state.timeline.length} events`;
  const evidence = $("run-evidence");
  evidence.className = "evidence-card";
  if (real) {
    evidence.classList.add("real");
    if (state.auditState === "passed") evidence.classList.add("verified");
    if (state.auditState === "failed") evidence.classList.add("invalid");
    evidence.textContent =
      `REAL PUBLIC GAME · ${environment.game_id || "unknown"} · ` +
      `${state.auditState === "pending" ? "EVIDENCE AUDIT PENDING" :
        state.auditState === "passed" ? "FULL EVIDENCE AUDIT PASSED" :
        "EVIDENCE AUDIT FAILED"} · ` +
      `chain ${state.chainValid ? "valid at last full load" : "INVALID"}`;
  } else {
    evidence.textContent =
      `SYNTHETIC / FIXTURE · chain ` +
      `${state.chainValid ? "valid at last full load" : "INVALID"}`;
  }
}

async function pollEvents() {
  if (!state.runId) return;
  const requestedRunId = state.runId;
  const data = await api(
    `/api/runs/${encodeURIComponent(requestedRunId)}/events` +
    `?after_sequence=${state.eventCursor}&limit=200`
  );
  if (state.runId !== requestedRunId) return;
  const events = data.events || [];
  if (!events.length) return;
  const expected = state.eventCursor + 1;
  if (events[0].sequence !== expected) {
    await loadRun(state.runId, {preserveSelection: true});
    return;
  }
  state.timeline.push(...events);
  state.eventCursor = data.next_after_sequence;
  renderTimeline({newCount: events.length});
  renderRunMeta();
  if (state.followLatest) await followLatestDisplayable();
}

async function followLatestDisplayable() {
  if (!state.timeline.length) return;
  let index = state.timeline.length - 1;
  while (index > 0 && !latestFrame(normalizeEvent(state.timeline[index]).actual)) index--;
  state.followLatest = true;
  $("new-events").textContent = "";
  await showEvent(state.timeline[index].sequence);
}

async function refreshSessions() {
  const sessions = await api("/api/tests");
  state.sessions = new Map(sessions.map((session) => [session.run_id, session]));
  if (state.sessionId && state.sessions.has(state.sessionId)) {
    state.session = state.sessions.get(state.sessionId);
  }
}

async function refreshRuns(selectRun = null) {
  state.runs = await api("/api/runs");
  const select = $("run-select");
  const prior = selectRun || state.desiredRunId || state.runId;
  select.replaceChildren();
  for (const run of state.runs) {
    const option = document.createElement("option");
    option.value = run.id;
    const real = run.config?.experiment?.run_kind === "official-public-game-live-llm";
    const interactive = run.config?.experiment?.controller === "interactive-phase-v1";
    option.textContent =
      `${real ? "[OFFICIAL] " : "[SYNTHETIC] "}` +
      `${interactive ? "[STEP] " : ""}${run.label} · ${run.event_count}`;
    select.append(option);
  }
  const runId = prior && state.runs.some((run) => run.id === prior)
    ? prior
    : state.runs[0]?.id;
  if (runId) {
    select.value = runId;
    if (runId !== state.runId || selectRun) await loadRun(runId);
  }
}

function renderCapabilities() {
  const capabilities = state.capabilities;
  const puzzles = $("puzzle-select");
  puzzles.replaceChildren();
  for (const puzzle of capabilities.puzzles || []) {
    const option = document.createElement("option");
    option.value = puzzle.id;
    option.dataset.kind = puzzle.kind;
    option.disabled = puzzle.kind === "official" && !puzzle.runtime_ready;
    option.textContent =
      `${puzzle.kind === "official" ? "[OFFICIAL] " : "[FIXTURE] "}` +
      `${puzzle.label}${puzzle.runtime_ready ? "" : " · runtime unavailable"}`;
    puzzles.append(option);
  }
  const effort = $("effort-select");
  effort.replaceChildren();
  for (const value of capabilities.efforts || []) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    effort.append(option);
  }
  const officialCount = (capabilities.puzzles || []).filter(
    (puzzle) => puzzle.kind === "official"
  ).length;
  const issueCount = (capabilities.issues || []).length;
  $("catalog-note").textContent =
    `${officialCount} validated local official puzzle${officialCount === 1 ? "" : "s"}` +
    `${issueCount ? ` · ${issueCount} cache issue${issueCount === 1 ? "" : "s"}` : ""}.`;
  renderProviderOptions({reset: true});
}

function renderProviderOptions({reset = false} = {}) {
  const official = selectedPuzzle()?.kind === "official";
  const select = $("provider-select");
  const prior = reset ? null : select.value;
  select.replaceChildren();
  for (const provider of state.capabilities.providers || []) {
    const option = document.createElement("option");
    option.value = provider.id;
    option.disabled = !provider.available || (official && provider.synthetic_only);
    option.textContent =
      `${provider.label}${provider.available ? "" : " · unavailable"}`;
    select.append(option);
  }
  const preferred = prior && [...select.options].some(
    (option) => option.value === prior && !option.disabled
  )
    ? prior
    : official
      ? [...select.options].find((option) => !option.disabled && option.value !== "deterministic")?.value
      : "deterministic";
  if (preferred) select.value = preferred;
  applyProviderDefaults();
}

function selectedPuzzle() {
  return state.capabilities?.puzzles?.find(
    (puzzle) => puzzle.id === $("puzzle-select").value
  );
}

function selectedProvider() {
  return state.capabilities?.providers?.find(
    (provider) => provider.id === $("provider-select").value
  );
}

function applyProviderDefaults() {
  const provider = selectedProvider();
  if (!provider) return;
  $("model-input").value = provider.default_model;
  $("effort-select").value = provider.default_effort;
  const deterministic = provider.id === "deterministic";
  $("model-input").readOnly = deterministic;
  $("effort-select").disabled = deterministic;
  $("candidate-input").disabled = deterministic;
  if (deterministic) $("candidate-input").value = "1";
  $("provider-note").textContent = provider.notice || "";
}

async function createTest(event) {
  event.preventDefault();
  state.autoRun = false;
  renderSession();
  $("form-error").textContent = "";
  const button = $("create-test");
  button.disabled = true;
  const payload = {
    puzzle_id: $("puzzle-select").value,
    provider: $("provider-select").value,
    model: $("model-input").value,
    effort: $("effort-select").value || "fixed",
    action_budget: Number($("budget-input").value),
    candidate_count: Number($("candidate-input").value),
    seed: Number($("seed-input").value)
  };
  try {
    const session = await api("/api/tests", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    state.sessionId = session.run_id;
    state.session = session;
    state.sessions.set(session.run_id, session);
    await refreshRuns(session.run_id);
    renderSession();
    $("session-announcer").textContent =
      "New paused test created. Initialize the environment when ready.";
  } catch (error) {
    $("form-error").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function requestStep({automatic = false} = {}) {
  const session = state.session;
  if (!session?.can_advance || session.busy || state.commandPending) return;
  const execution = session.phase === "execution";
  const official = session.test?.puzzle_id !== "synthetic-key-door";
  if (automatic && execution && official && !$("allow-auto-actions").checked) {
    state.autoRun = false;
    $("session-announcer").textContent =
      "Auto-run paused before a real official action. Review the plan, execute one " +
      "action manually, or explicitly allow automatic real actions.";
    renderSession();
    return;
  }
  state.commandPending = true;
  renderSession();
  try {
    const requestedRunId = session.run_id;
    const accepted = await api(
      `/api/tests/${encodeURIComponent(requestedRunId)}/step`,
      {
        method: "POST",
        body: JSON.stringify({
          expected_state_version: session.state_version,
          authorize_real_action:
            execution && (!automatic || !official || $("allow-auto-actions").checked)
        })
      }
    );
    state.sessions.set(accepted.run_id, accepted);
    if (state.sessionId === requestedRunId) {
      state.session = accepted;
      renderSession();
    }
  } catch (error) {
    state.autoRun = false;
    $("session-error").textContent = error.message;
  } finally {
    state.commandPending = false;
    renderSession();
  }
}

function renderSession() {
  const session = state.sessionId ? state.session : null;
  const controls = $("session-controls");
  if (!session) {
    controls.setAttribute("aria-busy", "false");
    $("session-state").textContent = "Inspection only";
    $("phase-label").textContent = "—";
    $("budget-label").textContent = "—";
    $("revision-label").textContent = "—";
    $("plan-label").textContent = "—";
    $("step-phase").disabled = true;
    $("auto-run").disabled = true;
    $("pause-run").disabled = true;
    $("auto-action-permission").hidden = true;
    $("session-error").textContent = "";
    return;
  }
  const busy = Boolean(session.busy);
  const active = session.active_phase;
  const terminal = ["finished", "error", "outcome_unknown"].includes(session.phase);
  const official = session.test?.puzzle_id !== "synthetic-key-door";
  if (state.permissionSessionId !== session.run_id) {
    $("allow-auto-actions").checked = false;
    state.permissionSessionId = session.run_id;
  }
  $("auto-action-permission").hidden = !official;
  controls.setAttribute("aria-busy", String(busy));
  $("session-state").textContent = terminal
      ? session.phase === "finished"
        ? "Finished"
        : session.phase === "outcome_unknown"
          ? "Outcome unknown"
          : "Failed"
      : session.error
        ? "Failed"
      : busy
        ? active
          ? `Running · ${friendlyPhase(active)}`
          : "Queued"
        : state.autoRun
          ? "Auto-running"
          : "Paused";
  $("phase-label").textContent = busy
    ? friendlyPhase(session.active_phase || session.phase)
    : terminal
      ? "—"
      : friendlyPhase(session.phase);
  $("budget-label").textContent = `${session.real_actions} / ${session.action_budget}`;
  $("revision-label").textContent = String(session.revision_count);
  $("plan-label").textContent = session.pending_plan
    ? `${session.pending_plan.remaining_count} action` +
      `${session.pending_plan.remaining_count === 1 ? "" : "s"}`
    : "none";

  const step = $("step-phase");
  step.textContent = stepLabel(session.phase);
  step.disabled =
    busy || terminal || state.autoRun || state.commandPending || !session.can_advance;
  $("auto-run").disabled =
    busy || terminal || state.autoRun || state.commandPending || !session.can_advance;
  $("pause-run").disabled = !state.autoRun;
  $("phase-help").textContent = phaseHelp(session);
  $("session-error").textContent = session.error || session.worker_error || "";
}

function stepLabel(phase) {
  return {
    start: "Initialize environment",
    induction: "Induce world model",
    planning: "Generate + simulate plan",
    execution: "Execute 1 real action",
    revision: "Revise + replay model"
  }[phase] || "Advance one phase";
}

function phaseHelp(session) {
  if (session.busy) {
    return session.active_phase
      ? "This phase is in flight. New observable requests, outputs, code, and receipts " +
        "appear in the event trace as they are recorded."
      : "This phase is queued behind another local test and has not started yet.";
  }
  if (session.phase === "execution") {
    return "This step authorizes exactly one real environment action. Any mismatch cancels " +
      "the unspent plan before revision.";
  }
  if (session.phase === "finished") {
    return `Run finished: ${session.result?.reason || "complete"}.`;
  }
  if (session.phase === "error") {
    return "The run failed closed. Inspect the final events; no further action is authorized.";
  }
  if (session.phase === "outcome_unknown") {
    return "A real action was intended but no durable result was recorded. The run is " +
      "inspection-only so retry cannot spend the same action twice.";
  }
  return "Each click completes one phase. Model calls expose final outputs and generated " +
    "artifacts, never hidden provider chain-of-thought.";
}

async function poll() {
  if (state.polling) return;
  state.polling = true;
  try {
    if (state.sessionId) {
      const requestedSessionId = state.sessionId;
      const previousPhase = state.session?.phase;
      const session = await api(`/api/tests/${encodeURIComponent(requestedSessionId)}`);
      state.sessions.set(session.run_id, session);
      if (state.sessionId === requestedSessionId) {
        state.session = session;
        renderSession();
        if (session.phase !== previousPhase || session.active_phase) {
          $("session-announcer").textContent =
            session.busy
              ? `${friendlyPhase(session.active_phase)} is running.`
              : `Ready for ${friendlyPhase(session.phase)}.`;
        }
        if (
          ["finished", "error", "outcome_unknown"].includes(session.phase) &&
          !session.busy &&
          !session.active_phase &&
          !state.completedRunReloaded
        ) {
          await loadRun(session.run_id, {preserveSelection: true});
          if (state.sessionId === requestedSessionId) {
            state.completedRunReloaded = true;
          }
        }
      }
    }
    await pollEvents();
    if (state.autoRun && state.session?.can_advance && !state.session.busy) {
      await requestStep({automatic: true});
    }
    state.pollCount += 1;
    if (state.pollCount % 8 === 0) {
      await refreshSessions();
      await refreshRuns();
    }
  } catch (error) {
    $("health").textContent = `local · polling error`;
    $("session-error").textContent = error.message;
  } finally {
    state.polling = false;
  }
}

function formatAction(action) {
  if (action?.id === undefined) return "—";
  return action.id === 6
    ? `ACTION6(${action.x},${action.y})`
    : action.id === 0
      ? "RESET"
      : `ACTION${action.id}`;
}

function friendlyEvent(kind) {
  return String(kind || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function friendlyPhase(phase) {
  return friendlyEvent(phase || "—");
}

function eventClass(kind) {
  if (kind.includes("error") || kind.includes("failed") || kind === "plan_invalidated") {
    return "event-danger";
  }
  if (kind.startsWith("reasoner_")) return "event-model";
  if (kind.startsWith("transition_") || kind === "action_intent") return "event-action";
  if (kind.startsWith("interactive_phase")) return "event-phase";
  return "";
}

$("run-select").addEventListener("change", async (event) => {
  state.autoRun = false;
  const requestedRunId = event.target.value;
  state.desiredRunId = requestedRunId;
  state.loadToken += 1;
  state.sessionId = null;
  state.session = null;
  renderSession();
  await refreshSessions();
  if (state.desiredRunId === requestedRunId) await loadRun(requestedRunId);
});
$("test-form").addEventListener("submit", createTest);
$("puzzle-select").addEventListener("change", () => renderProviderOptions({reset: true}));
$("provider-select").addEventListener("change", applyProviderDefaults);
$("step-phase").addEventListener("click", () => requestStep());
$("auto-run").addEventListener("click", async () => {
  state.autoRun = true;
  renderSession();
  await requestStep({automatic: true});
});
$("pause-run").addEventListener("click", () => {
  state.autoRun = false;
  renderSession();
  $("session-announcer").textContent =
    "Auto-run paused. An in-flight phase will finish, but no next phase will begin.";
});

(async () => {
  try {
    const [health, capabilities] = await Promise.all([
      api("/api/health"),
      api("/api/test-capabilities")
    ]);
    state.capabilities = capabilities;
    $("health").textContent = `local · ready · ${health.store}`;
    $("health").classList.add("ok");
    renderCapabilities();
    await refreshSessions();
    await refreshRuns();
    renderSession();
    window.setInterval(poll, 650);
  } catch (error) {
    $("health").textContent = `error · ${error.message}`;
    $("form-error").textContent = error.message;
  }
})();

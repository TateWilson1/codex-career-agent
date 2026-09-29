const token = document.querySelector('meta[name="career-token"]').content;
const headers = {"Content-Type": "application/json", "X-Career-Token": token};
let state = null;
let activeRun = null;
let currentView = "dashboard";
const alertedJobs = new Set(JSON.parse(localStorage.getItem("career-alerted-jobs") || "[]"));

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const escapeHtml = (value = "") => String(value).replace(/[&<>'"]/g, char => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", "'":"&#39;", '"':"&quot;"})[char]);
const statusClass = value => escapeHtml(String(value || "").toLowerCase().replaceAll(" ", "_"));
const formatDate = value => value ? new Intl.DateTimeFormat(undefined, {dateStyle: "medium", timeStyle: value.includes("T") ? "short" : undefined}).format(new Date(value)) : "Not scheduled";
const listText = value => Array.isArray(value) ? value.join(", ") : (value || "—");

async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {...headers, ...(options.headers || {})}});
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function statusBadge(value) {
  return `<span class="status ${statusClass(value)}">${escapeHtml(String(value || "unknown").replaceAll("_", " "))}</span>`;
}

function emptyState(title, copy, prompt, label) {
  return `<div class="empty-state"><h2>${escapeHtml(title)}</h2><p>${escapeHtml(copy)}</p><button class="button button-primary" data-prompt="${escapeHtml(prompt)}">${escapeHtml(label)}</button></div>`;
}

async function refresh() {
  try {
    state = await api("/api/state");
    $("#loading").hidden = true;
    $("#error-banner").hidden = true;
    renderAll();
    notifyFreshAlerts();
  } catch (error) {
    $("#loading").hidden = true;
    $("#error-banner").textContent = `Could not load the career workspace. ${error.message}`;
    $("#error-banner").hidden = false;
  }
}

async function refreshCodex() {
  try {
    const auth = await api("/api/codex");
    const card = $("#connection-card");
    card.classList.toggle("is-ready", auth.subscription_ready);
    card.innerHTML = `<span class="status-dot"></span><div><strong>${escapeHtml(auth.label)}</strong><small>${auth.subscription_ready ? "Uses your ChatGPT plan" : "No API billing"}</small></div>${auth.subscription_ready ? "" : '<button class="button button-quiet" id="connect-codex">Connect</button>'}`;
    $("#connect-codex")?.addEventListener("click", connectCodex);
  } catch (error) {
    showToast(error.message);
  }
}

async function connectCodex() {
  try {
    const result = await api("/api/codex/login", {method: "POST", body: "{}"});
    showToast(result.instruction);
    setTimeout(refreshCodex, 5000);
  } catch (error) {
    showToast(error.message);
  }
}

function renderAll() {
  renderWatchStatus();
  renderDashboard();
  renderJobs();
  renderApplications();
  renderSources();
  renderConnections();
  renderResume();
  renderActivity();
  bindDynamicActions();
}

function renderDashboard() {
  const profile = state.profile;
  const jobs = state.jobs.slice(0, 4);
  const pending = [
    ...state.interviews.filter(item => item.status === "scheduled").map(item => ({title: `${item.stage} interview`, detail: `${item.company} · ${formatDate(item.scheduled_at)}`, prompt: `Prepare me for my ${item.stage} interview for application ${item.application_id} using the exact saved application history.`})),
    ...state.followups.filter(item => item.status === "planned").map(item => ({title: `${item.kind} follow-up`, detail: `${item.company} · ${formatDate(item.due_at)}`, prompt: `Prepare the ${item.kind} follow-up for application ${item.application_id} using the saved application history. Show it before saving or sending anything.`})),
    ...state.automation.filter(item => ["blocked", "ready_for_fill", "authorized_to_submit"].includes(item.state)).map(item => ({title: `Application ${item.state.replaceAll("_", " ")}`, detail: `${item.company} · ${item.title}`, prompt: `Review automation run ${item.id} for ${item.company}. Show its safety state, exact approved documents, and the next permitted action.`}))
  ].slice(0, 5);
  const objective = state.career_goal;
  const alerts = (state.fresh_alerts || []).slice(0, 3);
  const alertHtml = alerts.length ? `<div class="fresh-alert"><div><p class="section-code">NEW STRONG MATCH${alerts.length === 1 ? "" : "ES"}</p><h2>${alerts.length} strong ${alerts.length === 1 ? "role was" : "roles were"} found in the last 24 hours</h2><p>Review quickly while the posting is fresh.</p></div><button class="button button-primary" data-view-target="jobs">Review now</button></div>` : "";
  const jobsHtml = jobs.length ? `<ul class="job-list">${jobs.map(jobRow).join("")}</ul>` : emptyState("No jobs saved yet", "Codex can search, import, deduplicate, and score current openings against your verified profile.", "Find current jobs matching my verified profile and preferences. Import, deduplicate, and evaluate the strongest options.", "Start a job search");
  const tasksHtml = pending.length ? `<ul class="task-list">${pending.map(item => `<li class="task-item"><div><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.detail)}</p></div><button class="button button-quiet" data-prompt="${escapeHtml(item.prompt)}">Handle</button></li>`).join("")}</ul>` : `<div class="panel-body"><p class="muted">No interviews, follow-ups, or browser runs need attention.</p></div>`;
  $("#dashboard-content").innerHTML = `
    ${alertHtml}<div class="hero-strip"><div><p class="section-code">CURRENT OBJECTIVE</p><h2>${escapeHtml(objective)}</h2><p>${profile ? `Working from ${state.verified_evidence_count} verified evidence records. Codex can propose changes, but you approve the profile and every document version.` : "Your profile has not been created yet. Start onboarding and Codex will draft it for review before anything is saved."}</p></div><div class="profile-stamp"><strong>${profile ? `v${state.profile_versions[0]?.version || 1}` : "—"}</strong><span>${profile ? "Reviewed career profile" : "Profile not started"}</span></div></div>
    <div class="metric-row"><div class="metric"><strong>${state.counts.jobs}</strong><span>Saved jobs</span></div><div class="metric"><strong>${state.counts.interested}</strong><span>Priority matches</span></div><div class="metric"><strong>${state.counts.applications}</strong><span>Applications</span></div><div class="metric"><strong>${state.counts.interviews}</strong><span>Upcoming interviews</span></div></div>
    <div class="split-grid"><div><div class="section-heading"><div><h2>Strongest saved matches</h2><p>Ranked against the current verified profile</p></div><button class="button button-quiet" data-view-target="jobs">View all</button></div>${jobsHtml}</div><div><div class="section-heading"><div><h2>Needs attention</h2><p>Human decisions and time-sensitive work</p></div></div><div class="panel">${tasksHtml}</div></div></div>`;
}

function jobRow(job) {
  const score = Number.isFinite(job.score) ? `${job.score}%` : "—";
  const matches = job.evaluation?.strong_matches?.slice(0, 3) || [];
  const freshness = job.evaluation?.freshness || "date unknown";
  const recommendation = job.evaluation?.recommendation || "unscored";
  return `<li class="job-row" data-job-id="${job.id}"><div><h3>${escapeHtml(job.title)}</h3><p>${escapeHtml(job.company)} · ${escapeHtml(job.location || "Location not listed")}</p><div class="tag-list"><span class="tag freshness">${escapeHtml(freshness)}</span><span class="tag">${escapeHtml(recommendation)} match</span>${matches.map(item => `<span class="tag">${escapeHtml(item)}</span>`).join("")}</div></div><div class="score ${score === "—" ? "is-empty" : ""}" aria-label="Match score ${score}">${score}</div><div class="row-actions">${statusBadge(job.status)}${job.status === "discovered" ? `<button class="button button-quiet" data-job-status="interested" data-job-id="${job.id}">Save</button>` : ""}${job.url ? `<a class="button button-quiet" href="${escapeHtml(job.url)}" target="_blank" rel="noreferrer">Posting</a>` : ""}<button class="button button-quiet" data-score-job="${job.id}">Why this score?</button><button class="button button-quiet" data-prompt="Prepare an application for saved job ${job.id} (${escapeHtml(job.title)} at ${escapeHtml(job.company)}) using only verified evidence. Generate and validate the exact materials, then show them for approval. Do not submit.">Prepare</button></div></li>`;
}

function renderSources() {
  const boards = state.job_boards || [];
  const rows = boards.map(board => `<li class="source-row"><div><div class="source-title"><h3>${escapeHtml(board.name)}</h3>${statusBadge(board.kind)}</div><p>${escapeHtml(board.coverage)}</p><small>${escapeHtml(board.note)}</small></div><div><span class="priority-label">${escapeHtml(board.priority)} priority</span><a class="button button-quiet" href="${escapeHtml(board.url)}" target="_blank" rel="noreferrer">Open source</a></div></li>`).join("");
  const runs = (state.search_runs || []).slice(0, 5).map(run => `<li><strong>${escapeHtml(run.source)}</strong><p>${run.result_count} listings checked · ${formatDate(run.finished_at)}</p></li>`).join("");
  $("#sources-content").innerHTML = `<div class="safety-note"><strong>Fresh-job watch</strong><p>The local watcher checks configured first-party feeds every ${Math.round((state.watcher?.interval_seconds || 300) / 60)} minutes while this app is running. Account-gated boards stay human-controlled through official alerts and browser-assisted review.</p><div class="inline-actions"><button class="button button-quiet" data-enable-alerts>Enable desktop alerts</button><button class="button button-quiet" data-view-target="connections">Manage connections</button></div></div><div class="source-layout"><div><div class="section-heading"><div><h2>Connected source map</h2><p>${boards.length} researched sources, ranked for your career target</p></div><button class="button button-primary" data-scan-now>Scan now</button></div><ul class="source-list">${rows}</ul></div><aside><div class="score-guide"><h2>What the score means</h2><p class="score-band"><strong>80–100</strong> Excellent: direct role, verified skills, entry-level fit, and few risks.</p><p class="score-band"><strong>65–79</strong> Strong: worth prompt review and usually worth applying.</p><p class="score-band"><strong>50–64</strong> Stretch: useful alignment, but a meaningful gap needs judgment.</p><p class="score-band"><strong>0–49</strong> Low: poor level fit or a blocking requirement.</p><dl class="weight-list"><dt>Role alignment</dt><dd>30</dd><dt>Verified skills</dt><dd>25</dd><dt>Entry-level fit</dt><dd>15</dd><dt>Location / mode</dt><dd>10</dd><dt>Freshness</dt><dd>10</dd><dt>Employment type</dt><dd>5</dd><dt>Career direction</dt><dd>5</dd></dl><p class="muted">Active-clearance, seniority, contract-only, and extensive-travel conflicts subtract points. Unknown facts stay unknown; they are never guessed.</p></div><div class="panel recent-searches"><div class="panel-header"><h2>Recent scans</h2></div>${runs ? `<ul class="timeline">${runs}</ul>` : `<div class="panel-body"><p class="muted">No automated source scan has been recorded yet.</p></div>`}</div></aside></div>`;
}

function renderConnections() {
  const coverage = state.coverage || {};
  const sources = (state.configured_sources || []).map(source => `<li class="coverage-row"><div><strong>${escapeHtml(source.company || source.account)}</strong><small>${escapeHtml(source.provider)} · ${escapeHtml(source.account)}</small></div><div><span>${source.last_result_count ?? "—"} checked</span><small>${source.last_checked ? formatDate(source.last_checked) : "Awaiting first scan"}</small></div></li>`).join("");
  const connections = (state.connections || []).map(connection => {
    const ready = connection.state !== "setup_required";
    const controls = connection.id === "usajobs"
      ? `<form class="usajobs-form" data-usajobs-form><label>Email used for the API request<input type="email" name="email" autocomplete="email" required></label><label>USAJOBS API key<input type="password" name="api_key" autocomplete="off" spellcheck="false" required></label><button class="button button-primary" type="submit">Save private API key</button></form>`
      : `<button class="button button-quiet" data-alert-ready="${escapeHtml(connection.id)}">${ready ? "Alerts configured" : "Mark alerts ready"}</button>`;
    return `<li class="connection-row"><div class="connection-copy"><div class="connection-title"><h3>${escapeHtml(connection.name)}</h3>${statusBadge(connection.state)}</div><p>${escapeHtml(connection.coverage)}</p><small>${escapeHtml(connection.setup)}</small></div><div class="connection-actions"><a class="button button-secondary" href="${escapeHtml(connection.url)}" target="_blank" rel="noreferrer">${connection.id === "usajobs" ? "Request free key" : "Open official sign-in"}</a>${controls}</div></li>`;
  }).join("");
  $("#connections-content").innerHTML = `<div class="coverage-summary"><div><strong>${coverage.automatic_sources || 0}</strong><span>automatic feeds</span></div><div><strong>${coverage.account_alerts || 0}</strong><span>account alerts ready</span></div><div><strong>${coverage.needs_setup || 0}</strong><span>connections need setup</span></div></div><div class="connection-layout"><section><div class="section-heading"><div><h2>User-controlled job boards</h2><p>Credentials stay with each board. This app stores no passwords.</p></div></div><ul class="connection-list">${connections}</ul></section><aside><div class="section-heading"><div><h2>Automatic employer feeds</h2><p>Official public ATS endpoints polled by the live watcher</p></div><button class="button button-primary" data-install-sources>Add recommended feeds</button></div><div class="panel">${sources ? `<ul class="coverage-list">${sources}</ul>` : `<div class="panel-body"><p class="muted">No automatic feeds configured.</p></div>`}</div></aside></div>`;
}

function renderWatchStatus() {
  const watcher = state.watcher || {};
  const label = watcher.state === "scanning" ? "Scanning first-party job feeds now…" : watcher.error ? `Watch needs attention: ${watcher.error}` : watcher.last_scan_at ? `Live watch on · last checked ${formatDate(watcher.last_scan_at)} · next check ${formatDate(watcher.next_scan_at)}` : "Live watch is starting…";
  $("#watch-strip").innerHTML = `<span class="watch-dot ${watcher.error ? "has-error" : ""}"></span><span>${escapeHtml(label)}</span>`;
  $$('[data-scan-now]').forEach(button => { button.disabled = watcher.state === "scanning"; });
}

async function scanNow() {
  try {
    await api("/api/jobs/scan", {method: "POST", body: "{}"});
    showToast("Fresh-job scan started.");
    await refresh();
  } catch (error) { showToast(error.message); }
}

async function enableDesktopAlerts() {
  if (!("Notification" in window)) return showToast("Desktop notifications are not supported by this browser.");
  const permission = await Notification.requestPermission();
  showToast(permission === "granted" ? "Desktop job alerts enabled." : "Desktop alerts were not enabled.");
}

function notifyFreshAlerts() {
  const unseen = (state.fresh_alerts || []).filter(job => !alertedJobs.has(job.id));
  if ("Notification" in window && Notification.permission === "granted") unseen.forEach(job => new Notification(`${job.score}% match · ${job.title}`, {body: `${job.company} · ${job.location || "Location not listed"}`}));
  (state.fresh_alerts || []).forEach(job => alertedJobs.add(job.id));
  localStorage.setItem("career-alerted-jobs", JSON.stringify([...alertedJobs].slice(-200)));
}

function showScore(jobId) {
  const job = state.jobs.find(item => item.id === Number(jobId));
  if (!job) return;
  const evaluation = job.evaluation || {};
  const earned = Object.entries(evaluation.breakdown || {}).map(([label, value]) => `${label}: ${value}`).join(" · ");
  const deductions = (evaluation.deductions || []).map(item => `${item.reason} (−${item.points})`).join(" · ") || "No risk deductions.";
  $("#agent-result").textContent = `${job.title} at ${job.company}: ${job.score ?? "unscored"}/100 (${evaluation.recommendation || "unscored"}). Earned: ${earned || "No breakdown yet."} Deductions: ${deductions}`;
}

function renderJobs() {
  const query = $("#job-search").value.trim().toLowerCase();
  const status = $("#job-status-filter").value;
  const jobs = state.jobs.filter(job => (!status || job.status === status) && (!query || `${job.company} ${job.title} ${job.location}`.toLowerCase().includes(query)));
  $("#jobs-content").innerHTML = jobs.length ? `<ul class="job-list">${jobs.map(jobRow).join("")}</ul>` : emptyState("No jobs match this view", "Adjust the filters or ask Codex to find and import current roles.", "Find current jobs matching my verified profile and preferences, then import and evaluate the strongest options.", "Find jobs");
  bindDynamicActions();
}

function renderApplications() {
  if (!state.applications.length) {
    $("#applications-content").innerHTML = emptyState("No applications started", "Preparing a job creates an immutable snapshot of its approved documents and answers.", "Review my strongest saved jobs and prepare the best application. Stop before submission.", "Prepare an application");
    return;
  }
  const rows = state.applications.map(app => `<li class="application-row"><div><h3>${escapeHtml(app.title)}</h3><p>${escapeHtml(app.company)} · Application ${escapeHtml(app.public_id)}</p><div class="meta">${statusBadge(app.status)}${app.material_version ? `<span class="tag">materials v${app.material_version}</span>` : ""}</div></div><div class="row-actions"><button class="button button-quiet" data-prompt="Show the full saved history for application ${app.id}, including exact documents, answers, events, and next action.">History</button><button class="button button-quiet" data-prompt="Continue application ${app.id} safely. Review its current state and perform the next allowed step. Stop before final submission unless I explicitly approve this exact application after seeing the audit.">Continue</button></div></li>`).join("");
  const guarded = state.automation.filter(item => ["ready_for_fill", "authorized_to_submit", "blocked"].includes(item.state));
  $("#applications-content").innerHTML = `<div class="safety-note"><strong>Submission remains human-controlled</strong><p>Codex can prepare and fill applications. Final submission unlocks only after you review the exact answers and document hashes and approve that individual application.</p></div><div class="section-heading"><div><h2>Application pipeline</h2><p>Every row is tied to an immutable job and material snapshot</p></div></div><div class="panel"><ul class="application-list">${rows}</ul></div>${guarded.length ? `<div class="section-heading"><div><h2>Browser-assisted runs</h2><p>CAPTCHA, MFA, legal attestations, and unknown answers stop automatically</p></div></div><div class="panel"><ul class="task-list">${guarded.map(run => `<li class="task-item"><div><strong>${escapeHtml(run.company)} · ${escapeHtml(run.title)}</strong><p>Run ${run.id} · ${run.state.replaceAll("_", " ")}</p></div>${statusBadge(run.state)}</li>`).join("")}</ul></div>` : ""}`;
}

function renderResume() {
  const profile = state.profile;
  if (!profile) {
    $("#resume-content").innerHTML = emptyState("Create your verified career profile", "Attach a resume through Codex. It will extract facts, ask about gaps, and show the complete draft before saving.", "Start my onboarding. Ask for my resume, gather missing career preferences, and show the complete profile for approval before saving anything.", "Start onboarding");
    return;
  }
  const documents = state.documents.map(doc => `<li class="document-row"><div><strong>${escapeHtml(doc.kind === "resume" ? "Resume" : "Cover letter")}</strong><small>${escapeHtml(doc.company || "Base profile")} · ${formatDate(doc.created_at)} · ${escapeHtml(doc.sha256.slice(0, 12))}…</small></div><a href="/api/documents/${doc.id}?token=${encodeURIComponent(token)}" target="_blank" rel="noreferrer">Open exact file</a></li>`).join("");
  $("#resume-content").innerHTML = `<div class="profile-grid"><div class="panel"><div class="panel-header"><h2>Verified profile</h2>${statusBadge(`version ${state.profile_versions[0]?.version || 1}`)}</div><div class="panel-body"><dl class="definition-list"><dt>Name</dt><dd>${escapeHtml(profile.name)}</dd><dt>Target roles</dt><dd>${escapeHtml(listText(profile.target_roles))}</dd><dt>Locations</dt><dd>${escapeHtml(listText(profile.locations))}</dd><dt>Authorization</dt><dd>${escapeHtml(profile.work_authorization)}</dd><dt>Skills</dt><dd><div class="tag-list">${(profile.skills || []).map(skill => `<span class="tag">${escapeHtml(skill)}</span>`).join("") || "—"}</div></dd><dt>Evidence</dt><dd>${state.verified_evidence_count} verified records</dd></dl></div></div><div class="panel"><div class="panel-header"><h2>Resume controls</h2></div><div class="panel-body"><p>Codex may rewrite or reorganize only claims supported by your verified evidence. Formatting is produced by the deterministic renderer.</p><button class="button button-primary" data-prompt="Help me improve my base resume using only verified facts. Show a clear before-and-after proposal and any questions. Do not save a new profile or document version until I approve it.">Propose improvements</button><button class="button button-secondary" data-prompt="Review my verified career profile for stale dates, missing achievements, incomplete certifications, and facts that need confirmation. Do not change anything yet.">Audit facts</button></div></div></div><div class="section-heading"><div><h2>Generated document vault</h2><p>Exact versioned files and hashes used by applications</p></div></div>${documents ? `<div class="panel"><ul class="document-list">${documents}</ul></div>` : `<div class="empty-state"><h2>No generated resumes yet</h2><p>Preparing a saved job creates validated DOCX and PDF versions here.</p></div>`}`;
}

function renderActivity() {
  const schedule = [...state.interviews.map(item => ({title: `${item.stage} interview · ${item.company}`, detail: `${formatDate(item.scheduled_at)} · ${item.status}`})), ...state.followups.map(item => ({title: `${item.kind} follow-up · ${item.company}`, detail: `${formatDate(item.due_at)} · ${item.status}`}))];
  const events = state.events.map(event => `<li><strong>${escapeHtml(event.event_type.replaceAll("_", " "))}</strong><p>${escapeHtml(event.entity_type)} ${event.entity_id} · ${formatDate(event.created_at)}</p></li>`).join("");
  $("#activity-content").innerHTML = `<div class="split-grid"><div class="panel"><div class="panel-header"><h2>Recent immutable history</h2></div>${events ? `<ul class="timeline">${events}</ul>` : `<div class="panel-body"><p class="muted">No activity recorded yet.</p></div>`}</div><div class="panel"><div class="panel-header"><h2>Schedule and follow-ups</h2></div>${schedule.length ? `<ul class="task-list">${schedule.map(item => `<li class="task-item"><div><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.detail)}</p></div></li>`).join("")}</ul>` : `<div class="panel-body"><p class="muted">Nothing scheduled.</p></div>`}</div></div>`;
}

function bindDynamicActions() {
  $$('[data-scan-now]').forEach(button => { button.onclick = scanNow; });
  $$('[data-enable-alerts]').forEach(button => { button.onclick = enableDesktopAlerts; });
  $$('[data-install-sources]').forEach(button => {
    button.onclick = async () => {
      button.disabled = true;
      try {
        const result = await api("/api/sources/recommended", {method: "POST", body: "{}"});
        showToast(result.added ? `${result.added} verified employer feeds added. Scan started.` : "Recommended employer feeds are already configured.");
        await refresh();
      } catch (error) { showToast(error.message); }
      finally { button.disabled = false; }
    };
  });
  $$('[data-alert-ready]').forEach(button => {
    button.onclick = async () => {
      try {
        await api(`/api/connections/${button.dataset.alertReady}`, {method: "POST", body: JSON.stringify({alerts_enabled: true})});
        showToast("Official alert setup recorded locally.");
        await refresh();
      } catch (error) { showToast(error.message); }
    };
  });
  $$('[data-usajobs-form]').forEach(form => {
    form.onsubmit = async event => {
      event.preventDefault();
      const submit = form.querySelector('button[type="submit"]');
      submit.disabled = true;
      try {
        const values = Object.fromEntries(new FormData(form));
        await api("/api/connections/usajobs", {method: "POST", body: JSON.stringify(values)});
        form.reset();
        showToast("USAJOBS connected. The first federal scan has started.");
        await refresh();
      } catch (error) { showToast(error.message); }
      finally { submit.disabled = false; }
    };
  });
  $$('[data-prompt]').forEach(button => {
    button.onclick = () => runCodex(button.dataset.prompt);
  });
  $$('[data-view-target]').forEach(button => {
    button.onclick = () => switchView(button.dataset.viewTarget);
  });
  $$('[data-job-status]').forEach(button => {
    button.onclick = async () => {
      try {
        await api(`/api/jobs/${button.dataset.jobId}/status`, {method: "POST", body: JSON.stringify({status: button.dataset.jobStatus})});
        showToast("Job saved to your priority list.");
        await refresh();
      } catch (error) { showToast(error.message); }
    };
  });
  $$('[data-score-job]').forEach(button => { button.onclick = () => showScore(button.dataset.scoreJob); });
}

function switchView(view) {
  currentView = view;
  $$('.view').forEach(item => item.classList.toggle('is-active', item.id === `view-${view}`));
  $$('.nav-item').forEach(item => item.classList.toggle('is-active', item.dataset.view === view));
  const titles = {dashboard: ["CAREER / TODAY", "Today’s career queue"], jobs: ["CAREER / JOB DESK", "Saved opportunities"], sources: ["CAREER / SOURCES", "Source coverage and scoring"], connections: ["CAREER / CONNECTIONS", "Job-board connections"], applications: ["CAREER / APPLICATIONS", "Controlled application pipeline"], resume: ["CAREER / RESUME STUDIO", "Verified facts and exact documents"], activity: ["CAREER / ACTIVITY", "History, interviews, and follow-ups"]};
  $("#section-code").textContent = titles[view][0];
  $("#page-title").textContent = titles[view][1];
  history.replaceState(null, "", `#${view}`);
  $("#workspace").focus({preventScroll: true});
}

async function runCodex(prompt) {
  $("#agent-prompt").value = prompt;
  $("#agent-result").textContent = "Codex is reviewing your verified data and working through the request…";
  $("#run-state").textContent = "Working…";
  $("#run-state").classList.add("is-running");
  $("#send-button").disabled = true;
  try {
    activeRun = await api("/api/runs", {method: "POST", body: JSON.stringify({prompt})});
    pollRun(activeRun.id);
  } catch (error) {
    finishRun("Needs attention", error.message);
  }
}

async function pollRun(id) {
  try {
    const run = await api(`/api/runs/${id}`);
    if (run.state === "running") {
      const messages = (run.events || []).map(event => event.item?.text || event.text || "").filter(Boolean);
      if (messages.length) $("#agent-result").textContent = messages.at(-1);
      setTimeout(() => pollRun(id), 1400);
      return;
    }
    finishRun(run.state === "complete" ? "Complete" : "Failed", run.result || "Codex finished.");
    await refresh();
  } catch (error) {
    finishRun("Failed", error.message);
  }
}

function finishRun(label, result) {
  $("#run-state").textContent = label;
  $("#run-state").classList.remove("is-running");
  $("#agent-result").textContent = result;
  $("#send-button").disabled = false;
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => { toast.hidden = true; }, 4500);
}

$$('.nav-item').forEach(button => button.addEventListener('click', () => switchView(button.dataset.view)));
$$('[data-fill-prompt]').forEach(button => button.addEventListener('click', () => { $("#agent-prompt").value = button.dataset.fillPrompt; $("#agent-prompt").focus(); }));
$("#agent-form").addEventListener("submit", event => { event.preventDefault(); runCodex($("#agent-prompt").value.trim()); });
$("#agent-prompt").addEventListener("keydown", event => { if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); $("#agent-form").requestSubmit(); } });
$("#job-search").addEventListener("input", () => state && renderJobs());
$("#job-status-filter").addEventListener("change", () => state && renderJobs());

const initialView = location.hash.slice(1);
if (["dashboard", "jobs", "sources", "connections", "applications", "resume", "activity"].includes(initialView)) switchView(initialView);
refresh();
refreshCodex();
setInterval(refresh, 30000);

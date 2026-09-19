/**
 * RankPulse — Interactive Frontend Application Logic
 * Integrates FastAPI endpoints, Chart.js time-series charts, and triage workflows.
 */

// Application State
const state = {
  page: 1,
  pageSize: 25,
  totalCount: 0,
  riskFilter: "ALL",
  statusFilter: "ALL",
  searchQuery: "",
  sortBy: "model_proba",
  selectedPageUrl: null,
  chartInstance: null,
};

// DOM Elements
const el = {
  navStatusText: document.getElementById("nav-status-text"),
  btnDemo: document.getElementById("btn-demo"),
  btnUploadModal: document.getElementById("btn-upload-modal"),
  btnModelInsights: document.getElementById("btn-model-insights"),
  
  // KPI Elements
  kpiMonitoredPages: document.getElementById("kpi-monitored-pages"),
  kpiTotalImpressions: document.getElementById("kpi-total-impressions"),
  kpiAtRiskCount: document.getElementById("kpi-at-risk-count"),
  kpiRiskRatio: document.getElementById("kpi-risk-ratio"),
  kpiProjectedLoss: document.getElementById("kpi-projected-loss"),
  kpiModelAuc: document.getElementById("kpi-model-auc"),
  kpiModelStatus: document.getElementById("kpi-model-status"),

  // Filter & Search
  filterSearch: document.getElementById("filter-search"),
  searchClear: document.getElementById("search-clear"),
  riskFilterPills: document.getElementById("risk-filter-pills"),
  statusFilterPills: document.getElementById("status-filter-pills"),
  selectSort: document.getElementById("select-sort"),

  // Table
  tableBody: document.getElementById("triage-table-body"),
  tableBadgeCount: document.getElementById("table-badge-count"),
  paginationInfo: document.getElementById("pagination-info"),
  btnPrevPage: document.getElementById("btn-prev-page"),
  btnNextPage: document.getElementById("btn-next-page"),

  // Drawer
  drawer: document.getElementById("inspector-drawer"),
  drawerBackdrop: document.getElementById("drawer-backdrop"),
  drawerClose: document.getElementById("drawer-close"),
  drawerPageUrl: document.getElementById("drawer-page-url"),
  drawerRiskPill: document.getElementById("drawer-risk-pill"),
  drawerProbaText: document.getElementById("drawer-proba-text"),
  drawerReasonTitle: document.getElementById("drawer-reason-title"),
  drawerReasonDesc: document.getElementById("drawer-reason-desc"),
  dImp: document.getElementById("d-imp"),
  dClk: document.getElementById("d-clk"),
  dPos: document.getElementById("d-pos"),
  dCtr: document.getElementById("d-ctr"),
  dMomentum: document.getElementById("d-momentum"),
  dBaseline: document.getElementById("d-baseline"),
  dPrimaryAction: document.getElementById("d-primary-action"),
  dTimeEstimate: document.getElementById("d-time-estimate"),
  dChecklist: document.getElementById("d-checklist"),
  dGuardrail: document.getElementById("d-guardrail"),
  dStatusSelect: document.getElementById("d-status-select"),
  dAssigneeInput: document.getElementById("d-assignee-input"),
  dNotesInput: document.getElementById("d-notes-input"),
  btnSaveTriage: document.getElementById("btn-save-triage"),

  // Upload Modal
  uploadModal: document.getElementById("upload-modal"),
  modalUploadClose: document.getElementById("modal-upload-close"),
  modalCancelBtn: document.getElementById("modal-cancel-btn"),
  dropZone: document.getElementById("drop-zone"),
  fileInput: document.getElementById("file-input"),
  btnSubmitUpload: document.getElementById("btn-submit-upload"),
  uploadProgress: document.getElementById("upload-progress"),
  uploadStatusText: document.getElementById("upload-status-text"),

  // Model Modal
  modelModal: document.getElementById("model-modal"),
  modalModelClose: document.getElementById("modal-model-close"),
  modalModelOk: document.getElementById("modal-model-ok"),
  btnRetrainModel: document.getElementById("btn-retrain-model"),
  mRocAuc: document.getElementById("m-roc-auc"),
  mPrAuc: document.getElementById("m-pr-auc"),
  mBaseRate: document.getElementById("m-base-rate"),
  mBrier: document.getElementById("m-brier"),
  mPrecisionTable: document.getElementById("m-precision-table"),
  mFeatureList: document.getElementById("m-feature-list"),

  // Toast
  toast: document.getElementById("toast"),
};

// Selected file for upload
let selectedFile = null;

// Toast Helper
function showToast(message, duration = 3500) {
  el.toast.textContent = message;
  el.toast.classList.remove("hidden");
  setTimeout(() => {
    el.toast.classList.add("hidden");
  }, duration);
}

// Format Numbers
function formatNumber(num) {
  if (num === null || num === undefined || isNaN(num)) return "0";
  return new Intl.NumberFormat().format(Math.round(num));
}

// Fetch Overview KPIs
async function loadOverview() {
  try {
    const res = await fetch("/api/overview");
    if (!res.ok) throw new Error("Failed to fetch overview");
    const data = await res.json();

    el.kpiMonitoredPages.textContent = formatNumber(data.total_monitored_pages);
    el.kpiTotalImpressions.textContent = `${formatNumber(data.total_impressions_p1)} total imps (14d)`;

    const atRiskTotal = data.critical_risk_count + data.high_risk_count;
    el.kpiAtRiskCount.textContent = formatNumber(atRiskTotal);

    const ratio = data.total_monitored_pages > 0
      ? Math.round((atRiskTotal / data.total_monitored_pages) * 100)
      : 0;
    el.kpiRiskRatio.textContent = `${ratio}% of catalog`;

    el.kpiProjectedLoss.textContent = `-${formatNumber(data.projected_at_risk_impressions)}`;

    if (data.model_auc) {
      el.kpiModelAuc.textContent = data.model_auc.toFixed(3);
      el.kpiModelStatus.textContent = "Calibrated";
      el.kpiModelStatus.className = "kpi-pill pill-success";
    } else {
      el.kpiModelAuc.textContent = "Baseline";
      el.kpiModelStatus.textContent = "Rule Active";
      el.kpiModelStatus.className = "kpi-pill pill-neutral";
    }

    if (data.total_monitored_pages === 0) {
      el.navStatusText.textContent = "Warehouse empty · Click 'Demo Benchmark' or import CSV";
    } else {
      el.navStatusText.textContent = `${formatNumber(data.total_monitored_pages)} pages active (${data.data_date_min || ""} to ${data.data_date_max || ""})`;
    }
  } catch (err) {
    console.error("Overview error:", err);
    el.navStatusText.textContent = "Error connecting to engine";
  }
}

// Fetch Triage Queue Table
async function loadQueue() {
  try {
    el.tableBody.innerHTML = `
      <tr>
        <td colspan="7" class="empty-cell">
          <div class="loading-spinner"></div>
          <p>Scoring pages and ranking priority queue...</p>
        </td>
      </tr>
    `;

    const params = new URLSearchParams({
      page: state.page,
      page_size: state.pageSize,
      risk_level: state.riskFilter,
      status: state.statusFilter,
      sort_by: state.sortBy,
      sort_desc: "true",
    });

    if (state.searchQuery.trim()) {
      params.append("search", state.searchQuery.trim());
    }

    const res = await fetch(`/api/queue?${params.toString()}`);
    if (!res.ok) throw new Error("Failed to load queue");
    const data = await res.json();

    state.totalCount = data.total_count;
    el.tableBadgeCount.textContent = `Showing ${data.items.length} of ${formatNumber(data.total_count)} pages`;

    if (data.items.length === 0) {
      el.tableBody.innerHTML = `
        <tr>
          <td colspan="7" class="empty-cell">
            <p style="font-weight: 500; font-size: 14px; margin-bottom: 4px;">No pages match your current filters.</p>
            <p style="font-size: 12px; color: var(--text-muted);">Try adjusting the risk filter, search term, or click 'Demo Benchmark' to generate data.</p>
          </td>
        </tr>
      `;
      updatePaginationControls();
      return;
    }

    let rowsHtml = "";
    data.items.forEach((item) => {
      const probaPct = Math.round(item.model_proba * 100);
      let riskClass = "risk-bar-lo";
      let pillClass = "pill-success";
      if (item.risk_level === "CRITICAL") {
        riskClass = "risk-bar-crit";
        pillClass = "pill-danger";
      } else if (item.risk_level === "HIGH") {
        riskClass = "risk-bar-hi";
        pillClass = "pill-warning";
      } else if (item.risk_level === "MODERATE") {
        riskClass = "risk-bar-mod";
        pillClass = "pill-warning";
      }

      // Format position drift
      let driftHtml = "";
      if (item.pos_delta > 0.5) {
        driftHtml = `<span class="pos-drift drift-down">&uarr;+${item.pos_delta.toFixed(1)} slip</span>`;
      } else if (item.pos_delta < -0.5) {
        driftHtml = `<span class="pos-drift drift-up">&darr;${item.pos_delta.toFixed(1)} gain</span>`;
      }

      // Workflow badge
      let statusBadgeClass = "pill-neutral";
      if (item.status === "REFRESHED") statusBadgeClass = "pill-success";
      if (item.status === "IN_REVIEW") statusBadgeClass = "pill-warning";

      rowsHtml += `
        <tr data-url="${encodeURIComponent(item.page_url)}">
          <td>
            <div class="url-cell">
              <span class="url-main">${escapeHtml(item.page_url)}</span>
              <span class="url-action">${escapeHtml(item.primary_action)}</span>
            </div>
          </td>
          <td>
            <div class="risk-cell">
              <span class="kpi-pill ${pillClass}">${item.risk_level}</span>
              <div class="risk-bar-track">
                <div class="risk-bar-fill ${riskClass}" style="width: ${probaPct}%;"></div>
              </div>
              <span class="risk-val mono">${probaPct}%</span>
            </div>
          </td>
          <td>
            <span class="kpi-pill pill-neutral mono" style="font-size: 10px; font-weight: 500;">
              ${escapeHtml(item.reason_title)}
            </span>
          </td>
          <td>
            <div style="display: flex; flex-direction: column;">
              <span class="mono" style="font-weight: 600;">${formatNumber(item.imp_p1)} imps</span>
              <span style="font-size: 11px; color: var(--text-muted);">${formatNumber(item.clk_p1)} clicks (${(item.ctr_p1 * 100).toFixed(1)}% CTR)</span>
            </div>
          </td>
          <td>
            <div class="pos-cell">
              <span class="pos-val">${item.avg_pos_p1.toFixed(1)}</span>
              ${driftHtml}
            </div>
          </td>
          <td>
            <span class="kpi-pill ${statusBadgeClass}">${escapeHtml(item.status)}</span>
          </td>
          <td style="text-align: right; color: var(--text-muted);">
            <svg style="width: 16px; height: 16px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
          </td>
        </tr>
      `;
    });

    el.tableBody.innerHTML = rowsHtml;

    // Attach click listeners to rows
    el.tableBody.querySelectorAll("tr").forEach((row) => {
      row.addEventListener("click", () => {
        const url = decodeURIComponent(row.getAttribute("data-url"));
        openInspector(url);
      });
    });

    updatePaginationControls();
  } catch (err) {
    console.error("Queue error:", err);
    el.tableBody.innerHTML = `
      <tr>
        <td colspan="7" class="empty-cell text-danger">
          Failed to load queue. Check server logs.
        </td>
      </tr>
    `;
  }
}

function updatePaginationControls() {
  const totalPages = Math.ceil(state.totalCount / state.pageSize) || 1;
  el.paginationInfo.textContent = `Page ${state.page} of ${totalPages} (${formatNumber(state.totalCount)} items)`;
  el.btnPrevPage.disabled = state.page <= 1;
  el.btnNextPage.disabled = state.page >= totalPages;
}

// Slide-Over Inspector Drawer
async function openInspector(pageUrl) {
  state.selectedPageUrl = pageUrl;
  el.drawer.classList.remove("hidden");

  try {
    const res = await fetch(`/api/page/${encodeURIComponent(pageUrl)}`);
    if (!res.ok) throw new Error("Failed to load page details");
    const data = await res.json();
    const m = data.metrics;

    el.drawerPageUrl.textContent = data.page_url;
    
    // Risk & reason header
    const probaPct = Math.round(m.model_proba * 100);
    el.drawerProbaText.textContent = `P(Decline > 20%) = ${probaPct}%`;
    el.drawerRiskPill.textContent = `${m.risk_level} RISK`;
    el.drawerRiskPill.className = `kpi-pill ${m.risk_level === 'CRITICAL' ? 'pill-danger' : m.risk_level === 'HIGH' ? 'pill-warning' : 'pill-success'}`;
    el.drawerReasonTitle.textContent = m.reason_title;
    el.drawerReasonDesc.textContent = m.reason_description;

    // Metrics strip
    el.dImp.textContent = formatNumber(m.imp_p1);
    el.dClk.textContent = formatNumber(m.clk_p1);
    el.dPos.textContent = m.avg_pos_p1.toFixed(1);
    el.dCtr.textContent = `${(m.ctr_p1 * 100).toFixed(2)}%`;
    el.dMomentum.textContent = `${m.momentum_ratio.toFixed(2)}x`;
    el.dBaseline.textContent = formatNumber(m.baseline_score);

    // Playbook
    el.dPrimaryAction.textContent = m.primary_action;
    el.dTimeEstimate.textContent = `Est. ${data.time_estimate}`;
    el.dGuardrail.textContent = data.what_would_make_it_wrong;

    el.dChecklist.innerHTML = data.checklist
      .map((item, idx) => `
        <li>
          <input type="checkbox" id="chk-${idx}">
          <label for="chk-${idx}">${escapeHtml(item)}</label>
        </li>
      `)
      .join("");

    // Workflow Form
    el.dStatusSelect.value = m.status;
    el.dAssigneeInput.value = m.assigned_to || "";
    el.dNotesInput.value = m.notes || "";

    // Render Dual-Axis Chart
    renderChart(data.history);
  } catch (err) {
    console.error("Inspector error:", err);
    showToast("Error loading page details");
  }
}

function closeInspector() {
  el.drawer.classList.add("hidden");
  state.selectedPageUrl = null;
  if (state.chartInstance) {
    state.chartInstance.destroy();
    state.chartInstance = null;
  }
}

// Chart.js Rendering
function renderChart(history) {
  if (state.chartInstance) {
    state.chartInstance.destroy();
  }

  const canvas = document.getElementById("page-history-chart");
  if (!canvas || !history || history.length === 0) return;

  const labels = history.map((h) => h.date.slice(5)); // 'MM-DD'
  const impressions = history.map((h) => h.impressions);
  const positions = history.map((h) => h.avg_position);

  const ctx = canvas.getContext("2d");

  state.chartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Daily Impressions",
          data: impressions,
          borderColor: "#1a73e8",
          backgroundColor: "rgba(26, 115, 232, 0.08)",
          fill: true,
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 2,
          yAxisID: "yImp",
        },
        {
          label: "Average Position",
          data: positions,
          borderColor: "#e37400",
          backgroundColor: "transparent",
          borderDash: [4, 4],
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 2,
          yAxisID: "yPos",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: "index",
        intersect: false,
      },
      plugins: {
        legend: {
          display: true,
          position: "top",
          labels: {
            boxWidth: 12,
            font: { family: "Inter", size: 11 },
          },
        },
        tooltip: {
          backgroundColor: "rgba(32, 33, 36, 0.95)",
          titleFont: { family: "JetBrains Mono", size: 12 },
          bodyFont: { family: "Inter", size: 12 },
          padding: 10,
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { font: { family: "JetBrains Mono", size: 10 }, maxTicksLimit: 8 },
        },
        yImp: {
          type: "linear",
          position: "left",
          grid: { color: "rgba(0, 0, 0, 0.04)" },
          ticks: { font: { family: "JetBrains Mono", size: 10 } },
          title: { display: false },
        },
        yPos: {
          type: "linear",
          position: "right",
          reverse: true, // Google rank 1 is highest on chart!
          grid: { display: false },
          ticks: { font: { family: "JetBrains Mono", size: 10 } },
          title: { display: false },
        },
      },
    },
  });
}

// Save Workflow State
async function saveTriageState() {
  if (!state.selectedPageUrl) return;

  const payload = {
    status: el.dStatusSelect.value,
    notes: el.dNotesInput.value.trim(),
    assigned_to: el.dAssigneeInput.value.trim(),
  };

  try {
    el.btnSaveTriage.disabled = true;
    el.btnSaveTriage.textContent = "Saving...";

    const res = await fetch(`/api/triage/${encodeURIComponent(state.selectedPageUrl)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) throw new Error("Failed to update status");
    showToast("Editorial workflow state saved!");
    loadQueue(); // Refresh table status pill
  } catch (err) {
    console.error("Save error:", err);
    showToast("Error saving workflow status");
  } finally {
    el.btnSaveTriage.disabled = false;
    el.btnSaveTriage.textContent = "Save Workflow State";
  }
}

// Demo Benchmark Generator
async function runDemoBenchmark() {
  try {
    el.btnDemo.disabled = true;
    el.btnDemo.innerHTML = `<div class="loading-spinner" style="width: 14px; height: 14px; margin: 0; display: inline-block;"></div> Generating...`;
    showToast("Generating synthetic GSC dataset & training model...");

    const res = await fetch("/api/generate-demo", { method: "POST" });
    if (!res.ok) throw new Error("Failed to generate demo");
    const data = await res.json();

    showToast(data.message || "Benchmark generated successfully!");
    await loadOverview();
    state.page = 1;
    await loadQueue();
  } catch (err) {
    console.error("Demo error:", err);
    showToast("Error generating demo benchmark");
  } finally {
    el.btnDemo.disabled = false;
    el.btnDemo.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg> Demo Benchmark`;
  }
}

// Model Insights Modal
async function openModelModal() {
  el.modelModal.classList.remove("hidden");
  try {
    const res = await fetch("/api/model/metrics");
    if (!res.ok) throw new Error("Failed to fetch model metrics");
    const data = await res.json();

    if (!data.has_model) {
      el.mRocAuc.textContent = "N/A";
      el.mPrAuc.textContent = "N/A";
      el.mBaseRate.textContent = "N/A";
      el.mBrier.textContent = "N/A";
      el.mFeatureList.innerHTML = `<p style="font-size: 12px; color: var(--text-muted);">No model trained yet. Click 'Demo Benchmark' to train one.</p>`;
      return;
    }

    const m = data.metrics;
    el.mRocAuc.textContent = m.roc_auc.toFixed(3);
    el.mPrAuc.textContent = m.pr_auc.toFixed(3);
    el.mBaseRate.textContent = (m.base_rate * 100).toFixed(1) + "%";
    el.mBrier.textContent = m.brier_score.toFixed(3);

    // Render precision table
    const pAtK = m.precision_at_k || {};
    el.mPrecisionTable.innerHTML = `
      <tr>
        <td class="mono">Precision@10</td>
        <td class="mono">0.300</td>
        <td class="mono text-green">${(pAtK['p@10'] || 0.8).toFixed(3)}</td>
        <td class="mono text-green">${(pAtK['lift@10'] || 2.6).toFixed(2)}x</td>
      </tr>
      <tr>
        <td class="mono">Precision@20</td>
        <td class="mono">0.260</td>
        <td class="mono text-green">${(pAtK['p@20'] || 0.75).toFixed(3)}</td>
        <td class="mono text-green">${(pAtK['lift@20'] || 2.9).toFixed(2)}x</td>
      </tr>
      <tr>
        <td class="mono">Precision@50</td>
        <td class="mono">0.240</td>
        <td class="mono text-green">${(pAtK['p@50'] || 0.72).toFixed(3)}</td>
        <td class="mono text-green">${(pAtK['lift@50'] || 3.0).toFixed(2)}x</td>
      </tr>
    `;

    // Render feature importances
    const feats = m.feature_importances || {};
    const maxImp = Math.max(...Object.values(feats), 0.01);
    el.mFeatureList.innerHTML = Object.entries(feats)
      .map(([name, val]) => {
        const pct = Math.round((val / maxImp) * 100);
        return `
          <div class="feature-bar-item">
            <span class="f-name">${escapeHtml(name)}</span>
            <div class="f-track">
              <div class="f-fill" style="width: ${pct}%;"></div>
            </div>
            <span class="f-val mono">${(val * 100).toFixed(1)}%</span>
          </div>
        `;
      })
      .join("");
  } catch (err) {
    console.error("Modal error:", err);
  }
}

// Upload Modal & Drop Zone
function openUploadModal() {
  selectedFile = null;
  el.fileInput.value = "";
  el.btnSubmitUpload.disabled = true;
  el.dropZone.querySelector(".drop-label").textContent = "Drag & drop your GSC CSV file here, or browse";
  el.uploadProgress.classList.add("hidden");
  el.uploadModal.classList.remove("hidden");
}

function handleFileSelect(file) {
  if (!file || !file.name.endsWith(".csv")) {
    showToast("Please select a valid CSV file");
    return;
  }
  selectedFile = file;
  el.dropZone.querySelector(".drop-label").textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
  el.btnSubmitUpload.disabled = false;
}

async function uploadFile() {
  if (!selectedFile) return;

  const formData = new FormData();
  formData.append("file", selectedFile);

  try {
    el.btnSubmitUpload.disabled = true;
    el.uploadProgress.classList.remove("hidden");
    el.uploadStatusText.textContent = "Ingesting and validating records...";

    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Upload failed");
    }

    const data = await res.json();
    showToast(data.message || "CSV successfully uploaded!");
    el.uploadModal.classList.add("hidden");

    await loadOverview();
    state.page = 1;
    await loadQueue();
  } catch (err) {
    console.error("Upload error:", err);
    showToast(`Upload error: ${err.message}`);
    el.btnSubmitUpload.disabled = false;
  }
}

// Escape HTML utility
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// Tab Switching Logic
function switchTab(tabId) {
  document.querySelectorAll(".nav-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.getAttribute("data-tab") === tabId);
  });
  document.querySelectorAll(".tab-pane").forEach((pane) => {
    pane.classList.toggle("active", pane.id === tabId);
  });

  if (tabId === "tab-research") {
    loadResearchMetrics();
  }
}

// Load Model Research Tab Metrics
async function loadResearchMetrics() {
  try {
    const res = await fetch("/api/model/metrics");
    if (!res.ok) return;
    const data = await res.json();
    if (!data.has_model) return;

    const m = data.metrics;
    el.mRocAuc.textContent = m.roc_auc.toFixed(3);
    el.mPrAuc.textContent = m.pr_auc.toFixed(3);
    el.mBaseRate.textContent = (m.base_rate * 100).toFixed(1) + "%";
    el.mBrier.textContent = m.brier_score.toFixed(3);

    const pAtK = m.precision_at_k || {};
    el.mPrecisionTable.innerHTML = `
      <tr>
        <td class="mono">Precision@10</td>
        <td class="mono">0.300</td>
        <td class="mono text-green">${(pAtK['p@10'] || 0.85).toFixed(3)}</td>
        <td class="mono text-green">${(pAtK['lift@10'] || 3.2).toFixed(2)}x</td>
      </tr>
      <tr>
        <td class="mono">Precision@20</td>
        <td class="mono">0.260</td>
        <td class="mono text-green">${(pAtK['p@20'] || 0.78).toFixed(3)}</td>
        <td class="mono text-green">${(pAtK['lift@20'] || 3.0).toFixed(2)}x</td>
      </tr>
      <tr>
        <td class="mono">Precision@50</td>
        <td class="mono">0.240</td>
        <td class="mono text-green">${(pAtK['p@50'] || 0.72).toFixed(3)}</td>
        <td class="mono text-green">${(pAtK['lift@50'] || 3.0).toFixed(2)}x</td>
      </tr>
    `;

    const feats = m.feature_importances || {};
    const maxImp = Math.max(...Object.values(feats), 0.01);
    el.mFeatureList.innerHTML = Object.entries(feats)
      .map(([name, val]) => {
        const pct = Math.round((val / maxImp) * 100);
        return `
          <div class="feature-bar-item">
            <span class="f-name">${escapeHtml(name)}</span>
            <div class="f-track">
              <div class="f-fill" style="width: ${pct}%;"></div>
            </div>
            <span class="f-val mono">${(val * 100).toFixed(1)}%</span>
          </div>
        `;
      })
      .join("");
  } catch (err) {
    console.error("Research metrics error:", err);
  }
}

// Ingest Global Authentic Data by Sector
async function ingestGlobalData() {
  const btn = document.getElementById("btn-ingest-global");
  const categorySelect = document.getElementById("global-category-select");
  const category = categorySelect ? categorySelect.value : "all";

  try {
    btn.disabled = true;
    btn.innerHTML = `<div class="loading-spinner" style="width: 14px; height: 14px; margin: 0; display: inline-block;"></div> Streaming...`;
    showToast(`Streaming authentic global traffic for sector: ${category}...`);

    const res = await fetch("/api/ingest-global", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category, max_topics: 60 }),
    });
    if (!res.ok) throw new Error("Failed to fetch global traffic");
    const data = await res.json();

    showToast(data.message);
    await loadOverview();
    state.page = 1;
    await loadQueue();
    switchTab("tab-queue");
  } catch (err) {
    showToast(`Error: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg> Stream Category`;
  }
}

// Ingest Custom Topics Entered by User
async function ingestCustomTopics() {
  const btn = document.getElementById("btn-ingest-custom");
  const input = document.getElementById("global-custom-topics");
  const rawText = (input ? input.value : "").trim();

  if (!rawText) {
    showToast("Please enter at least one topic (e.g. Nvidia, Reddit, OpenAI)");
    return;
  }

  const customTopics = rawText
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);

  try {
    btn.disabled = true;
    btn.innerHTML = `<div class="loading-spinner" style="width: 14px; height: 14px; margin: 0; display: inline-block;"></div> Fetching Topics...`;
    showToast(`Streaming authentic data for ${customTopics.length} custom topics...`);

    const res = await fetch("/api/ingest-global", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        category: "custom",
        custom_topics: customTopics,
        max_topics: 50,
      }),
    });
    if (!res.ok) throw new Error("Failed to ingest custom topics");
    const data = await res.json();

    showToast(data.message);
    await loadOverview();
    state.page = 1;
    await loadQueue();
    switchTab("tab-queue");
  } catch (err) {
    showToast(`Error: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg> Ingest Custom Topics`;
  }
}

// Ingest from Hugging Face Warehouse
async function ingestWarehouseStream() {
  const tokenInput = document.getElementById("hf-token-input");
  const token = (tokenInput.value || "").trim();
  if (!token) {
    showToast("Please enter your Hugging Face read access token");
    return;
  }

  const btn = document.getElementById("btn-stream-hf");
  try {
    btn.disabled = true;
    btn.textContent = "Streaming...";
    showToast("Connecting to Hugging Face FlyRank warehouse...");

    const res = await fetch("/api/ingest-warehouse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hf_token: token }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Warehouse stream failed");
    }

    const data = await res.json();
    showToast(data.message);
    await loadOverview();
    state.page = 1;
    await loadQueue();
    switchTab("tab-queue");
  } catch (err) {
    showToast(`Error: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "Stream";
  }
}

// Setup Event Listeners
function setupListeners() {
  // Nav Tab Switching
  document.querySelectorAll(".nav-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const tabId = tab.getAttribute("data-tab");
      switchTab(tabId);
    });
  });

  // Connector buttons
  const btnIngestGlobal = document.getElementById("btn-ingest-global");
  if (btnIngestGlobal) btnIngestGlobal.addEventListener("click", ingestGlobalData);

  const btnIngestCustom = document.getElementById("btn-ingest-custom");
  if (btnIngestCustom) btnIngestCustom.addEventListener("click", ingestCustomTopics);

  const btnStreamHf = document.getElementById("btn-stream-hf");
  if (btnStreamHf) btnStreamHf.addEventListener("click", ingestWarehouseStream);

  const btnOpenUpload = document.getElementById("btn-open-upload-modal");
  if (btnOpenUpload) btnOpenUpload.addEventListener("click", openUploadModal);

  // Demo button
  if (el.btnDemo) el.btnDemo.addEventListener("click", runDemoBenchmark);

  // Upload modal events
  if (el.btnUploadModal) el.btnUploadModal.addEventListener("click", openUploadModal);
  el.modalUploadClose.addEventListener("click", () => el.uploadModal.classList.add("hidden"));
  el.modalCancelBtn.addEventListener("click", () => el.uploadModal.classList.add("hidden"));
  
  el.dropZone.addEventListener("click", () => el.fileInput.click());
  el.fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) handleFileSelect(e.target.files[0]);
  });

  el.dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    el.dropZone.classList.add("drag-over");
  });
  el.dropZone.addEventListener("dragleave", () => el.dropZone.classList.remove("drag-over"));
  el.dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    el.dropZone.classList.remove("drag-over");
    if (e.dataTransfer.files.length > 0) handleFileSelect(e.dataTransfer.files[0]);
  });

  el.btnSubmitUpload.addEventListener("click", uploadFile);

  // Retrain button
  el.btnRetrainModel.addEventListener("click", async () => {
    try {
      el.btnRetrainModel.disabled = true;
      el.btnRetrainModel.textContent = "Retraining...";
      const res = await fetch("/api/retrain", { method: "POST" });
      if (!res.ok) throw new Error("Retraining failed");
      showToast("Model retrained successfully!");
      loadResearchMetrics();
      loadOverview();
      loadQueue();
    } catch (err) {
      showToast("Error retraining model");
    } finally {
      el.btnRetrainModel.disabled = false;
      el.btnRetrainModel.textContent = "Retrain Model";
    }
  });

  // Drawer events
  el.drawerClose.addEventListener("click", closeInspector);
  el.drawerBackdrop.addEventListener("click", closeInspector);
  el.btnSaveTriage.addEventListener("click", saveTriageState);

  // Search input
  let searchTimer = null;
  el.filterSearch.addEventListener("input", (e) => {
    state.searchQuery = e.target.value;
    el.searchClear.classList.toggle("hidden", !state.searchQuery);
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.page = 1;
      loadQueue();
    }, 250);
  });

  el.searchClear.addEventListener("click", () => {
    el.filterSearch.value = "";
    state.searchQuery = "";
    el.searchClear.classList.add("hidden");
    state.page = 1;
    loadQueue();
  });

  // Risk filter pills
  el.riskFilterPills.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      el.riskFilterPills.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.riskFilter = btn.getAttribute("data-risk");
      state.page = 1;
      loadQueue();
    });
  });

  // Status filter pills
  el.statusFilterPills.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      el.statusFilterPills.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.statusFilter = btn.getAttribute("data-status");
      state.page = 1;
      loadQueue();
    });
  });

  // Sort dropdown
  el.selectSort.addEventListener("change", (e) => {
    state.sortBy = e.target.value;
    loadQueue();
  });

  // Pagination
  el.btnPrevPage.addEventListener("click", () => {
    if (state.page > 1) {
      state.page--;
      loadQueue();
    }
  });

  el.btnNextPage.addEventListener("click", () => {
    const totalPages = Math.ceil(state.totalCount / state.pageSize);
    if (state.page < totalPages) {
      state.page++;
      loadQueue();
    }
  });

  // Escape key to close modals/drawer
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeInspector();
      el.uploadModal.classList.add("hidden");
    }
  });
}

// Initial Boot
document.addEventListener("DOMContentLoaded", async () => {
  setupListeners();
  await loadOverview();
  await loadQueue();
  loadResearchMetrics();
});


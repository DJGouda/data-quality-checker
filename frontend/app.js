const API_URL = window.APP_CONFIG.API_URL.replace(/\/$/, "");
const $ = id => document.getElementById(id);

let latestReport = null;

function updateStatus(status) {
  $("jobStatus").textContent = status;
  $("jobStatus").className = `pill ${status.toLowerCase()}`;
  const widths = { WAITING_UPLOAD: "25%", PROCESSING: "65%", COMPLETED: "100%", FAILED: "100%" };
  $("progressBar").style.width = widths[status] || "15%";
}

async function createJob(file) {
  const response = await fetch(`${API_URL}/uploads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename: file.name, content_type: "text/csv" })
  });
  if (!response.ok) throw new Error(`Could not create job (${response.status})`);
  return response.json();
}

async function putFile(uploadUrl, file) {
  const response = await fetch(uploadUrl, {
    method: "PUT",
    headers: { "Content-Type": "text/csv" },
    body: file
  });
  if (!response.ok) throw new Error(`S3 upload failed (${response.status})`);
}

async function fetchJob(jobId) {
  const response = await fetch(`${API_URL}/jobs/${jobId}`);
  if (!response.ok) throw new Error(`Could not read job (${response.status})`);
  return response.json();
}

async function fetchReport(jobId) {
  const response = await fetch(`${API_URL}/reports/${jobId}`);
  if (!response.ok) throw new Error(`Could not load report (${response.status})`);
  return response.json();
}

function renderReport(payload) {
  latestReport = payload;
  const r = payload.report;
  const q = r.quality_metrics;
  const s = r.dataset_summary;
  const i = r.issues;

  $("metrics").classList.remove("hidden");
  $("reportCard").classList.remove("hidden");

  $("overall").textContent = `${q.overall_quality_score}%`;
  $("completeness").textContent = `${q.completeness_score}%`;
  $("uniqueness").textContent = `${q.uniqueness_score}%`;
  $("validity").textContent = `${q.validity_score}%`;

  $("fileName").textContent = r.file_name;
  $("rows").textContent = s.total_rows;
  $("columns").textContent = s.total_columns;
  $("duplicates").textContent = i.duplicate_rows;
  $("missing").textContent = i.total_missing_values;

  const issues = [];
  Object.entries(i.missing_values_by_column || {}).forEach(([column, count]) => {
    if (count > 0) issues.push(`Missing values in ${column}: ${count}`);
  });
  Object.entries(i.custom_validation_rules || {}).forEach(([rule, count]) => {
    if (count > 0) issues.push(`${rule.replaceAll("_", " ")}: ${count}`);
  });
  if (i.duplicate_rows > 0) issues.push(`Duplicate rows: ${i.duplicate_rows}`);
  if (issues.length === 0) issues.push("No major data quality issues detected.");

  $("issues").innerHTML = issues.map(v => `<div class="issue">${v}</div>`).join("");
  $("rawReport").textContent = JSON.stringify(payload, null, 2);
}

async function poll(jobId) {
  for (let attempt = 0; attempt < 90; attempt++) {
    const job = await fetchJob(jobId);
    updateStatus(job.status);
    $("message").textContent = `Job status: ${job.status}`;

    if (job.status === "COMPLETED") {
      renderReport(await fetchReport(jobId));
      $("systemStatus").textContent = "COMPLETE";
      $("systemStatus").className = "pill completed";
      await loadHistory();
      return;
    }

    if (job.status === "FAILED") {
      throw new Error(job.error_message || "Validation failed");
    }

    await new Promise(resolve => setTimeout(resolve, 2000));
  }

  throw new Error("Timed out waiting for validation");
}

$("uploadButton").addEventListener("click", async () => {
  const file = $("fileInput").files[0];
  if (!file) {
    $("message").textContent = "Choose a CSV file first.";
    return;
  }

  $("uploadButton").disabled = true;
  $("metrics").classList.add("hidden");
  $("reportCard").classList.add("hidden");
  $("systemStatus").textContent = "WORKING";
  $("systemStatus").className = "pill processing";

  try {
    $("message").textContent = "Creating job…";
    const created = await createJob(file);

    $("jobCard").classList.remove("hidden");
    $("jobId").textContent = created.job_id;
    updateStatus(created.status);

    $("message").textContent = "Uploading directly to Amazon S3…";
    await putFile(created.upload_url, file);

    $("message").textContent = "Upload complete. Waiting for asynchronous validation…";
    await poll(created.job_id);
  } catch (error) {
    console.error(error);
    $("message").textContent = `Error: ${error.message}`;
    $("systemStatus").textContent = "ERROR";
    $("systemStatus").className = "pill failed";
  } finally {
    $("uploadButton").disabled = false;
  }
});

async function loadHistory() {
  try {
    const response = await fetch(`${API_URL}/jobs`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const jobs = await response.json();
    $("historyBody").innerHTML = jobs.map(job => `
      <tr>
        <td>${job.file_name || "—"}</td>
        <td>${job.status || "—"}</td>
        <td>${job.quality_score !== undefined ? `${job.quality_score}%` : "—"}</td>
        <td>${job.created_at ? new Date(job.created_at).toLocaleString() : "—"}</td>
      </tr>`).join("") || '<tr><td colspan="4">No jobs found.</td></tr>';
  } catch (error) {
    $("historyBody").innerHTML = `<tr><td colspan="4">Could not load history: ${error.message}</td></tr>`;
  }
}

$("refreshButton").addEventListener("click", loadHistory);

$("downloadButton").addEventListener("click", () => {
  if (!latestReport) return;
  const blob = new Blob([JSON.stringify(latestReport, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `data-quality-report-${latestReport.job_id}.json`;
  link.click();
  URL.revokeObjectURL(url);
});

fetch(`${API_URL}/health`)
  .then(r => r.json())
  .then(() => {
    $("systemStatus").textContent = "ONLINE";
    $("systemStatus").className = "pill completed";
  })
  .catch(() => {
    $("systemStatus").textContent = "API ERROR";
    $("systemStatus").className = "pill failed";
  });

loadHistory();

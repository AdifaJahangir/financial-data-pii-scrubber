const fileInput = document.getElementById("files");
const processButton = document.getElementById("processButton");
const statusBox = document.getElementById("status");
const results = document.getElementById("results");

fileInput.addEventListener("change", () => {
  const files = Array.from(fileInput.files || []);
  document.getElementById("selection").textContent =
    files.length
      ? `${files.length} file(s) selected`
      : "No files selected.";
});

function showStatus(message, type = "") {
  statusBox.textContent = message;
  statusBox.className = type;
}

processButton.addEventListener("click", async () => {
  const files = Array.from(fileInput.files || []);

  if (!files.length) {
    showStatus("Please select at least one file.", "error");
    return;
  }

  const formData = new FormData();
  files.forEach(file => formData.append("files", file));

  processButton.disabled = true;
  results.classList.add("hidden");
  showStatus("Uploading and processing locally...");

  try {
    const response = await fetch("/api/v1/upload", {
      method: "POST",
      body: formData
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Upload failed.");
    }

    results.classList.remove("hidden");

    const summary = document.getElementById("summary");
    summary.replaceChildren();

    [
      `Status: ${data.status || "unknown"}`,
      `Safe to send: ${data.safe_to_send === true ? "Yes" : "No"}`,
      `Files processed: ${data.processed_count ?? 0}`,
      `Files failed: ${data.failed_count ?? 0}`,
      `Database job ID: ${data.job_id ?? "Not saved"}`,
      `Message: ${data.reason || "No additional information"}`
    ].forEach(line => {
      const p = document.createElement("p");
      p.textContent = line;
      summary.appendChild(p);
    });

    const fileResults = document.getElementById("fileResults");
    fileResults.replaceChildren();

    (data.processed_files || []).forEach(file => {
      const div = document.createElement("div");
      div.className = "file-row";
      div.textContent =
        `${file.file_name} — ${file.status} — Redactions: ${file.redacted_count}`;
      fileResults.appendChild(div);
    });

    (data.failed_files || []).forEach(file => {
      const div = document.createElement("div");
      div.className = "file-row error";
      div.textContent = `${file.file || "Unknown"} — ${file.reason || "Failed"}`;
      fileResults.appendChild(div);
    });

    document.getElementById("output").value =
      data.safe_to_send === true && typeof data.combined_output === "string"
        ? data.combined_output
        : "No output available: safety validation failed.";

    showStatus(
      data.safe_to_send === true
        ? "Processing completed. Safety validation passed."
        : "Safety validation failed. Do not send this batch externally.",
      data.safe_to_send === true ? "success" : "error"
    );
  } catch (error) {
    showStatus(error.message || "An unexpected error occurred.", "error");
  } finally {
    processButton.disabled = false;
  }
});

document.getElementById("copyButton").addEventListener("click", async () => {
  const output = document.getElementById("output");

  if (!output.value || output.value.startsWith("No output available")) {
    showStatus("There is no validated output to copy.", "error");
    return;
  }

  try {
    await navigator.clipboard.writeText(output.value);
    showStatus("Scrubbed output copied.", "success");
  } catch {
    showStatus("Clipboard failed. Select and copy the output manually.", "error");
  }
});

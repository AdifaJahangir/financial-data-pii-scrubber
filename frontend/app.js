
const fileInput = document.getElementById("files");
const processButton = document.getElementById("processButton");
const statusBox = document.getElementById("status");
const results = document.getElementById("results");

const analysisSection = document.getElementById("analysisSection");
const analyzeButton = document.getElementById("analyzeButton");
const analysisStatus = document.getElementById("analysisStatus");
const analysisResult = document.getElementById("analysisResult");
const analysisContent = document.getElementById("analysisContent");
const analysisModel = document.getElementById("analysisModel");

const chatSection = document.getElementById("chatSection");
const chatButton = document.getElementById("chatButton");
const chatQuestion = document.getElementById("chatQuestion");
const chatStatus = document.getElementById("chatStatus");
const chatResult = document.getElementById("chatResult");
const chatAnswer = document.getElementById("chatAnswer");
const chatModel = document.getElementById("chatModel");

let currentJobId = null;

// Create the budget results section without requiring an HTML change.
const budgetSection = document.createElement("section");
budgetSection.id = "budgetSection";
budgetSection.className = "result-card hidden";
budgetSection.innerHTML = `
  <h2>Financial Summary</h2>
  <p id="budgetStatus"></p>
  <div id="budgetContent"></div>
`;
analysisSection.parentNode.insertBefore(budgetSection, analysisSection);

const budgetStatus = document.getElementById("budgetStatus");
const budgetContent = document.getElementById("budgetContent");

function showStatus(element, message, type = "") {
  element.textContent = message;
  element.className = type;
}

function displayText(element, content) {
  // Display AI responses as plain text to prevent HTML injection.
  element.textContent = content || "";
  element.style.whiteSpace = "pre-wrap";
}

function addBudgetText(parent, label, value) {
  const p = document.createElement("p");
  const strong = document.createElement("strong");
  strong.textContent = `${label}: `;
  p.append(strong, document.createTextNode(String(value)));
  parent.appendChild(p);
}

function renderBudgetAnalysis(budget) {
  budgetContent.replaceChildren();
  budgetSection.classList.remove("hidden");

  if (!budget || typeof budget !== "object") {
    showStatus(
      budgetStatus,
      "Budget calculations were not included in the API response.",
      "error"
    );
    return;
  }

  if (budget.status !== "success") {
    showStatus(
      budgetStatus,
      budget.message || "There is not enough transaction data for a budget summary.",
      "error"
    );

    addBudgetText(
      budgetContent,
      "Identified transactions",
      budget.transaction_count ?? 0
    );

    renderLimitations(budgetContent, budget.limitations);
    return;
  }

  showStatus(
    budgetStatus,
    "Financial totals calculated locally from identified transactions.",
    "success"
  );

  addBudgetText(
    budgetContent,
    "Identified transactions",
    budget.transaction_count ?? 0
  );

  const currencies = budget.currencies || {};
  const currencyEntries = Object.entries(currencies);

  if (!currencyEntries.length) {
    addBudgetText(
      budgetContent,
      "Currency summary",
      "No currency totals available."
    );
  }

  currencyEntries.forEach(([currency, summary]) => {
    const card = document.createElement("div");
    card.className = "file-row";

    const heading = document.createElement("h3");
    heading.textContent = currency;
    card.appendChild(heading);

    addBudgetText(card, "Income", summary.income ?? "0");
    addBudgetText(card, "Expenses", summary.expenses ?? "0");
    addBudgetText(card, "Net amount", summary.net ?? "0");
    addBudgetText(
      card,
      "Unclassified amount",
      summary.unknown_amount ?? "0"
    );
    addBudgetText(
      card,
      "Transactions",
      summary.transaction_count ?? 0
    );

    budgetContent.appendChild(card);
  });

  renderLimitations(budgetContent, budget.limitations);
}

function renderLimitations(parent, limitations) {
  if (!Array.isArray(limitations) || limitations.length === 0) {
    return;
  }

  const heading = document.createElement("h3");
  heading.textContent = "Important limitations";
  parent.appendChild(heading);

  const list = document.createElement("ul");

  limitations.forEach(item => {
    const li = document.createElement("li");
    li.textContent = String(item);
    list.appendChild(li);
  });

  parent.appendChild(list);
}

fileInput.addEventListener("change", () => {
  const files = Array.from(fileInput.files || []);

  document.getElementById("selection").textContent =
    files.length
      ? `${files.length} file(s) selected`
      : "No files selected.";
});

processButton.addEventListener("click", async () => {
  const files = Array.from(fileInput.files || []);

  if (!files.length) {
    showStatus(statusBox, "Please select at least one file.", "error");
    return;
  }

  const formData = new FormData();
  files.forEach(file => formData.append("files", file));

  processButton.disabled = true;
  results.classList.add("hidden");
  analysisSection.classList.add("hidden");
  chatSection.classList.add("hidden");
  budgetSection.classList.add("hidden");

  currentJobId = null;

  analysisResult.classList.add("hidden");
  chatResult.classList.add("hidden");

  showStatus(statusBox, "Uploading and processing locally...");

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
      div.textContent =
        `${file.file || "Unknown"} — ${file.reason || "Failed"}`;
      fileResults.appendChild(div);
    });

    document.getElementById("output").value =
      data.safe_to_send === true &&
      typeof data.combined_output === "string"
        ? data.combined_output
        : "No output available: safety validation failed.";

    const safeJob =
      data.safe_to_send === true &&
      data.status === "success" &&
      Number.isInteger(data.job_id) &&
      data.processed_count > 0 &&
      data.failed_count === 0;

    if (safeJob) {
      currentJobId = data.job_id;

      analysisSection.classList.remove("hidden");
      chatSection.classList.remove("hidden");

      showStatus(
        statusBox,
        "Processing completed. Safety validation passed.",
        "success"
      );
    } else {
      showStatus(
        statusBox,
        "Processing completed, but safety checks did not pass. AI features are disabled.",
        "error"
      );
    }

  } catch (error) {
    showStatus(
      statusBox,
      error.message || "An unexpected error occurred.",
      "error"
    );
  } finally {
    processButton.disabled = false;
  }
});


// Financial analysis: deterministic budget summary + Groq report
analyzeButton.addEventListener("click", async () => {
  if (!currentJobId) {
    showStatus(
      analysisStatus,
      "No validated processing job is available.",
      "error"
    );
    return;
  }

  analyzeButton.disabled = true;
  analysisResult.classList.add("hidden");
  budgetSection.classList.add("hidden");

  showStatus(
    analysisStatus,
    "Calculating financial totals and requesting Groq analysis..."
  );

  try {
    const response = await fetch(
      `/api/v1/jobs/${currentJobId}/analysis`,
      {
        method: "POST",
        headers: {
          "Accept": "application/json"
        }
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Financial analysis failed.");
    }

    // Display locally calculated financial totals.
    renderBudgetAnalysis(data.budget_analysis);

    // Display the separate AI-generated explanation.
    displayText(analysisContent, data.analysis);
    analysisModel.textContent = `AI model: ${data.model}`;

    analysisResult.classList.remove("hidden");

    showStatus(
      analysisStatus,
      "Financial analysis completed successfully.",
      "success"
    );

  } catch (error) {
    showStatus(
      analysisStatus,
      error.message || "Unable to complete financial analysis.",
      "error"
    );
  } finally {
    analyzeButton.disabled = false;
  }
});


// Groq financial chat
chatButton.addEventListener("click", async () => {
  if (!currentJobId) {
    showStatus(
      chatStatus,
      "No validated processing job is available.",
      "error"
    );
    return;
  }

  const question = chatQuestion.value.trim();

  if (!question) {
    showStatus(chatStatus, "Please enter a question.", "error");
    return;
  }

  if (question.length > 1000) {
    showStatus(
      chatStatus,
      "Your question must not exceed 1000 characters.",
      "error"
    );
    return;
  }

  chatButton.disabled = true;
  chatResult.classList.add("hidden");

  showStatus(chatStatus, "Getting an answer from Groq...");

  try {
    const response = await fetch(
      `/api/v1/jobs/${currentJobId}/chat`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify({ question })
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Chat request failed.");
    }

    displayText(chatAnswer, data.answer);
    chatModel.textContent = `AI model: ${data.model}`;

    chatResult.classList.remove("hidden");

    showStatus(
      chatStatus,
      "Answer received successfully.",
      "success"
    );

  } catch (error) {
    showStatus(
      chatStatus,
      error.message || "Unable to get an answer.",
      "error"
    );
  } finally {
    chatButton.disabled = false;
  }
});


// Copy validated scrubbed output
document.getElementById("copyButton").addEventListener(
  "click",
  async () => {
    const output = document.getElementById("output");

    if (
      !output.value ||
      output.value.startsWith("No output available")
    ) {
      showStatus(statusBox, "There is no validated output to copy.", "error");
      return;
    }

    try {
      await navigator.clipboard.writeText(output.value);

      showStatus(
        statusBox,
        "Scrubbed output copied.",
        "success"
      );
    } catch {
      showStatus(
        statusBox,
        "Clipboard failed. Select and copy the output manually.",
        "error"
      );
    }
  }
);

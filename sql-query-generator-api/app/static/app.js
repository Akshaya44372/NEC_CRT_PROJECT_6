const queryInput = document.getElementById("query-input");
const executeBtn = document.getElementById("execute-btn");
const sqlOutput = document.getElementById("sql-output");
const errorMsg = document.getElementById("error-msg");

async function executeQuery() {
  const query = queryInput.value.trim();
  errorMsg.hidden = true;
  errorMsg.textContent = "";

  if (!query) {
    errorMsg.textContent = "Please enter a question.";
    errorMsg.hidden = false;
    return;
  }

  executeBtn.disabled = true;
  sqlOutput.textContent = "Generating…";

  try {
    const response = await fetch("/generate/sql", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/plain" },
      body: JSON.stringify({ query }),
    });

    const text = await response.text();

    if (!response.ok) {
      let message = text;
      try {
        const json = JSON.parse(text);
        message = json.detail || message;
      } catch {
        /* plain text error */
      }
      throw new Error(message);
    }

    sqlOutput.textContent = text.trim();
  } catch (err) {
    sqlOutput.textContent = "";
    errorMsg.textContent = err.message || "Failed to generate SQL.";
    errorMsg.hidden = false;
  } finally {
    executeBtn.disabled = false;
  }
}

executeBtn.addEventListener("click", executeQuery);

queryInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    executeQuery();
  }
});

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    queryInput.value = chip.dataset.query || "";
    executeQuery();
  });
});

queryInput.focus();

# Financial Data PII Scrubber

A privacy-focused financial document processing application that extracts financial data locally, detects and redacts personally identifiable information (PII), validates sanitized output, and stores processing results in PostgreSQL.

The application also provides deterministic financial summaries and optional Groq-powered financial analysis and follow-up chat using validated, scrubbed document content.

## 1. Features

- **Local document processing:** Extracts text from PDF, DOCX, CSV, and TXT files.
- **PII detection and redaction:** Detects and redacts supported sensitive information, including account identifiers, email addresses, phone numbers, and other configured PII patterns.
- **Independent safety validation:** Checks scrubbed output for detectable residual PII before external AI processing.
- **PostgreSQL persistence:** Stores processing jobs, document metadata, redaction information, and scrubbed output.
- **Deterministic financial analysis:** Identifies transactions and calculates income, expenses, net amounts, and unclassified amounts separately by currency.
- **Groq AI analysis:** Generates explanations using validated, scrubbed financial documents.
- **Financial chat:** Supports follow-up questions about the available scrubbed data.
- **Web interface:** Upload documents, review results, view financial summaries, and interact with the AI.
- **REST API:** FastAPI endpoints for health checks, document uploads, financial analysis, and chat.
- **Automated tests:** Unit and API tests for core functionality.

## 2. Technology Stack

- Python 3.11
- FastAPI
- PostgreSQL
- SQLAlchemy
- Groq API
- HTML, CSS, and JavaScript
- Pytest
- Document-processing and data-analysis libraries

## 3. Requirements

Before installation, make sure you have:

- Windows 10 or later
- Python 3.11
- PostgreSQL
- Git
- Internet access for installing dependencies and using Groq
- A Groq API key (required only for AI analysis and chat)

You can download Python from https://www.python.org/downloads/ and PostgreSQL from https://www.postgresql.org/download/.

## 4. Installation and Setup (Windows)

### Step 1: Clone the repository

Open PowerShell and run:

```powershell
git clone https://github.com/AdifaJahangir/financial-data-pii-scrubber.git
cd financial-data-pii-scrubber
```

Alternatively, download the repository as a ZIP file and extract it.

### Step 2: Create a virtual environment

```powershell
py -3.11 -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run this command in the current terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then activate the environment again:

```powershell
.\.venv\Scripts\Activate.ps1
```

Upgrade pip and install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Create the PostgreSQL database

Start the PostgreSQL service and open the PostgreSQL command-line tool (`psql`) or pgAdmin.

Create the database:

```sql
CREATE DATABASE financial_pii_scrubber;
```

Keep your PostgreSQL username and password available for the connection configuration.

### Step 4: Configure environment variables

Create your local `.env` file from the example:

```powershell
Copy-Item .env.example .env
```

Open `.env` in VS Code and configure the values using the variable names provided in `.env.example`.

The main settings include:

- `DATABASE_URL` — PostgreSQL connection string.
- `GROQ_API_KEY` — Your Groq API key.
- `GROQ_MODEL` — AI model name. The tested configuration uses `openai/gpt-oss-20b`.

An example SQLAlchemy PostgreSQL connection string is:

```text
postgresql+psycopg://username:password@localhost:5432/financial_pii_scrubber
```

Replace `username` and `password` with your own PostgreSQL credentials. Use the connection-string format expected by your application configuration.

Obtain a Groq API key from https://console.groq.com/ and place it in your local `.env` file.

**Security:** Never share or commit your `.env` file, API key, database password, or original financial documents. Keep `.env.example` free of real credentials.

### Step 5: Start the application

Make sure PostgreSQL is running and your virtual environment is activated.

From the project root, run:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

When the server starts successfully, open these addresses:

| Purpose | URL |
|---|---|
| Web application | http://127.0.0.1:8000/ |
| Interactive API documentation | http://127.0.0.1:8000/docs |
| Health check | http://127.0.0.1:8000/api/v1/health |

Keep the terminal running while using the application. To stop the server, press `Ctrl + C`.

## 5. How to Use the Application

### Step 1: Open the frontend

Visit:

http://127.0.0.1:8000/

### Step 2: Select financial documents

Choose one or more supported documents:

- PDF
- DOCX
- CSV
- TXT

### Step 3: Upload and process

Upload the selected documents through the web interface.

The application extracts document text locally, detects supported PII patterns, redacts sensitive information, and performs independent safety validation.

### Step 4: Review processing results

Review:

- Processing status
- Number of processed and failed documents
- Redaction counts
- Scrubbed document output
- Safety validation status

Only continue to external AI analysis when the application reports that the processing job is safe to send.

### Step 5: Review financial analysis

The application calculates financial summaries locally using its transaction parser and budget analyzer.

Review the identified transactions, income, expenses, net amounts, and unclassified amounts.

### Step 6: Request AI analysis

Select **Analyze Financial Data** to request a Groq-generated explanation based on eligible scrubbed documents.

### Step 7: Ask follow-up questions

Enter a question in the financial chat interface to ask about the available scrubbed financial information.

AI responses are generated from the supplied context and should be checked against the document output.

## 6. Upload Limits

The upload API enforces the following limits:

- Maximum 20 files per request.
- Maximum 10 MB per file.
- Maximum 50 MB total per request.

Supported extensions are PDF, DOCX, CSV, and TXT.

## 7. Financial Analysis Approach

Financial calculations are performed locally using the transaction parser and budget analyzer.

The application attempts to:

- Identify recognizable transaction entries.
- Extract transaction dates, descriptions, amounts, and currencies.
- Classify recognizable income and expenses.
- Report unclassified amounts separately.
- Calculate net amounts separately for each currency.
- Exclude balance-only entries from transaction totals.

Different currencies are never combined. Calculations cover only transactions successfully identified by the parser. Results should not be treated as complete account reconciliation or professional financial advice.

Groq analysis and chat are separate from deterministic calculations. Only eligible validated, scrubbed document content is sent to Groq, not original statement files.

## 8. API Endpoints

The main API routes include:

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Check application health |
| POST | `/api/v1/upload` | Upload and process documents |
| POST | `/api/v1/jobs/{job_id}/analysis` | Generate financial and AI analysis |
| POST | `/api/v1/jobs/{job_id}/chat` | Ask a follow-up question |

For request and response details, open:

http://127.0.0.1:8000/docs

## 9. Database Design

The application uses PostgreSQL to persist processing results.

- `processing_jobs`: Stores batch-level processing status, safety results, counts, combined scrubbed output, and timestamps.
- `scrubbed_documents`: Stores individual document filenames, processing status, redaction counts, warnings, and scrubbed output.

Raw extracted statement text is not intentionally stored as a database document field. Scrubbed financial data is still sensitive and should be protected with appropriate database access controls.

## 10. Privacy and Security

- Original financial documents are processed locally.
- Original statement contents are not intentionally transmitted to Groq.
- Only validated, scrubbed document content is eligible for external AI analysis.
- Failed safety validation prevents external AI processing.
- Raw extracted statement text is not intentionally stored as a database document field.
- AI prompts instruct the model to treat document content as untrusted data and avoid inventing or reconstructing redacted information.
- Never commit `.env`, real API keys, database credentials, or private financial documents.

PII detection is rule-based and cannot guarantee detection of every possible sensitive identifier. Always review scrubbed output before sharing it externally.

## 11. Running the Tests

Activate the virtual environment and run:

```powershell
pytest -q
```

The latest verified test run completed with:

```text
138 passed, 0 failed
```

The test suite includes checks for PII detection, document extraction, validation, API processing, database persistence, financial parsing, and Groq integration.

## 12. Troubleshooting

**Problem: PowerShell blocks virtual-environment activation**

Run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then activate `.venv` again.

**Problem: Database connection fails**

- Confirm PostgreSQL is installed and running.
- Confirm the database `financial_pii_scrubber` exists.
- Check the username, password, host, port, and `DATABASE_URL` in `.env`.

**Problem: Groq analysis or chat fails**

- Confirm `GROQ_API_KEY` is configured correctly.
- Confirm the API key is valid.
- Confirm `GROQ_MODEL` is set to a model available to your Groq account.
- Check your internet connection and Groq API availability.

**Problem: Application does not start**

- Confirm the virtual environment is activated.
- Confirm dependencies were installed using `pip install -r requirements.txt`.
- Run the command from the project root.
- Review the error displayed in the PowerShell terminal.

## 13. Project Structure

```text
app/
    api/
        routes/
    core/
    db/
        repositories/
    domain/
        analytics/
        chat/
        extraction/
        finance/
        llm/
        pii/
    services/
    utils/
frontend/
    index.html
    styles.css
    app.js
tests/
    fixtures/
    integration/
    unit/
.env.example
.gitignore
requirements.txt
README.md
NOTES.md
```

## 14. Limitations and Future Improvements

- PII detection may miss unusual or previously unseen identifier formats.
- Transaction parsing depends on recognizable document layouts and descriptions.
- Financial summaries may be incomplete if transactions cannot be reliably identified.
- Income and expense classification is rule-based and may need additional transaction-specific rules.
- AI-generated explanations may contain errors and should be checked against scrubbed source data.
- Additional testing with diverse synthetic document formats, stronger validation rules, improved categorization, and database access controls would improve reliability.

## 15. Research and Design Documentation

See [NOTES.md](NOTES.md) for research decisions, architecture, database design, guardrails, AI integration, testing, and future improvements.

## 16. GitHub Repository

https://github.com/AdifaJahangir/financial-data-pii-scrubber
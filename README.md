# Financial Data PII Scrubber

A privacy-focused Python application that processes local financial documents, detects and redacts personally identifiable information (PII), validates sanitized output, and stores processing metadata in PostgreSQL.

## Features

- **Local document processing:** Discover and extract text from PDF, DOCX, CSV, and TXT files.
- **PII redaction:** Detect and redact sensitive information such as names, email addresses, and account numbers.
- **Output validation:** Validate sanitized output before it can be sent to an external AI service.
- **PostgreSQL persistence:** Store processing jobs, status information, and sanitized document output.
- **REST API:** FastAPI endpoints for health checks and local document processing.
- **Automated tests:** Unit and API tests for key components.

Budgeting analysis and follow-up chat using an external language model are planned features unless otherwise implemented and tested.

## Technology Stack

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- HTML, CSS, and JavaScript
- Pytest

## Windows 10 Setup

### Prerequisites

- Python 3.12 or a compatible version supported by the dependencies
- PostgreSQL
- Git

### 1. Clone the repository

```powershell
git clone https://github.com/AdifaJahangir/financial-data-pii-scrubber.git
cd financial-data-pii-scrubber
```

### 2. Create and activate a virtual environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure environment variables

Create your local environment file:

```powershell
Copy-Item .env.example .env
```

Edit `.env` with your local database connection details and other required settings. Never commit `.env` or publish API keys, passwords, or private financial documents.

### 4. Configure PostgreSQL

Create a local database named `financial_pii_scrubber` and set the appropriate `DATABASE_URL` in `.env`.

### 5. Start the API

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open the interactive API documentation:

http://127.0.0.1:8000/docs

Check the health endpoint:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/health
```

### 6. Run the tests

```powershell
pytest tests -v
```

## Frontend

The frontend files are located in `frontend/`:

- `index.html`
- `styles.css`
- `app.js`

Open `frontend/index.html` in a browser for a static preview. API-connected features may require the FastAPI server to be running and the frontend API configuration to be correct.

## Security Considerations

- Process financial documents locally within the configured directory.
- Do not store raw statement text or original documents in the database.
- Send content to an external AI provider only after successful redaction and validation.
- Fail closed when extraction, redaction, or validation is unsuccessful.
- Never commit `.env`, real API keys, database credentials, or private financial documents.
- Use synthetic data when testing and demonstrating the application.

## Project Structure

```text
app/          FastAPI application and processing logic
frontend/     HTML, CSS, and JavaScript
tests/        Automated tests
.env.example  Example configuration
requirements.txt
README.md
```

## Current Status

The project includes document extraction, PII redaction, output validation, database persistence, API endpoints, and automated tests. Features should be considered complete only when their implementation and tests have been verified.

## Future Improvements

- Budgeting analysis and follow-up chat using a language model
- More comprehensive PII detection and validation
- Improved frontend integration and user experience
- Additional security and integration tests

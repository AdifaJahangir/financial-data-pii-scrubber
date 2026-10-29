# Financial Data PII Scrubber

## Overview
This project is a privacy-first Python service for processing local financial documents, scrubbing PII, storing only sanitized metadata in PostgreSQL, and providing budgeting analysis and follow-up chat grounded in scrubbed data.

## Windows 10 setup
1. Install Python 3.12 or newer.
2. Install PostgreSQL 16 and create a local database.
3. Clone the repository.
4. Open PowerShell in the project root and create a virtual environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

5. Copy `.env.example` to `.env` and update values:

```powershell
Copy-Item .env.example .env
```

6. Configure PostgreSQL by creating a database named `financial_pii_scrubber` and updating `DATABASE_URL` in `.env`.
7. Start the API:

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

8. Verify the health endpoint:

```powershell
Invoke-WebRequest http://localhost:8000/api/health
```

## Security notes
- Do not store raw uploaded documents or raw statement text in the database.
- Only scrubbed content may be sent to Groq.
- The system must fail closed when extraction or scrubbing confidence is low.
- The configured data directory must be the only filesystem location allowed for local scanning.

## Planned structure
- app/
- frontend/
- tests/
- data/

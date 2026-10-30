# Research and Design Notes - Financial Data PII Scrubber

## 1. Problem and Research
The goal is to protect sensitive financial information while preserving useful transaction details. Original documents are processed locally. External document-processing services are avoided to protect privacy.

## 2. Alternatives and Technology Choices
Rule-based PII detection was selected because it is transparent, testable, and does not require sending original statements to an external AI service. Its limitation is that unusual or unlabelled identifiers may be missed. FastAPI provides the backend API, PostgreSQL stores processing results, and plain HTML, CSS, and JavaScript provide the frontend.

## 3. Final Architecture
The workflow is: file upload -> local text extraction -> PII detection -> redaction -> independent output validation -> PostgreSQL persistence. Supported formats are PDF, DOCX, CSV, and TXT. Multiple files can be processed and combined with clear file headers.

## 4. Database Design
The `processing_jobs` table stores batch-level status, safety results, counts, and combined scrubbed output. The `scrubbed_documents` table stores individual filenames, statuses, redaction counts, warnings, and scrubbed output. Raw extracted statement text is not intentionally stored. Scrubbed financial data remains sensitive and requires access controls.

## 5. Guardrails and Accuracy
The detector uses configured patterns for names, account identifiers, email addresses, phone numbers, and other supported personal and financial identifiers. Dates, amounts, balances, and merchant descriptions are intended to remain readable. Independent validation checks for detectable residual PII. Failed validation prevents external use. Detection is not guaranteed to catch every possible identifier.


## 6. AI Integration
Groq-based budgeting analysis and grounded chat are not implemented in the current version. Therefore, no Groq model or system prompt is claimed as selected or tested. Any future integration must send only independently validated scrubbed data, ground answers in available records, validate responses, and prevent unsupported financial claims.

## 7. Testing
The automated test suite completed with 119 passed tests. A synthetic upload test verified one file, four redactions, output validation, and PostgreSQL persistence (job ID 9). No original financial statements were used in this test. These results do not establish perfect detection or production readiness.

## 8. Future Improvements
Implement and test Groq integration, budgeting analysis, and grounded chat; improve detection of unusual identifiers; add aggregate upload-limit and security tests; strengthen database access controls; and expand integration testing.

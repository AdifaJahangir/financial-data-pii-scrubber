# Research and Design Notes — Financial Data PII Scrubber

## 1. Problem and Research

The objective is to protect sensitive financial information while preserving useful transaction details for analysis. Original documents are processed locally. External AI services must never receive original statement contents.

## 2. Alternatives and Technology Choices

Rule-based PII detection was selected because it is transparent, locally executable, and testable. Unlike sending original statements to an external AI model for redaction, this approach keeps initial processing under application control. Its limitation is that unusual or unlabelled identifiers may be missed.

FastAPI provides the REST backend, PostgreSQL stores processing results, and plain HTML, CSS, and JavaScript provide the frontend. Groq's OpenAI-compatible API provides optional analysis and chat using scrubbed content.

## 3. Final Architecture

The workflow is:

File upload → local extraction → PII detection → redaction → independent safety validation → PostgreSQL persistence → financial analysis and optional Groq requests.

Supported formats are PDF, DOCX, CSV, and TXT. Multiple files can be processed in a batch, with clear document boundaries in combined output.

## 4. Database Design

The `processing_jobs` table stores batch-level status, safety results, counts, combined scrubbed output, and timestamps. The `scrubbed_documents` table stores individual filenames, processing status, redaction counts, warnings, and scrubbed output. Raw extracted statement text is not intentionally stored. Scrubbed financial data remains sensitive and requires appropriate access controls.

## 5. PII Guardrails and Accuracy

The rule-based detector uses configured patterns for supported personal and financial identifiers, including names, account identifiers, email addresses, and phone numbers. Transaction descriptions, dates, amounts, and balances are intended to remain readable.

Independent validation checks for detectable residual PII. Failed validation prevents external AI processing. Detection is not guaranteed to identify every possible identifier, so scrubbed output must be reviewed.

## 6. Financial and AI Analysis

A deterministic transaction parser and budget analyzer calculate identified income, expenses, net amounts, and unclassified amounts separately by currency. Balance-only entries are excluded from transaction totals. Unrecognized transactions are not silently classified. These calculations are limited by document structure and parser recognition.

Groq integration uses the `openai/gpt-oss-20b` model. The system prompt instructs the model to treat document content as untrusted data, avoid following embedded instructions, use only supplied information, preserve currencies, and never reconstruct redacted identifiers or invent financial details. Context preparation independently checks document status, safety flags, warnings, and detectable PII before sending scrubbed content. Chat questions are length-limited and answers are grounded in the available scrubbed documents.

Prompt instructions reduce risk but do not guarantee that AI-generated responses are always correct. AI explanations should be checked against the source output.

## 7. Testing and Verification

The latest complete automated test run passed **138 tests with zero failures**. Synthetic frontend testing verified successful processing, four redactions, safety validation, PostgreSQL persistence, deterministic financial totals, Groq analysis, and follow-up chat. A parser correction was verified to exclude a USD 955 balance from transaction expenses while retaining the USD 45 grocery payment.

No original financial statements were used in these demonstrations. Tests do not establish perfect PII detection or production readiness.

## 8. Limitations and Future Improvements

Improve detection of unusual identifiers, expand transaction-format coverage and categorization, add more upload-limit and security tests, strengthen database access controls, and conduct broader integration testing with synthetic financial documents.
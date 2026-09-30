# Security & Data Governance Specification
## Smart India Hackathon 2026 — Problem Statement SIH26081

---

## 1. Security Principles

1. **Zero Secret Exposure:**
   - No API keys or credentials exist in frontend HTML or JavaScript.
   - All third-party communication occurs server-side in Python.
   - `.env` is strictly ignored by `.gitignore`.

2. **Rate Limiting:**
   - Implemented via `slowapi` with remote IP tracking to prevent denial-of-service spikes.

3. **Input Sanitization:**
   - Strict Pydantic v2 data validation on all query parameters and JSON payloads.
   - Coordinates clamped to valid ranges ($[-90, +90]$, $[-180, +180]$).
   - String inputs length-bounded.

4. **Error Masking:**
   - Raw stack traces are never returned to clients; generic HTTP status codes (404, 422, 502, 503) are emitted.

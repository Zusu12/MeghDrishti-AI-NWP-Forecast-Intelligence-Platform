# Deployment Specification
## Smart India Hackathon 2026 — Problem Statement SIH26081

---

## 1. Local Development

```powershell
# 1. Activate virtual environment
.\venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy environment configuration
copy .env.example .env

# 4. Run tests
pytest

# 5. Start FastAPI application
python main.py
```
App runs at `http://localhost:8000`.

---

## 2. Docker Deployment

```bash
# Build image
docker build -t sih-nwp-blending .

# Run container
docker run -p 8000:8000 --env-file .env sih-nwp-blending
```

---

## 3. Cloud Deployment (Railway / PaaS)

- Platform detects `Dockerfile` and `railway.json`.
- Dynamic port assignment via `$PORT`.
- Host binds to `0.0.0.0`.

---

## 4. Vercel Serverless Deployment

MeghDrishti is pre-configured for zero-friction Vercel deployment:

1. **Architecture:**
   - **Static Assets:** Hosted on Vercel Edge CDN (`public/` and `static/`) for sub-50ms TTFB.
   - **API & NWP Engine:** Powered by Vercel Serverless Functions via `api/index.py` and `vercel.json`.
   - **Runtime:** Python 3.11 specified in `runtime.txt`.
   - **Database:** Serverless-resilient fallback automatically switches SQLite storage to `/tmp/meghdrishti.db` or memory.

2. **Deploy Steps:**
   - Import repository `Zusu12/MeghDrishti-AI-NWP-Forecast-Intelligence-Platform` in Vercel.
   - Framework Preset: `Other`.
   - Click **Deploy**.
   - Optional environment variables: `OPENWEATHERMAP_API_KEY`, `GEMINI_API_KEY`, `ELEVENLABS_API_KEY`.


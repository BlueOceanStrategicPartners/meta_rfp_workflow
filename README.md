# Hospitality RFP Engine

Autonomous multimodal multi-agent RFP and dynamic pricing platform (Django + React).

## Voice assistant stack (required)

| Layer | Technology |
|-------|------------|
| Speech-to-text | **Default:** local **Meta `omniASR_CTC_300M_v2`** on GPU (`ASR_BACKEND=omniasr`, `pip install -r requirements-asr.txt`). **Optional:** Muse cloud realtime (`ASR_BACKEND=muse`, `META_MODEL_API_KEY`) via `ws://<host>/ws/asr/` |
| Agent reasoning | **Muse Wonder** (initial PDF extract, Designer layout validation) + **Muse Spark 1.3** (critic, re-extract, design chat, negotiation) |
| **Text-to-speech (compulsory)** | **[SeamlessM4T v2](https://ai.meta.com/research/seamless/)** via `POST /api/voice/seamless-m4t-v2/synthesize/` |

Production TTS: `pip install -r requirements-voice.txt` and set `USE_SEAMLESS_FIXTURE=0`. Local dev defaults to fixture WAV unless the full model is loaded.

## Quick start (local SQLite)

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install -r requirements-asr.txt
set DJANGO_SETTINGS_MODULE=config.settings.local_sqlite
set USE_FIXTURE_DEBATE=1
set CELERY_TASK_ALWAYS_EAGER=1
python manage.py migrate
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8000
```

Use `scripts/dev-backend.ps1` from the repo root on Windows (loads `.env`, autoreload on). **Do not** use `runserver --noreload` or standalone `daphne` for everyday coding.

```bash
cd frontend
npm install
npm run dev
```

## Environment

| Variable | Purpose |
|----------|---------|
| `DB_ENGINE_MODE` | `sqlite` (default) or `azuresql` |
| `META_MODEL_API_KEY` | Meta Model API key (`https://api.meta.ai/v1`; local fixtures if empty or `USE_FIXTURE_DEBATE=1`) |
| `META_MODEL_SPARK` | Default `muse-spark-1.3` |
| `META_MODEL_WONDER` | Default `muse-wonder` (Designer validation, initial extraction) |
| `USE_FIXTURE_DEBATE` | Deterministic 3-agent debate for demos/tests |
| `USE_SEAMLESS_FIXTURE` | `1` = WAV stub; `0` = load **SeamlessM4T v2** (needs `requirements-voice.txt`) |
| `SEAMLESS_M4T_V2_MODEL` | Default `facebook/seamless-m4t-v2-large` |
| `SEAMLESS_M4T_DEVICE` | `cpu` or `cuda` |
| `ASR_BACKEND` | `omniasr` (local GPU CTC) or `muse` (Meta cloud ASR) |
| `OMNIASR_MODEL_HF` | Default `aadel4/omniASR-CTC-300M-v2` (Meta v2 weights on Hugging Face) |
| `OMNIASR_RUNTIME` | `onnx` (fast-omniasr, no PyTorch — pairs better with **llama.cpp** on GPU) or `torch` |
| `OMNIASR_ONNX_MODEL` | Default `EmreAkgul/omniASR-CTC-300M-v2-ONNX` (~1.4 GiB VRAM FP16) |
| `MUSE_ASR_MODE` | When `ASR_BACKEND=muse`: `ENDPOINTING` or `PUSH_TO_TALK` |
| `REDIS_URL` | Channels/Celery broker |
| `AZURE_SQL_*` | Production Azure SQL (see `config/settings/prod_azuresql.py`) |

## Azure SQL production

Set `DJANGO_SETTINGS_MODULE=config.settings.prod_azuresql` and `DB_ENGINE_MODE=azuresql` with ODBC Driver 18 installed.

## Tests

```bash
cd backend
pytest
cd ../frontend
npm test
npm run test:e2e
```

# file_validator_prototype

## AI verification (Groq)

Set these environment variables for the backend:

- `GROQ_API_KEY` (required)
- `GROQ_MODEL` (default: `llama-3.1-70b-versatile`)
- `GROQ_TIMEOUT_SECONDS` (default: `20`)
- `AI_MAX_CHARS` (default: `4000`)
- `AI_MAX_PAGES` (default: `3`)
- `AI_OCR_LANG` (default: `eng`)
- `AI_OCR_MIN_TEXT_CHARS` (default: `200`)

After updating requirements, run migrations:

```bash
cd backend
python manage.py migrate
```

## OCR dependencies

OCR uses Tesseract. Install it locally, for example on macOS:

```bash
brew install tesseract
```

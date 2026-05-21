# QR Code Generator Prototype

A dynamic QR code generator that creates short URL tokens, supports 302 redirects with scan tracking, and allows URL modification after QR code creation.

## Key Design Decisions

1. **Dynamic QR Codes** — QR codes encode a short URL that redirects via server, enabling URL modification and scan analytics
2. **SHA-256 + Nonce + Base62** — Token generation with collision retry (7-char tokens, ~3.52 trillion possible values)
3. **302 Found** — Temporary redirects ensure every scan hits the server for tracking and real-time URL changes

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/qr/create` | Create a short URL + QR code |
| GET | `/r/{token}` | Redirect to original URL (302) |
| GET | `/api/qr/{token}` | Get QR code metadata |
| PATCH | `/api/qr/{token}` | Update target URL or expiration |
| DELETE | `/api/qr/{token}` | Soft delete (returns 410 on redirect) |
| GET | `/api/qr/{token}/image` | Get QR code as PNG image |
| GET | `/api/qr/{token}/analytics` | Get scan count and daily breakdown |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

API docs available at http://localhost:8000/docs

## Example

```bash
# Create a QR code
curl -X POST http://localhost:8000/api/qr/create \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'

# Response
{
  "token": "Os8TXDb",
  "short_url": "http://localhost:8000/r/Os8TXDb",
  "qr_code_url": "http://localhost:8000/api/qr/Os8TXDb/image",
  "original_url": "https://example.com"
}
```

## Project Structure

```
app/
├── main.py          # FastAPI app initialization
├── routes.py        # API endpoints
├── schemas.py       # Pydantic request/response models
├── models.py        # SQLAlchemy DB models (url_mappings, scan_events)
├── token_gen.py     # SHA-256 + Nonce + Base62 token generation
├── url_validator.py # URL normalization and validation
└── database.py      # SQLite connection
```

import json
import os
import hmac
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data.json"
API_KEY = os.getenv("API_KEY", "").strip()

app = FastAPI(
    title="Private Number Information API",
    description="API-key protected search over the locally stored dataset.",
    version="1.0.0",
)

def load_database():
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("data.json must contain a JSON list")
        return data
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"Could not load data.json: {exc}") from exc

DATABASE = load_database()

def require_api_key(x_api_key: Optional[str]):
    if not API_KEY:
        raise HTTPException(status_code=503, detail="Server API_KEY is not configured")
    if not x_api_key or not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

def public_record(row):
    # Do not return street addresses from this endpoint.
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "phone": row.get("phone"),
        "city": row.get("city"),
    }

@app.get("/")
def home():
    return {"message": "Private Number Information API", "docs": "/docs", "records_loaded": len(DATABASE)}

@app.get("/health")
def health():
    return {"status": "ok", "records_loaded": len(DATABASE)}

@app.get("/search")
def search(
    q: str = Query(..., min_length=2, max_length=100, description="Name or phone search"),
    limit: int = Query(10, ge=1, le=10),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    require_api_key(x_api_key)
    query = q.strip().casefold()
    digits = "".join(ch for ch in query if ch.isdigit())
    results = []
    for row in DATABASE:
        name = str(row.get("name", "")).casefold()
        name_search = str(row.get("name_search", "")).casefold()
        phone = str(row.get("phone", "")).casefold()
        phone_digits = "".join(ch for ch in phone if ch.isdigit())
        if query in name or query in name_search or query in phone or (digits and digits in phone_digits):
            results.append(public_record(row))
            if len(results) >= limit:
                break
    return {"count": len(results), "results": results}

@app.get("/lookup/{phone}")
def lookup_phone(
    phone: str,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    require_api_key(x_api_key)
    wanted = "".join(ch for ch in phone if ch.isdigit())
    if len(wanted) < 7:
        raise HTTPException(status_code=400, detail="Provide a valid phone number")
    matches = []
    for row in DATABASE:
        current = "".join(ch for ch in str(row.get("phone", "")) if ch.isdigit())
        if current == wanted:
            matches.append(public_record(row))
    return {"count": len(matches), "results": matches}
  

# main.py
import os
import random
import io
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, validator
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, func
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError

# Load .env
load_dotenv()

# --- Config ---
# PostgreSQL configuration
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "country_cache")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")

# Build DATABASE_URL from PostgreSQL components or fallback to SQLite
if POSTGRES_PASSWORD:
    DATABASE_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}?sslmode=require"
else:
    # Fallback to SQLite for development environments
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
REFRESH_TIMEOUT = int(os.getenv("REFRESH_TIMEOUT_SECONDS", "20"))

RESTCOUNTRIES_URL = "https://restcountries.com/v2/all?fields=name,capital,region,population,flag,currencies"
EXCHANGE_URL = "https://open.er-api.com/v6/latest/USD"

# --- Database setup ---
# PostgreSQL-optimized engine configuration
if DATABASE_URL.startswith("postgresql"):
    # PostgreSQL-specific optimizations
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        future=True,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=3600,
        echo=False
    )
else:
    # SQLite configuration (fallback for development)
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class Country(Base):
    __tablename__ = "countries"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    capital = Column(String(255), nullable=True)
    region = Column(String(255), nullable=True)
    population = Column(Integer, nullable=False)
    currency_code = Column(String(10), nullable=True)
    exchange_rate = Column(Float, nullable=True)
    estimated_gdp = Column(Float, nullable=True)
    flag_url = Column(Text, nullable=True)
    last_refreshed_at = Column(DateTime(timezone=True), nullable=True)

class Meta(Base):
    __tablename__ = "meta"
    id = Column(Integer, primary_key=True)
    key = Column(String(255), unique=True, nullable=False)
    value = Column(Text, nullable=True)

Base.metadata.create_all(bind=engine)

# --- Pydantic schemas ---
class CountryOut(BaseModel):
    id: int
    name: str
    capital: Optional[str]
    region: Optional[str]
    population: int
    currency_code: Optional[str]
    exchange_rate: Optional[float]
    estimated_gdp: Optional[float]
    flag_url: Optional[str]
    last_refreshed_at: Optional[datetime]

    class Config:
        from_attributes = True

class ErrorResponse(BaseModel):
    error: str
    details: Optional[Dict[str, str]]

app = FastAPI(title="Country Currency & Exchange API")

# --- Utils: external API fetchers ---
def fetch_countries():
    try:
        r = requests.get(RESTCOUNTRIES_URL, timeout=REFRESH_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise RuntimeError(f"Could not fetch data from restcountries.com: {str(e)}")

def fetch_exchange_rates():
    try:
        r = requests.get(EXCHANGE_URL, timeout=REFRESH_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise RuntimeError(f"Could not fetch data from open.er-api.com: {str(e)}")

# --- Helper: save meta (like last_refreshed_at) ---
def set_meta(session, key: str, value: str):
    m = session.query(Meta).filter(Meta.key == key).one_or_none()
    if m:
        m.value = value
    else:
        m = Meta(key=key, value=value)
        session.add(m)

def get_meta(session, key: str) -> Optional[str]:
    m = session.query(Meta).filter(Meta.key == key).one_or_none()
    return m.value if m else None

# --- Image generation ---
CACHE_DIR = "cache"
SUMMARY_IMAGE_PATH = os.path.join(CACHE_DIR, "summary.png")

def generate_summary_image(session, last_refreshed_iso: str):
    # Ensure cache dir exists
    os.makedirs(CACHE_DIR, exist_ok=True)

    # Get total and top 5 by estimated_gdp (non-null)
    total = session.query(func.count(Country.id)).scalar() or 0
    top5 = session.query(Country).filter(Country.estimated_gdp != None).order_by(Country.estimated_gdp.desc()).limit(5).all()

    # Make a simple image
    width, height = 800, 400
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", size=18)
    except:
        font = ImageFont.load_default()

    draw.text((20, 20), f"Total countries: {total}", font=font, fill=(0, 0, 0))
    draw.text((20, 50), f"Last refreshed at: {last_refreshed_iso}", font=font, fill=(0, 0, 0))
    draw.text((20, 90), "Top 5 by estimated_gdp:", font=font, fill=(0, 0, 0))
    y = 120
    for idx, c in enumerate(top5, start=1):
        draw.text((30, y), f"{idx}. {c.name} — {c.estimated_gdp:.2f}", font=font, fill=(0,0,0))
        y += 30

    img.save(SUMMARY_IMAGE_PATH)

# --- Endpoint: POST /countries/refresh ---
@app.post("/countries/refresh")
def refresh_countries():
    # Step 1: fetch external data first (fail early if external problem)
    try:
        countries_data = fetch_countries()
    except RuntimeError as e:
        return JSONResponse(status_code=503, content={"error":"External data source unavailable", "details": str(e)})

    try:
        exchange_data = fetch_exchange_rates()
    except RuntimeError as e:
        return JSONResponse(status_code=503, content={"error":"External data source unavailable", "details": str(e)})

    # Validate exchange_data has rates
    if not isinstance(exchange_data, dict) or "rates" not in exchange_data:
        return JSONResponse(status_code=503, content={"error":"External data source unavailable", "details":"Could not fetch data from exchange API"})

    rates = exchange_data.get("rates", {})

    # Now we have both APIs — proceed with a DB transaction
    session = SessionLocal()
    try:
        last_refresh_dt = datetime.now(timezone.utc)
        # We'll upsert per-country but ensure whole operation completes or fails.
        # Simple approach: iterate and upsert; on any DB error raise and rollback.
        for c in countries_data:
            # Extract required fields safely
            name = c.get("name")
            population = c.get("population")
            capital = c.get("capital")
            region = c.get("region")
            flag_url = c.get("flag")
            currencies = c.get("currencies") or []

            if not name or population is None:
                # per validation: name and population required; still store? spec requires 400 on invalid data,
                # but these are external API records; we skip invalid entries.
                continue

            # Currency handling: first currency code or None
            currency_code = None
            if isinstance(currencies, list) and len(currencies) > 0:
                first = currencies[0]
                # the countries API returns objects with 'code' key
                currency_code = first.get("code") if isinstance(first, dict) else None

            exchange_rate = None
            estimated_gdp = None

            if not currency_code:
                # Spec: set currency_code null, exchange_rate null, estimated_gdp 0, store it.
                estimated_gdp = 0
            else:
                # Find in rates (rates are relative to USD)
                # example: rates["NGN"] = 1600.23
                if currency_code in rates:
                    try:
                        exchange_rate_value = float(rates[currency_code])
                        exchange_rate = exchange_rate_value
                        # compute estimated_gdp = population × random(1000–2000) ÷ exchange_rate.
                        multiplier = random.randint(1000, 2000)
                        estimated_gdp = (population * multiplier) / exchange_rate_value
                    except Exception:
                        exchange_rate = None
                        estimated_gdp = None
                else:
                    # currency not found in exchange rates
                    exchange_rate = None
                    estimated_gdp = None

            # Upsert logic (match by name case-insensitive)
            existing = session.query(Country).filter(func.lower(Country.name) == name.lower()).one_or_none()
            if existing:
                existing.capital = capital
                existing.region = region
                existing.population = population
                existing.currency_code = currency_code
                existing.exchange_rate = exchange_rate
                existing.estimated_gdp = estimated_gdp
                existing.flag_url = flag_url
                existing.last_refreshed_at = last_refresh_dt
                session.add(existing)
            else:
                newc = Country(
                    name=name,
                    capital=capital,
                    region=region,
                    population=population,
                    currency_code=currency_code,
                    exchange_rate=exchange_rate,
                    estimated_gdp=estimated_gdp,
                    flag_url=flag_url,
                    last_refreshed_at=last_refresh_dt
                )
                session.add(newc)

        # update global meta last_refreshed_at
        set_meta(session, "last_refreshed_at", last_refresh_dt.isoformat())
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        return JSONResponse(status_code=500, content={"error":"Internal server error", "details": str(e)})
    finally:
        session.close()

    # After successful DB commit, generate summary image
    session = SessionLocal()
    try:
        generate_summary_image(session, last_refresh_dt.isoformat())
    finally:
        session.close()

    return {"message":"Refresh successful", "last_refreshed_at": last_refresh_dt.isoformat()}

# --- GET /countries with filters & sorting ---
@app.get("/countries", response_model=List[CountryOut])
def list_countries(region: Optional[str] = Query(None), currency: Optional[str] = Query(None), sort: Optional[str] = Query(None)):
    session = SessionLocal()
    try:
        q = session.query(Country)
        if region:
            q = q.filter(Country.region == region)
        if currency:
            q = q.filter(Country.currency_code == currency)
        if sort:
            if sort == "gdp_desc":
                q = q.order_by(Country.estimated_gdp.desc())
            elif sort == "gdp_asc":
                q = q.order_by(Country.estimated_gdp.asc())
        results = q.all()
        return results
    finally:
        session.close()

# --- GET /countries/image ---
@app.get("/countries/image")
def get_image():
    # Use absolute path to ensure we find the file
    abs_path = os.path.abspath(SUMMARY_IMAGE_PATH)
    if not os.path.exists(abs_path):
        return JSONResponse(status_code=404, content={"error": f"Summary image not found at {abs_path}"})
    return FileResponse(abs_path, media_type="image/png")

# --- GET /countries/{name} ---
@app.get("/countries/{name}", response_model=CountryOut)
def get_country(name: str):
    session = SessionLocal()
    try:
        c = session.query(Country).filter(func.lower(Country.name) == name.lower()).one_or_none()
        if not c:
            raise HTTPException(status_code=404, detail={"error":"Country not found"})
        return c
    finally:
        session.close()

# --- DELETE /countries/{name} ---
@app.delete("/countries/{name}")
def delete_country(name: str):
    session = SessionLocal()
    try:
        c = session.query(Country).filter(func.lower(Country.name) == name.lower()).one_or_none()
        if not c:
            return JSONResponse(status_code=404, content={"error":"Country not found"})
        session.delete(c)
        session.commit()
        return {"message": f"Country '{name}' deleted"}
    except SQLAlchemyError as e:
        session.rollback()
        return JSONResponse(status_code=500, content={"error":"Internal server error", "details": str(e)})
    finally:
        session.close()

# --- GET /status ---
@app.get("/status")
def status():
    session = SessionLocal()
    try:
        total = session.query(func.count(Country.id)).scalar() or 0
        last_ref = get_meta(session, "last_refreshed_at")
        return {"total_countries": total, "last_refreshed_at": last_ref}
    finally:
        session.close()

# --- Basic validation on create/update (not used in refresh but useful if you add manual endpoints) ---
class CountryIn(BaseModel):
    name: str
    population: int
    currency_code: Optional[str]
    capital: Optional[str]
    region: Optional[str]
    flag_url: Optional[str]

    @validator("name")
    def name_required(cls, v):
        if not v or not v.strip():
            raise ValueError("is required")
        return v

    @validator("population")
    def population_required(cls, v):
        if v is None:
            raise ValueError("is required")
        if v < 0:
            raise ValueError("must be non-negative")
        return v

# --- Root health ---
@app.get("/")
def root():
    return {"message":"Country Currency & Exchange API. See /docs for interactive API docs."}

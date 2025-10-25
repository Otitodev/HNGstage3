# 🌍 Country Currency & Exchange API

A FastAPI backend that fetches country and currency data, matches exchange rates, computes estimated GDP, and caches results in MySQL.

---

## 🚀 Features

* Fetch data from **RestCountries** & **Open ER API**
* Compute and store `estimated_gdp`
* CRUD + filter + sort endpoints
* Summary image generation (`Top 5 GDPs`)
* MySQL persistence & `.env` config

---

## 🧩 Endpoints

| Method   | Endpoint             | Description                                                 |
| -------- | -------------------- | ----------------------------------------------------------- |
| `POST`   | `/countries/refresh` | Fetch & update all countries                                |
| `GET`    | `/countries`         | List countries (`?region=`, `?currency=`, `?sort=gdp_desc`) |
| `GET`    | `/countries/{name}`  | Get single country                                          |
| `DELETE` | `/countries/{name}`  | Delete a country                                            |
| `GET`    | `/status`            | Show total + last refresh                                   |
| `GET`    | `/countries/image`   | Get generated summary image                                 |

---

## ⚙️ Quick Setup

### 1️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

### 2️⃣ Configure `.env`

```bash
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/country_cache
APP_HOST=0.0.0.0
APP_PORT=8000
REFRESH_TIMEOUT_SECONDS=20
```

### 3️⃣ Run locally

```bash
uvicorn main:app --reload
```

→ Open [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🐳 Optional: Docker Compose

```bash
docker-compose up --build
```

---

## ☁️ Deployment

1. Push to GitHub
2. Connect repo to **Leapcell.io / Railway / AWS**
3. Add `.env` variables in dashboard
4. Deploy service container

---

## 🧾 Example Error Responses

```json
{"error":"Country not found"}
{"error":"External data source unavailable","details":"Could not fetch data from restcountries.com"}
```

---




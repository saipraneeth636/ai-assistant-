# SalesIQ — AI-Powered Business Intelligence Dashboard

A full-stack business intelligence web application with a Groq-powered AI assistant that answers questions about sales data in natural language.

## 🚀 Features

- **Live Dashboard** — KPI cards, monthly revenue trend, regional breakdown, top products
- **AI Assistant** — Ask questions in plain English; answers are grounded in real database data via Groq's Llama 3.1
- **4 Pages** — Dashboard · Products · Regions · AI Assistant
- **Safe by Design** — The LLM never runs SQL; all queries are pre-defined and parameterised
- **SQLite Database** — Auto-imported from CSV on first run

## 🛠 Tech Stack

| Layer | Tech |
|---|---|
| Backend | Python · FastAPI · Uvicorn |
| AI | Groq API (Llama 3.1-8b-instant) |
| Database | SQLite |
| Frontend | Vanilla HTML · CSS · JavaScript · Chart.js |

## ⚡ Quick Start

### 1. Install dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Set your Groq API key
Create `backend/.env`:
```env
GROQ_API_KEY=your_key_here
```
Get a free key at [console.groq.com/keys](https://console.groq.com/keys)

### 3. Start the backend
```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

### 4. Open the frontend
```bash
# From the salesiq/ folder
python -m http.server 3000
```
Then open: **http://localhost:3000/index.html**

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/analytics/overview` | KPI summary |
| GET | `/api/analytics/monthly-revenue` | Monthly revenue |
| GET | `/api/analytics/region-revenue` | Revenue by region |
| GET | `/api/analytics/top-products` | Top products |
| POST | `/api/chat` | AI assistant |
| GET | `/api/suggestions` | Suggested questions |
| GET | `/api/health` | Health check |

## 📊 Dataset

Sales data with 50 transactions covering:
- **Products:** Laptop Stand, Wireless Mouse, Office Chair, Monitor, Keyboard, Desk, USB-C Hub
- **Regions:** North, South, East, West
- **Period:** Jan – Jun 2026
- **Currency:** INR (₹)

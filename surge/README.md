# SURGE

FastAPI backend for SURGE (incidents, event timelines and links between related
incidents), plus a read-only React + Leaflet map. No accounts, photos, status
logic or posting yet.

Requires Python 3.14, PostgreSQL (any recent version; 18 is fine) and Node.js.

## Backend setup

From `surge/backend/`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

On macOS/Linux the activate step is `source .venv/bin/activate`.

## Configure

The backend reads settings from `.env` in `backend/`:

```powershell
Copy-Item .env.example .env
```

Then open `.env` and replace `YOUR_PASSWORD` in **both** URLs with your PostgreSQL
password. The app uses `DATABASE_URL`; the tests use `TEST_DATABASE_URL`.

## Create the databases

With `psql` (or pgAdmin), create two empty databases:

```powershell
createdb -U postgres surge
createdb -U postgres surge_test
```

Tables are created automatically on startup with `create_all`.

## Run the backend

```powershell
python -m uvicorn app.main:app --reload
```

- Health check: <http://127.0.0.1:8000/health>
- API docs: <http://127.0.0.1:8000/docs>

## Frontend (map)

Requires Node.js. In a second terminal, from `surge/`:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The dev server proxies `/api` to the backend on
<http://localhost:8000>, so start the backend first. `npm run build` creates a
static build in `frontend/dist`.

## Seed data

To fill the main database with ~30 sample incidents around Chennai (with some
notes and linked clusters):

```powershell
python seed.py
```

This **clears** `incidents`, `events` and `incident_links` first, so only run it
on a database you are happy to wipe. Afterwards `GET /incidents` returns about 30
items and the linked clusters report the right `group_size`.

## Tests

```powershell
python -m pytest
```

Tests run against `surge_test`, never the main database. The frontend has no
automated tests in this phase.

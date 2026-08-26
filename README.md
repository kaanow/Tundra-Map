# Tundra-Map

Freezer inventory for two users. Web app (PWA) + Postgres + Brother QL-810WC label printer.

## Shape

- **Backend**: FastAPI + Postgres. Deploys as a single Railway service (frontend built into the image).
- **Frontend**: Vite + React PWA. Installable to iOS/Android home screen.
- **Pi print worker**: Python daemon on a Raspberry Pi. Persistent Postgres connection, `LISTEN print_jobs`, prints via `brother_ql` when notified.
- **Auth**: shared secret in URL / header. No accounts.

## Print pipeline

```
[phone/browser]  --POST /items/{id}/print-->  [FastAPI]
                                                 |
                                                 v
                                         INSERT print_jobs
                                                 |
                                                 v      (trigger)
                                          NOTIFY print_jobs
                                                 |
                                                 v
                                     [Pi worker LISTENing]
                                                 |
                                                 v
                                     render PNG + brother_ql
                                                 |
                                                 v
                                     UPDATE print_jobs SET printed_at=now()
```

No inbound reachability to the Pi. Add/list/consume still work if the Pi is offline; the job just stays queued and prints when it wakes up.

## Layout

- `backend/` — FastAPI app, migrations, static-served built PWA
- `frontend/` — Vite + React PWA (builds into `backend/app/static/`)
- `pi-print-worker/` — daemon for the Pi, systemd unit, udev rules
- `Dockerfile`, `railway.json` — deploy artifacts

## Env vars

| var                | where     | example                                   |
|--------------------|-----------|-------------------------------------------|
| `DATABASE_URL`     | backend, worker | `postgres://user:pass@host:5432/frz` |
| `SHARED_SECRET`    | backend, worker | random 32-char string                |
| `PUBLIC_BASE_URL`  | backend, worker | `https://frz.up.railway.app`         |
| `PHOTO_DIR`        | backend         | `/data/photos` (Railway volume)      |
| `PRINTER_MODEL`    | worker          | `QL-810W`                            |
| `PRINTER_BACKEND`  | worker          | `pyusb` or `network` or `file`       |
| `PRINTER_IDENT`    | worker          | `usb://0x04f9:0x209c`                |
| `LABEL_SIZE`       | worker          | `29x90` (DK-1201)                    |

See `.env.example`.

## Deploy on Railway

1. `railway link` this repo (or create a new project via the UI).
2. Add a Postgres plugin. Railway auto-injects `DATABASE_URL`.
3. Set `SHARED_SECRET` and `PUBLIC_BASE_URL` in service env.
4. (Optional) mount a Volume at `/data` for photo persistence and set `PHOTO_DIR=/data/photos`.
5. First deploy runs migrations automatically (see `backend/app/migrate.py`).

## Local dev

```bash
# DB
sudo -u postgres createuser -P frz         # password: frz_dev
sudo -u postgres createdb -O frz frz
sudo -u postgres psql -d frz -c 'CREATE EXTENSION pgcrypto;'

# Backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.migrate
DATABASE_URL=postgres://frz:frz_dev@localhost:5432/frz \
SHARED_SECRET=dev-secret \
PUBLIC_BASE_URL=http://localhost:8000 \
  .venv/bin/uvicorn app.main:app --reload

# Frontend (dev)
cd frontend && npm install && npm run dev    # http://localhost:5173

# Frontend (production build, served by backend)
cd frontend && npm run build

# Print worker (dry-run, no printer needed)
cd pi-print-worker
python3 -m venv .venv && .venv/bin/pip install psycopg[binary] Pillow qrcode[pil]
DATABASE_URL=postgres://frz:frz_dev@localhost:5432/frz \
SHARED_SECRET=dev-secret \
PUBLIC_BASE_URL=http://localhost:8000 \
PRINTER_BACKEND=file \
  .venv/bin/python worker.py
# → labels land in /tmp/tundra-labels/
```

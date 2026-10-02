# Nova Cart 2.0

A serious full-stack foundation for the Nova Cart multi-vendor delivery marketplace.

## What is included

- React + Vite customer web app
- FastAPI backend
- SQLAlchemy database layer (SQLite by default; PostgreSQL-ready via `DATABASE_URL`)
- Hashed server-side sessions using scrypt password hashes
- CSRF protection for state-changing requests
- Security headers and consistent API error envelopes
- Role-aware customer, dealer, delivery and admin surfaces
- Catalog, cart, checkout and strict order-state transitions
- Inventory deduction during checkout
- Private prescription upload validation/storage foundation
- Mock payment, routing, OCR, storage and notification provider abstractions
- PWA manifest
- Automated backend tests
- Development seed data

## Important development-mode boundary

Payment, maps/routing, OCR, notifications and storage are deliberately labelled as MOCK/DEVELOPMENT here because no production credentials are available in this environment. The code provides replaceable provider interfaces; it does not claim those external systems are connected.

## Run locally

### Backend

```bash
cd backend
python -m pip install -r requirements.txt
python scripts_seed.py
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run build
npm run dev
```

For a single-process preview after building the frontend, start the backend. FastAPI will serve `frontend/dist` when that directory exists.

## Development accounts

- Customer: `9000000001` / `customer123`
- Dealer: `9000000002` / `dealer123`
- Delivery: `9000000003` / `delivery123`
- Admin: `9000000004` / `admin123`

These credentials are for local development only and must be replaced before deployment.

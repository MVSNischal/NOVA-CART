# Nova Cart architecture

## Request flow

Browser → React/Vite UI → FastAPI API → service layer → SQLAlchemy → SQLite/PostgreSQL.

External capabilities are hidden behind provider abstractions so the business logic does not depend directly on a payment, maps, OCR or notification vendor.

## Authorization

Authentication is server-side session based. Every protected request resolves the current user from a hashed session token stored in the database. State-changing requests require the CSRF token. Dealer/delivery/customer ownership checks are enforced in backend queries/routes.

## Order state machine

Orders move through a constrained state machine. A transition is rejected with a 409 error when the requested next state is not allowed. Every successful transition is recorded in `order_events` with actor, previous status and new status.

## Production hardening still required

Before production, replace development accounts/secrets, configure PostgreSQL, Redis/job workers, HTTPS, a real object store, a real payment provider with verified webhooks, a real routing/geocoding service, real OCR/AI integrations, production notification channels, centralized logs/metrics, backups, secret management, vulnerability scanning and end-to-end tests against the production configuration.

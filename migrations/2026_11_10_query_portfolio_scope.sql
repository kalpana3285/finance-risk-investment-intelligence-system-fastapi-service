-- Persist the authenticated portfolio scope with each asynchronous query so
-- the worker can answer account-scoped portfolio listing requests safely.
ALTER TABLE query_requests
    ADD COLUMN IF NOT EXISTS authorized_portfolio_ids JSON NOT NULL DEFAULT '[]'::json;

ALTER TABLE query_requests
    ADD COLUMN IF NOT EXISTS all_portfolios_access BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE query_requests
    ADD COLUMN IF NOT EXISTS principal_roles JSON NOT NULL DEFAULT '[]'::json;

# Inventory Management System

A Django web app for managing products, suppliers, stock, purchase orders and sales.

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_demo           # optional: demo users, products and 150 days of history
python manage.py runserver
```

Open http://127.0.0.1:8000 and log in as `admin` / `ChangeMe123!` (the demo data also creates `manager`, `sales`
and `viewer` with the same password). Without the demo data, create your own admin with
`python manage.py createsuperuser`.

SQLite is used by default. For PostgreSQL, copy `.env.example` to `.env`, fill in the `DB_*` values and export them,
or run `docker compose up --build`.

## Roles

| Role | Can do |
|---|---|
| Admin | everything, including users and the audit log |
| Inventory Manager | products, suppliers, stock adjustments, purchase orders |
| Sales / Billing | create sales, view stock |
| Viewer / Auditor | read-only access to reports and the audit log |

## What's in it

- Products, categories and suppliers, with CSV import and export for products
- Stock ledger: stock is the sum of stock movements, written only through `inventory/services.post_movement()`
- Stock take, with differences posted as adjustments; large manual adjustments are flagged for review
- Purchase orders: draft, approve, send, receive goods (partial deliveries allowed), print
- Sales and billing with returns and printable invoices
- Dashboard and reports (stock valuation, movements, sales summary, purchases) with CSV download
- Audit log of changes to important records
- Read-only REST API at `/api/` (docs at `/api/docs/`, token from `POST /api/token/`)

## Moving data from the old Tkinter app

```bash
python manage.py import_legacy --host localhost --user root --password 1234 --database inventory_system --default-password "Temp#1234"
```

Employees become users, and products, suppliers, categories and sales are copied. Current stock becomes an opening
balance. The old app had no cost price, so cost is set equal to the selling price; correct it afterwards.

## Tests

```bash
python manage.py test
```

## Layout

`accounts` users and roles, `suppliers`, `catalog` products and categories, `inventory` stock ledger and stock take,
`purchasing`, `sales`, `reports` dashboard and reports, `audit` change log, `api` REST API, `core` shared helpers.

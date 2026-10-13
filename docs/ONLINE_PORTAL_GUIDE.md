# Online Pharmacy Portal — Architecture, Integration & Setup Guide

This guide documents the design, architecture, safety rules, database migrations, and operational procedures for the **Online Pharmacy Portal** (`@pharmacy/online-web` and `pharmacy-online-portal-api`).

---

## 1. Architecture & Core Areas

The online pharmacy portal provides three distinct, responsive areas:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ONLINE PHARMACY WEB APP                            │
├───────────────────────┬─────────────────────────────┬───────────────────────┤
│ 1. Public Storefront  │ 2. Customer Portal          │ 3. Staff Dashboard    │
│  • Medicine Catalog   │  • Registration & Sign In   │  • Order Queue & KPIs │
│  • Category Browsing  │  • Profile & Address Mgmt   │  • Pharmacist Review  │
│  • Search & Salt Info │  • Live Stepper Tracking    │  • Stock Availability │
│  • Persistent Cart    │  • Customer Order Isolation │  • Catalog Editor     │
│  • Safe Checkout Flow │  • Order Cancellation       │  • Immutable Audits   │
└───────────────────────┴─────────────────────────────┴───────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 FASTAPI BACKEND SERVICE (services/online-portal-api)        │
│  • Role-based Access Control (ADMIN, PHARMACIST, STAFF, CUSTOMER)           │
│  • Passlib PBKDF2/Bcrypt salted hashing & PyJWT token management            │
│  • Automatic SPA static distribution serving from `apps/online-web/dist`    │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 POSTGRESQL DATABASE (with SQLite Local Fallback)            │
│  • Users, Roles, Customers, Categories, Products, Orders, History, Audits   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Decoupling & Integration with the Offline MediHisaab

### The Risk of Real-Time Direct Stock Coupling
The core pharmacy POS (`apps/daemon` and `apps/web`) operates offline-first on localhost workstations inside physical retail pharmacies (frequently with intermittent internet and concurrent counter billing). Attempting direct real-time bidirectional synchronization with a cloud online store without staff confirmation introduces severe risks:
- Dispensing medicines in the physical store while an online customer checks out simultaneously leads to overselling.
- Scheduled/prescription medications would be inadvertently dispatched without physical prescription validation.

### The Safe Reversible Integration Solution
To prevent overselling and guarantee compliance with pharmacy regulations:
1. **Physical Acceptance Workflow (`PENDING_CONFIRMATION`):**
   - When a customer places an order for over-the-counter products, the order enters `PENDING_CONFIRMATION`.
   - Pharmacy counter staff inspect physical shelf inventory and click **"Confirm Order"** before the customer is notified and items are packed.
2. **Prescription Items Gate (`PHARMACIST_REVIEW`):**
   - Products flagged with `is_prescription_required = true` automatically place the order into `PHARMACIST_REVIEW`.
   - Standard staff cannot approve this order. Only users with the **`PHARMACIST`** or **`ADMIN`** role can review, input clinical notes, and approve the order for dispensing.
3. **Card-Free Payment Safety:**
   - No payment card numbers are collected or stored online.
   - Customers select **"Pay at Pharmacy Counter"** (for in-store pickup) or **"Cash / UPI on Delivery"** (for local delivery).

---

## 3. Database Models & Schema

The online portal uses SQLAlchemy 2.0 and supports PostgreSQL (`postgresql+psycopg2://`) as well as SQLite (`sqlite:///`) for local development and testing.

| Entity | Table Name | Purpose | Key Fields |
|---|---|---|---|
| **Staff Users** | `portal_staff_users` | Pharmacy staff & admins | `id`, `email`, `password_hash`, `full_name`, `role` (`ADMIN`, `PHARMACIST`, `STAFF`), `is_active` |
| **Customers** | `portal_customers` | Online store shoppers | `id`, `email`, `password_hash`, `full_name`, `phone`, `delivery_address`, `is_active` |
| **Categories** | `portal_categories` | Product classification | `id`, `name`, `slug`, `description`, `display_order`, `is_active` |
| **Products** | `portal_products` | Medicines & healthcare | `id`, `category_id`, `name`, `slug`, `generic_name`, `dosage_form`, `pack_size`, `mrp_paise`, `selling_price_paise`, `is_prescription_required`, `stock_status` (`IN_STOCK`, `LOW_STOCK`, `OUT_OF_STOCK`), `description`, `usage_instructions`, `side_effects` |
| **Orders** | `portal_orders` | Customer online orders | `id`, `order_number`, `customer_id`, `fulfillment_type` (`PICKUP`, `DELIVERY`), `payment_method`, `status` (`PENDING_CONFIRMATION`, `PHARMACIST_REVIEW`, `CONFIRMED`, `PREPARING`, `READY_FOR_PICKUP`, `OUT_FOR_DELIVERY`, `DELIVERED`, `CANCELLED`), `subtotal_paise`, `delivery_fee_paise`, `total_paise`, `pharmacist_notes`, `rejection_reason` |
| **Order Items** | `portal_order_items` | Products in an order | `id`, `order_id`, `product_id`, `product_name`, `generic_name`, `dosage_form`, `pack_size`, `unit_price_paise`, `quantity`, `total_paise`, `is_prescription_required` |
| **Status History** | `portal_order_status_history` | Step progression history | `id`, `order_id`, `from_status`, `to_status`, `changed_by_type`, `changed_by_name`, `notes`, `created_at` |
| **Audit Logs** | `portal_audit_logs` | Immutable staff actions | `id`, `staff_user_id`, `staff_email`, `action`, `entity_type`, `entity_id`, `details_json`, `created_at` |

---

## 4. Default Seed Accounts for Local Testing

When the backend service starts, it automatically initializes database tables and seeds sample data:

| Account Type | Email | Password | Role & Permissions |
|---|---|---|---|
| **Chief Administrator** | `admin@apexhealthcare.com` | `AdminPassword2026!` | `ADMIN` — Full access, catalog edits, category creation, audit inspection, order approvals |
| **Registered Pharmacist** | `pharmacist@apexhealthcare.com` | `PharmSecure2026!` | `PHARMACIST` — Prescription verification, clinical notes, order approvals, audit inspection |
| **Fulfillment Staff** | `staff@apexhealthcare.com` | `StaffPass2026!` | `STAFF` — Stock availability toggles, order packing, delivery status progression |
| **Demo Customer** | `customer@example.com` | `CustomerPass2026!` | `CUSTOMER` — Order history, personal profile, checkout |

---

## 5. Local Development Quickstart

### Prerequisites
- Node.js 18+ & npm
- Python 3.11+

### Step 1: Install Dependencies
```bash
# Install node packages
npm install

# Install backend dependencies & editable package
pip install -r services/online-portal-api/requirements.txt
pip install -e services/online-portal-api
```

### Step 2: Run Backend API Service
```bash
# Start backend on port 8000
python -m uvicorn portal_service.app:app --host 127.0.0.1 --port 8000 --reload
```
Interactive OpenAPI documentation will be accessible at `http://127.0.0.1:8000/api/docs`.

### Step 3: Run Frontend Web Portal (Development Mode)
```bash
npm run dev:portal
```
The Vite development server will start at `http://localhost:5174/` with automatic API proxying to `http://127.0.0.1:8000`.

### Step 4: Run Automated Tests
```bash
# Run online portal backend integration tests
pytest services/online-portal-api/tests -v

# Run typescript typecheck on frontend
npm run typecheck:portal

# Verify offline POS daemon tests are untouched
pytest apps/daemon/tests/test_licensing.py -q
```

---

## 6. Environment Configuration

Copy `services/online-portal-api/.env.example` to `services/online-portal-api/.env`:

```env
# Database connection (PostgreSQL in production, SQLite in local dev)
DATABASE_URL=postgresql+psycopg2://portal_admin:YOUR_DB_PASSWORD@localhost:5432/pharmacy_online_portal

# JWT Security
JWT_SECRET_KEY=replace-with-a-secure-random-secret-key-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

# Environment mode
ENVIRONMENT=production
CORS_ORIGINS=https://portal.yourdomain.com,http://localhost:5174

# Pharmacy Store Details
STORE_NAME=Apex Healthcare & Pharmacy
STORE_TAGLINE=Your Trusted Neighborhood & Online Pharmacy
STORE_PHONE=+91 98765 43210
STORE_EMAIL=care@apexhealthcare.com
STORE_ADDRESS=Plot 42, Health City Avenue, Medical District, Hyderabad 500081
OPERATING_HOURS=Mon - Sat: 8:00 AM - 10:30 PM | Sun: 9:00 AM - 9:00 PM
DELIVERY_FEE_PAISE=4000
FREE_DELIVERY_THRESHOLD_PAISE=50000
ESTIMATED_DELIVERY_TIME=45 - 90 minutes
ESTIMATED_PICKUP_TIME=Ready in 15 minutes
```

---

## 7. Cloud Deployment via Render

The service is configured in `render.yaml` with:
- Managed PostgreSQL database: `pharmacy-online-portal-db`
- Python Web Service: `pharmacy-online-portal`
  - Build command: `npm --workspace=apps/online-web run build && pip install -r services/online-portal-api/requirements.txt && pip install -e services/online-portal-api`
  - Start command: `uvicorn portal_service.app:app --host 0.0.0.0 --port $PORT`
  - Automatic static serving: The built frontend in `apps/online-web/dist` is served directly by FastAPI at `/`, eliminating the need for a separate CDN setup while preserving instant API routing.

---

## 8. Integrating an External Payment Gateway in the Future

When online credit/debit card, netbanking, or automated UPI processing is required:
1. Register with an authorized payment provider (e.g. Razorpay or Cashfree).
2. Store `PAYMENT_GATEWAY_KEY_ID` and `PAYMENT_GATEWAY_KEY_SECRET` in environment variables.
3. In `services/online-portal-api/src/portal_service/api/customer_orders.py`:
   - Add a `PAYMENT_PENDING` status.
   - Generate an order token and payment order ID via the payment provider API.
   - Create a webhook endpoint (`POST /api/v1/payments/webhook`) with HMAC signature verification to update order status to `PENDING_CONFIRMATION` or `PHARMACIST_REVIEW` upon successful payment capture.
4. **Important:** Never handle or store raw card numbers, expiry dates, or CVV codes on pharmacy servers.

-- =============================================================================
-- PHARMACY POS — CENTRAL VENDOR LICENSING & SUBSCRIPTION SCHEMA FOR SUPABASE
-- =============================================================================
-- Target Database: Supabase PostgreSQL
-- Purpose: Software vendor operations (Clients, Plans, Subscriptions, Payments, Licenses, Audits)
-- STRICT RULE: ZERO pharmacy operational data (medicines, batches, invoices, Khata,
-- patient data, or pharmacy.db) is stored in Supabase.
-- =============================================================================

-- Enable UUID extension if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. VENDOR PORTAL USERS
CREATE TABLE IF NOT EXISTS vendor_users (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'SUPPORT', -- OWNER, ADMIN, SUPPORT, READ_ONLY
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vendor_users_email ON vendor_users(email);
CREATE INDEX IF NOT EXISTS idx_vendor_users_role ON vendor_users(role);

-- 2. SUBSCRIPTION PLANS
CREATE TABLE IF NOT EXISTS plans (
    id SERIAL PRIMARY KEY,
    plan_code VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    billing_period VARCHAR(32) NOT NULL DEFAULT 'ANNUAL', -- TRIAL, MONTHLY, ANNUAL
    price INTEGER NOT NULL DEFAULT 0, -- price in paise (INR) or currency smallest unit
    currency VARCHAR(8) NOT NULL DEFAULT 'INR',
    maximum_terminals INTEGER NOT NULL DEFAULT 1,
    enabled_features TEXT NOT NULL DEFAULT 'ALL',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_plans_code ON plans(plan_code);
CREATE INDEX IF NOT EXISTS idx_plans_active ON plans(is_active);

-- 3. CLIENT PHARMACIES
CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
    client_code VARCHAR(64) UNIQUE NOT NULL, -- e.g. CL-1001
    business_name VARCHAR(255) NOT NULL,
    owner_name VARCHAR(255) NOT NULL,
    phone VARCHAR(32) NOT NULL,
    email VARCHAR(255) NOT NULL,
    address VARCHAR(500) NOT NULL DEFAULT '',
    city VARCHAR(100) NOT NULL DEFAULT '',
    state VARCHAR(100) NOT NULL DEFAULT '',
    postal_code VARCHAR(32) NOT NULL DEFAULT '',
    gstin VARCHAR(32),
    retail_drug_license VARCHAR(100),
    wholesale_drug_license VARCHAR(100),
    primary_contact_name VARCHAR(255) NOT NULL,
    notes TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'LEAD', -- LEAD, TRIAL, ACTIVE, SUSPENDED, CLOSED
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clients_code ON clients(client_code);
CREATE INDEX IF NOT EXISTS idx_clients_business_name ON clients(business_name);
CREATE INDEX IF NOT EXISTS idx_clients_phone ON clients(phone);
CREATE INDEX IF NOT EXISTS idx_clients_status ON clients(status);

-- 4. SUBSCRIPTIONS
CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    plan_id INTEGER NOT NULL REFERENCES plans(id),
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE', -- TRIALING, ACTIVE, PAST_DUE, CANCELLED, EXPIRED, SUSPENDED
    start_date DATE NOT NULL,
    current_period_start DATE NOT NULL,
    current_period_end DATE NOT NULL,
    grace_period_end DATE NOT NULL,
    trial_days INTEGER,
    is_trial BOOLEAN NOT NULL DEFAULT FALSE,
    cancelled_at TIMESTAMPTZ,
    payment_reference VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_client ON subscriptions(client_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_plan ON subscriptions(plan_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);

-- 5. MANUAL PAYMENT CONFIRMATIONS
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    subscription_id INTEGER REFERENCES subscriptions(id) ON DELETE SET NULL,
    amount INTEGER NOT NULL, -- amount in paise
    currency VARCHAR(8) NOT NULL DEFAULT 'INR',
    payment_date DATE NOT NULL,
    payment_method VARCHAR(64) NOT NULL DEFAULT 'UPI', -- UPI, BANK_TRANSFER, CHEQUE, CASH, OTHER
    payment_reference VARCHAR(255) NOT NULL, -- UTR / Reference ID
    status VARCHAR(32) NOT NULL DEFAULT 'CONFIRMED', -- CONFIRMED, PENDING, REFUNDED
    notes TEXT,
    recorded_by_email VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_payments_client ON payments(client_id);
CREATE INDEX IF NOT EXISTS idx_payments_sub ON payments(subscription_id);
CREATE INDEX IF NOT EXISTS idx_payments_reference ON payments(payment_reference);

-- 6. CRYPTOGRAPHICALLY SIGNED LICENSES (ED25519)
CREATE TABLE IF NOT EXISTS licenses (
    id SERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    subscription_id INTEGER REFERENCES subscriptions(id) ON DELETE SET NULL,
    license_id VARCHAR(128) UNIQUE NOT NULL, -- e.g. LIC-CL1001-20261009-ABCD
    client_name VARCHAR(255) NOT NULL,
    terminal_count INTEGER NOT NULL DEFAULT 1,
    activation_date VARCHAR(32) NOT NULL, -- YYYY-MM-DD
    expiry_date VARCHAR(32), -- YYYY-MM-DD or NULL for perpetual
    edition VARCHAR(64) NOT NULL DEFAULT 'COMMERCIAL', -- TRIAL, COMMERCIAL
    enabled_features TEXT NOT NULL DEFAULT 'ALL',
    signature VARCHAR(256) NOT NULL, -- 128-char hex Ed25519 signature
    issued_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_licenses_client ON licenses(client_id);
CREATE INDEX IF NOT EXISTS idx_licenses_license_id ON licenses(license_id);
CREATE INDEX IF NOT EXISTS idx_licenses_revoked ON licenses(revoked_at);

-- 7. SYSTEM SETTINGS
CREATE TABLE IF NOT EXISTS system_settings (
    id SERIAL PRIMARY KEY,
    key VARCHAR(128) UNIQUE NOT NULL,
    value TEXT NOT NULL,
    description VARCHAR(255),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_system_settings_key ON system_settings(key);

-- 8. IMMUTABLE AUDIT LOG
CREATE TABLE IF NOT EXISTS audit_events (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL,
    action VARCHAR(128) NOT NULL,
    entity_type VARCHAR(64) NOT NULL,
    entity_id VARCHAR(128),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(64),
    metadata_json TEXT -- Sanitized JSON (passwords and private keys strictly omitted)
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_events(user_email);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_events(action);

-- =============================================================================
-- SEED DEFAULT DATA (IDEMPOTENT)
-- =============================================================================

-- Seed System Settings
INSERT INTO system_settings (key, value, description)
VALUES 
    ('default_trial_days', '15', 'Default evaluation trial duration in days for new pharmacy clients.'),
    ('default_grace_days', '7', 'Default grace period in days before commercial restrictions apply.')
ON CONFLICT (key) DO NOTHING;

-- Seed Default Plans
INSERT INTO plans (plan_code, name, description, billing_period, price, currency, maximum_terminals, enabled_features, is_active)
VALUES
    ('TRIAL', 'Trial Plan (15 Days)', '15-day fully featured evaluation license for prospective pharmacy clients.', 'TRIAL', 0, 'INR', 2, 'ALL', TRUE),
    ('SINGLE_COUNTER', 'Single Counter Standard', 'Annual license for standalone single-workstation retail pharmacies.', 'ANNUAL', 600000, 'INR', 1, 'ALL', TRUE),
    ('MULTI_COUNTER', 'Multi-Counter LAN Commercial', 'Annual license for pharmacies operating up to 5 concurrent LAN billing counters.', 'ANNUAL', 1500000, 'INR', 5, 'ALL', TRUE),
    ('ANNUAL_COMMERCIAL', 'Enterprise Pharmacy Suite', 'Comprehensive commercial license for high-volume pharmacies with up to 20 counters.', 'ANNUAL', 3500000, 'INR', 20, 'ALL', TRUE)
ON CONFLICT (plan_code) DO NOTHING;

-- Seed Default Owner User (Password: OwnerSecurePass2026!)
INSERT INTO vendor_users (full_name, email, password_hash, role, is_active)
VALUES (
    'Software Vendor Administrator',
    'owner@apexhealth.local',
    '$pbkdf2-sha256$29000$t7x8Zz5mK1w.$9Y7z2A9D1fG3hJ5kL7mN9pQ1rS3tU5vW7xY9z1A3bC5',
    'OWNER',
    TRUE
)
ON CONFLICT (email) DO NOTHING;

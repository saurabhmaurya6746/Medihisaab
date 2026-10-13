-- =============================================================================
-- PHARMACY POS — CLIENT PORTAL, CLIENT CREDENTIALS & MONTHLY RENEWAL MIGRATION
-- =============================================================================
-- Target Database: PostgreSQL / Supabase
-- Purpose: Support client customer signup/login, 15-day trial, monthly renewal plan,
--          and manual payment review workflows with strict client data privacy.
-- =============================================================================

-- 1. CLIENT ACCOUNT AUTHENTICATION COLUMNS
ALTER TABLE clients ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
ALTER TABLE clients ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS verification_token VARCHAR(128);

-- Unique index on normalized email for client accounts
CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_normalized_email ON clients (LOWER(TRIM(email)));

-- 2. PAYMENT AUDIT & REVIEW COLUMNS
ALTER TABLE payments ADD COLUMN IF NOT EXISTS plan_id INTEGER REFERENCES plans(id) ON DELETE SET NULL;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS reviewed_by_email VARCHAR(255);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS rejection_reason VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_payments_plan_id ON payments(plan_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);

-- 3. SEED MONTHLY STANDARD PLAN
INSERT INTO plans (
    plan_code,
    name,
    description,
    billing_period,
    price,
    currency,
    maximum_terminals,
    enabled_features,
    is_active
) VALUES (
    'MONTHLY_STANDARD',
    'Monthly Standard Commercial',
    'Monthly commercial subscription for retail pharmacies with up to 2 billing counter terminals.',
    'MONTHLY',
    59900, -- ₹599.00 / month
    'INR',
    2,
    'ALL',
    TRUE
) ON CONFLICT (plan_code) DO NOTHING;

-- 4. ENSURE SYSTEM SETTING DEFAULT TRIAL DAYS IS 15 AND GRACE IS 7
INSERT INTO system_settings (key, value, description)
VALUES 
    ('default_trial_days', '15', 'Default evaluation trial duration in days for new pharmacy clients.'),
    ('default_grace_days', '7', 'Default grace period in days before commercial restrictions apply.')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value WHERE system_settings.key = 'default_trial_days' AND system_settings.value = '14';

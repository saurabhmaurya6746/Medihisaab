# MediHisaab Client Portal and Subscription Plan

## Goal

Give pharmacy owners one place to create an account, download the Windows application, start a configurable evaluation trial, see their license status, and request or complete a subscription renewal. Keep the pharmacy POS usable offline and keep pharmacy operations data on the client's computer.

## Recommended first release

Use the existing public download portal for product downloads and the existing licensing API/vendor portal for client and subscription administration. Add a separate customer-facing account area connected to the licensing API. Do not expose vendor administration screens to customer accounts.

### Client journey

1. The client creates an account with email, password, pharmacy/business name, owner/contact name, and phone. Collect address/GSTIN only if actually needed for licensing or invoicing.
2. Verify the email address (or phone) and create a unique client account. Prevent duplicate accounts by normalized email and phone, and provide a support process for corrections.
3. Start the configured evaluation period on first activation. The default can be 15 days, but the vendor owner can change it in settings or override it for a client. Show the start date, end date, and remaining days in both portal and POS.
4. The client downloads the current signed installer from the public download portal, installs it, and activates the trial with a short code or signed license file from the account portal. Avoid embedding a database credential or signing secret in the installer or browser code.
5. The account page shows current plan, license status, expiry date, number of licensed counters, renewal instructions, invoices/payment references, and available downloads.
6. For the first release, accept manual UPI/bank transfer and let the client submit the UTR/reference. Mark it pending until a vendor admin verifies receipt. Only a verified payment activates or renews a paid subscription. Do not trust a client-submitted payment reference as proof of payment.
7. After confirmation, extend the subscription for one month or one year from the later of today or current expiry, then issue a new signed license. Provide a clear import/activation flow and renewal receipt.
8. Remind clients before expiry (for example, 7 days, 3 days, and on expiry). Provide a configurable grace period (suggest 7 days for the initial plan). Display notices in the portal and POS.

## Expiry and offline policy

The local signed license is verified offline. A computer with no network cannot learn immediately that a subscription was renewed or revoked: the client must import a renewed license or the app must successfully check in when online. Define a reasonable offline license validity/check-in window and handle system clock rollback thoughtfully; do not claim instant remote enforcement while the application is offline.

When the grace period ends, restrict new commercial operations according to the product policy, but preserve local pharmacy data and provide read-only historical access and export/backup. Never delete, encrypt, or remotely wipe the local database because of nonpayment. Make reactivation restore normal operation without reinstalling or losing records.

## Data boundaries and security

- Licensing database: client account/contact details, password hash or identity-provider ID, plans, subscription dates/status, payment references/confirmation, license issuance records, and security audit events.
- Client computer only: medicine inventory, sales, purchases, customer/patient records, prescriptions, supplier balances, and pharmacy operational reports.
- Do not send pharmacy transaction or patient data to the licensing service.
- Store secrets only in environment/secret-manager configuration. Never commit `.env`, real credentials, private signing keys, or production database URLs.
- Use TLS, strong password hashing (prefer a well-maintained identity provider or Argon2id), email verification, rate limits, secure sessions, role separation, audit logs, least-privilege database credentials, and backups.
- Use a server-side database connection for vendor/licensing operations. Never put Supabase service-role keys or PostgreSQL credentials in frontend JavaScript or the downloadable client.
- Use migrations and keep public customer APIs separate from vendor-only APIs. Test tenant isolation so a client can access only their own account/subscription/license/download metadata.

## Suggested subscription states

`PENDING_VERIFICATION` -> `TRIALING` -> `ACTIVE` -> `PAST_DUE` (grace) -> `EXPIRED`.
Support `CANCELED` and vendor-controlled `SUSPENDED` states with audited reasons. A submitted payment remains `PENDING_REVIEW` until vendor verification; then mark it `CONFIRMED` or `REJECTED`.

## Delivery phases

1. **Audit current system:** inspect the licensing API, schema/migrations, vendor portal, public download portal, license signing/import in the POS, and deployment configuration. Reuse existing capabilities; report gaps before making a second overlapping implementation.
2. **Account and activation:** client registration/login, verification, duplicate handling, first-activation trial, customer dashboard, and trial license activation.
3. **Renewal:** monthly/annual plans, manual payment submission/review, renewal, signed license issuance, receipts, and audit trail.
4. **Expiry experience:** reminders, configurable trial/grace periods, offline behavior, read-only expired mode, and data export.
5. **Deployment hardening:** environment-variable setup, database migrations/backups, rate limits, monitoring without pharmacy data, and release/rollback guide.

## Decisions to keep consistent

- Use one configurable default trial duration across portal, API, documentation, and POS. The current project docs/configuration mention both 14 and 15 days; choose one (15 days is the requested starting value) and remove conflicting behavior.
- Offer monthly renewal as the requested default commercial option; annual can be an optional discounted plan.
- Begin with vendor-verified manual payments. Add a payment gateway only after selecting a provider and implementing verified server-side webhooks/idempotency.
- Keep customer self-service and vendor administration as separate roles and interfaces.


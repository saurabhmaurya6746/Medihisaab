# Antigravity Prompt: Implement MediHisaab Client Portal and Subscriptions

Paste the prompt below into Antigravity with the MediHisaab repository open.

---

You are working in the existing MediHisaab repository. Implement the customer-facing account/download/trial/monthly-subscription experience described below. This is an existing system: inspect it first and extend/reuse the current licensing API, database schema, vendor portal, download portal, signed-license workflow, and POS license enforcement. Do not create a parallel licensing system or replace working components without a demonstrated need.

## Start by auditing the repository

Read the repository instructions (`AGENTS.md` if present), and inspect at least:

- `docs/CLIENT_PORTAL_SUBSCRIPTION_PLAN.md`
- `docs/CLIENT_SUBSCRIPTION_GUIDE.md`
- `docs/SUPABASE_LICENSING_GUIDE.md`
- `docs/LICENSING_SECURITY_GUIDE.md`
- `docs/CLIENT_DATA_RETENTION_POLICY.md`
- `services/licensing-api/` including its API, models, migrations, tests, and `.env.example`
- `services/licensing-api/src/licensing_service/portal/`
- `portal/`
- the POS license validation/import and expiry enforcement paths in `apps/daemon/` and `apps/web/`
- deployment configuration and root package scripts

Before editing, summarize what already exists and list the concrete gaps this change will address. Then implement the smallest complete coherent solution in the established architecture. Keep all work in this repository and preserve unrelated user changes.

## Product behavior

Build a customer account experience, separate from the vendor admin portal:

1. Customer signup and login, with verified email (use existing infrastructure if present; otherwise provide a safe, documented verification approach). Collect only necessary account data: email, password, pharmacy name, contact person, and phone. Do not collect pharmacy transaction or patient data.
2. Create a unique client account and prevent duplicate normalized emails. Ensure customer APIs enforce ownership/tenant isolation.
3. Start the default trial on first activation, not merely on installer download. Make trial duration configurable by vendor in existing settings and overridable per client. Use 15 days as the initial default consistently across application, API, UI, migration/configuration, and docs.
4. Let the customer download the current installer and relevant guides from the account/download area. Keep the public installer distribution flow working. Do not expose private releases or another client's license.
5. Provide a customer dashboard showing plan, trial/subscription state, start/end dates, days remaining, counter allowance, renewal status/instructions, and license activation/download state.
6. Support monthly and annual plans if the current schema can express billing periods cleanly. Monthly is the initial default. Add server-side/manual payment submission with reference/UTR and amount; mark it pending review. Only vendor-authorized confirmation activates or renews a paid plan. Reuse existing vendor payment and subscription workflows.
7. On vendor confirmation, extend from max(today, current expiry) by the selected plan period and issue a signed license using the existing Ed25519 private-key server workflow. Let the customer retrieve/activate the renewed license securely.
8. Add configurable grace period (initial suggestion: 7 days), expiry notices/reminders, and a clear renewal path. Avoid duplicate reminders and audit meaningful state changes.
9. Respect offline licensing limits: explain/show when license status was last refreshed, and do not promise instant remote revocation or renewal on disconnected machines. Ensure renewed licenses can be imported without reinstalling.
10. After grace expires, enforce the established policy consistently: prevent new commercial operations as configured while preserving read-only historical access and data export. Never delete, encrypt, wipe, or make the local SQLite database inaccessible because of expiration. Reactivation must preserve all local data.

## Security and privacy requirements

- PostgreSQL/Supabase credentials, JWT secrets, email credentials, payment secrets, and Ed25519 private keys must be read only from server environment/secret configuration. Never hard-code them, print them in logs, commit them, bundle them into browser code, or include them in the installer.
- The PostgreSQL URL must be configured through `DATABASE_URL` in the server environment. Add only a safe placeholder such as `DATABASE_URL=postgresql://postgres.<project-ref>:<password>@<pooler-host>:6543/postgres` to `.env.example` if needed. Do not copy any supplied password-like string into source files or docs. The user will configure the real secret outside source control.
- Use the server-side licensing API for database access. Never place a Supabase service-role key or database URL in React/Vite environment variables or client code.
- Keep all medicine, invoice, purchase, patient, prescription, customer-ledger, and pharmacy stock data local. Do not add operational-data telemetry.
- Apply secure password hashing or the existing trusted identity provider, email verification, rate limiting, secure sessions, role-based access, tenant isolation, input validation, audit logging, and least-privilege database access.
- Use migrations compatible with the current deployment and avoid destructive schema/data changes.
- Ensure payment status is not trusted from the customer. A submitted UTR/reference is not proof of payment; vendor review must be explicit and audited.

## Implementation expectations

- Follow existing code conventions and types. Add or update focused automated tests for signup, trial timing/configuration, tenant isolation, payment pending/confirmation, renewal period extension, signed-license delivery authorization, and expired/read-only behavior. Run the relevant tests and report exact commands/results.
- Add/update API contracts and UI states, loading/error/empty states, and accessibility labels.
- Add migration(s), environment examples, setup/deployment steps, backup notes, and customer/vendor workflow docs as appropriate.
- Update trial duration references so the project no longer inconsistently advertises 14 vs. 15 days.
- Do not implement automatic recurring billing unless an existing payment gateway is configured and verified webhooks are available. Manual vendor-confirmed renewals are the first release.
- Do not silently claim an end-to-end email or payment integration if none exists. Clearly document any configuration or external account setup still required.

## Work process and final response

Inspect first, then implement. Keep changes scoped, preserve user work, and do not stop at a plan if the repository contains enough information to proceed. At completion, summarize the architecture reused, files changed, security/privacy decisions, tests run and results, and any remaining manual deployment configuration. Do not expose secrets in the final response.

---

## Supabase configuration reminder

Set the real PostgreSQL connection URL in the licensing API's hosting environment as `DATABASE_URL`. Use the Supabase pooler URL format and the correct password from Supabase dashboard. Do not place credentials in this prompt, frontend `.env` files, source control, or the installer. If the password previously pasted into chat is ever a real credential, rotate it before deployment.


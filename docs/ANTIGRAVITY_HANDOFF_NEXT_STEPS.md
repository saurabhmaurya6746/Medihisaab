# Antigravity Handoff — Next Steps

## Current release artifacts found

The following outputs are present in the workspace:

- Installer: `dist-release/MediHisaab-Setup-1.0.0.exe`
- Installer size: approximately 50.4 MB
- Standalone daemon: `dist/pharmacy-daemon/pharmacy-daemon.exe`
- Production frontend: `apps/web/dist/`
- Download portal: `dist-release/portal/index.html`
- Mirrored portal: `portal/index.html`
- Client licenses: `dist-release/licenses/LIC-CLIENT-001.json` through `LIC-CLIENT-100.json`
- License manifest: `dist-release/licenses/index.json`
- Render deployment guide: `docs/RENDER_DOWNLOAD_PORTAL_GUIDE.md`

The installer SHA-256 currently observed in the workspace is:

```text
44684E22E82D26C0DF4BF5F56425DABFBEF0EC995287DE401A945A0DA4A3E73D
```

Recalculate this hash after the final installer build. Do not publish a hash for an installer that changes afterward.

## What Antigravity reports as completed

- Frontend production build.
- Settings and theme work.
- UI cleanup and keyboard-shortcut help.
- PyInstaller daemon packaging.
- Inno Setup installer packaging.
- Standalone daemon health check.
- Backend tests and settings verification.
- LAN launcher updates.
- Backup/restore work.
- Offline license generation.
- Static download portal.

The report states that 102 backend tests and 8 settings checks passed. Run the tests again before release and keep the fresh command output with the release records.

## Important checks before distributing to clients

### 1. Test the installer on a clean Windows computer

Use a fresh Windows 10/11 virtual machine or computer with:

- No Node.js.
- No Python.
- No source repository.
- No existing MediHisaab installation.
- Internet disconnected after downloading the installer.

Verify:

- Installation completes.
- Desktop shortcut starts the application.
- First-run setup works.
- Billing and medicine search work.
- Database is created in `%LOCALAPPDATA%\\PharmacyApp\\data\\`.
- The application runs without internet.
- Uninstall does not delete business data unless the user explicitly confirms it.

### 2. Verify the license workflow

The release report describes a License tab and an upload workflow. A current frontend search did not find a License tab in `SettingsModal.tsx` or another visible license UI.

Before sending licenses to clients, verify the complete workflow:

1. Admin opens Settings.
2. Admin can find the license action.
3. Admin imports a client license file.
4. The application displays the active client name, license ID, terminal count, and expiry.
5. Invalid or modified licenses are rejected.

If the UI is missing, either add it or document the actual activation workflow. Do not tell clients to follow a workflow that is not present.

### 3. Treat the current HMAC licensing as tamper-evident, not high-security licensing

The current implementation contains the HMAC verification secret in the application code. Because the verifier and secret are delivered to the client, a determined user could extract the secret and generate a new license.

For basic offline entitlement tracking this may be acceptable for a pilot. For strong commercial licensing, replace the shared-secret design with asymmetric signing:

- Keep the private signing key only on the publisher machine or license service.
- Embed only the public verification key in the client application.
- Sign licenses with Ed25519 or an equivalent public-key signature scheme.
- Never place the private key, signing script secret, or master license secret in the installer.

Do not publish the generated license directory on the public download portal.

### 4. Check that release files do not contain secrets or client data

Before uploading anything to Render, inspect the portal and release package for:

- `.env` files.
- JWT secrets.
- License signing secrets.
- Private keys.
- SQLite databases.
- Client backups.
- Internal test data.

The public portal should contain only the installer, public documentation, release notes, and public checksum.

## Immediate next move

Do not distribute to 100 clients yet. Perform this release-candidate sequence:

```text
1. Verify the license UI/workflow.
2. Re-run frontend build and backend tests.
3. Rebuild the final installer.
4. Test installer on a clean Windows machine.
5. Test offline operation after installation.
6. Test printer and barcode hardware.
7. Test backup and restore.
8. Test LAN mode with two computers.
9. Upload only the verified installer and portal files to Render.
10. Pilot with 3–5 pharmacies.
11. Fix pilot issues.
12. Begin the 100-client rollout.
```

## Render pilot deployment

Use `portal/` as the static website source. The first pilot can use the Render-provided URL. Add a custom domain only after the installer and pilot workflow are stable.

If the installer is stored directly inside the static site, verify the complete download and checksum from a clean browser. For larger production traffic, keep the static website on Render and move the installer to dedicated release storage or a CDN.

## Client delivery package

For each client, provide:

```text
Client-Release/
├── MediHisaab-Setup-1.0.0.exe
├── Client-License.json
└── Documentation/
    ├── Installation guide
    ├── LAN setup guide
    └── Backup and restore guide
```

Do not provide the source repository or the shared license-generation secret.

## Release decision

The project has moved from development toward a release candidate, but it is not yet ready to call a commercial 100-client release until the clean-machine installer test, license workflow check, secret review, and pilot rollout are complete.

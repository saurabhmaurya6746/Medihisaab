# MediHisaab Download Portal on Render

This document explains how to publish a simple website where clients can download the MediHisaab Windows installer.

## 1. Recommended architecture

The download website and the pharmacy application are separate:

```text
Client browser
      |
      v
Render static website
      |
      +-- Download MediHisaab-Setup-X.Y.Z.exe
      +-- Installation guide
      +-- User guide
      +-- Support contact

Client Windows computer
      |
      +-- MediHisaab frontend
      +-- Local daemon
      +-- Local SQLite database
```

Render hosts only the download page and release files. It does not host the pharmacy database, billing API, or live client data.

After a client downloads and installs the application, the application runs locally and does not require internet access for normal pharmacy operations.

## 2. Is Render a good choice?

Yes, Render Static Sites are suitable for an initial pilot and for a small client distribution portal. Render provides a hosted static website URL and supports custom domains later. The site can contain an installer download link, documentation, release notes, and support information.

For a larger commercial rollout, keep the website on Render but consider moving the installer binary to dedicated release storage or a CDN. This separates normal website traffic from large installer downloads.

Do not deploy the local MediHisaab daemon or SQLite database to Render for the offline product.

## 3. What must be ready before publishing

Before creating the portal, finish and test:

- Production frontend build.
- Self-contained Windows installer.
- Backend runtime packaging.
- First-run setup.
- Admin login and permissions.
- Billing and stock operations.
- Printing and barcode workflows.
- Backup and restore.
- Standalone offline mode.
- LAN mode, if required.

The installer should not require clients to install Node.js or run development commands. Ideally, it should also include the Python runtime and backend dependencies, or package the backend as a standalone executable.

The current installer configuration is in `installer/pharmacy-pos-installer.iss`. Confirm that the final installer preserves:

```text
%LOCALAPPDATA%\PharmacyApp\data\pharmacy.db
%LOCALAPPDATA%\PharmacyApp\backups\
```

## 4. Prepare a release package

Use versioned release names:

```text
MediHisaab-Setup-1.0.0.exe
MediHisaab-Setup-1.1.0.exe
```

Do not upload:

- SQLite databases.
- Client backup files.
- `.env` files.
- Private signing keys.
- JWT secrets.
- Source code, unless the repository is intentionally public.
- Internal test data.

Create a checksum for every installer release. On Windows PowerShell:

```powershell
Get-FileHash .\MediHisaab-Setup-1.0.0.exe -Algorithm SHA256
```

Publish the resulting SHA-256 value on the release page or in a text file next to the download. This lets a client verify that the installer was not corrupted during download.

## 5. Simple portal structure

For the first version, use a small static website:

```text
release-portal/
└── public/
    ├── index.html
    ├── installation.html
    ├── support.html
    ├── releases.html
    └── downloads/
        ├── MediHisaab-Setup-1.0.0.exe
        └── MediHisaab-Setup-1.0.0.sha256.txt
```

The home page should contain:

- MediHisaab name and logo.
- One clear “Download for Windows” button.
- Current version number.
- Minimum Windows requirement.
- Short offline-operation explanation.
- Installation guide link.
- Backup and restore guide link.
- LAN setup guide link.
- Support email or contact method.

Example download link:

```html
<a href="/downloads/MediHisaab-Setup-1.0.0.exe" download>
  Download MediHisaab for Windows
</a>
```

The download page should not ask clients to download the source repository or run Python commands.

## 6. Create the Render Static Site

1. Push the portal files to a Git repository.
2. Open the Render Dashboard.
3. Select **New** and then **Static Site**.
4. Connect the repository that contains the portal.
5. Select the production branch.
6. Set the root directory to the portal directory if it is inside the MediHisaab repository.
7. For a plain HTML portal:
   - Build command: leave empty.
   - Publish directory: `public`.
8. If the portal uses Vite or another frontend builder:
   - Build command: use the portal's build command.
   - Publish directory: use the generated `dist` directory.
9. Create the site and wait for the first deployment to finish.
10. Open the Render-provided URL and test every link.

Render automatically redeploys the static site when the configured repository branch changes. Keep the portal repository separate from production client data.

## 7. Uploading a new release

For each release:

1. Build the frontend.
2. Build the backend package.
3. Build the Windows installer.
4. Test the installer on a clean Windows computer.
5. Calculate its SHA-256 checksum.
6. Copy the installer into the portal's `downloads` directory, or upload it to the selected release-storage location.
7. Update the version number and release notes on the portal.
8. Commit and push the portal change.
9. Wait for Render to redeploy.
10. Download the installer from the public portal and verify the checksum.

Never replace an old installer without keeping a versioned copy and release notes.

## 8. Installer download options

### Pilot option: installer inside the portal repository

This is the simplest approach. Put the `.exe` in `public/downloads/` and link to it from the page.

Use this only if the installer size and expected download volume are acceptable for the chosen Render plan. Test the complete download with a clean browser before sending the link to clients.

### Production option: portal plus separate release storage

Keep the website on Render, but store the installer in dedicated object storage or a release distribution service. The portal's download button points to that file.

This avoids putting a large binary in the website repository and makes it easier to manage multiple versions, access control, and download traffic.

If client-specific installers or licenses are used, do not put private files in a public static directory. Use authenticated or time-limited download links.

## 9. Domain name

A custom domain is optional for the pilot. The Render-provided URL is enough for testing.

Buy a domain after the product name and installer are stable. Example structure:

```text
yourbrand.com
yourbrand.com/download
yourbrand.com/docs
yourbrand.com/support
```

Connect the custom domain in Render after registering it with a domain registrar. Keep the domain account in the business owner's name, enable two-factor authentication, and enable automatic renewal.

## 10. Client distribution process

For each client:

1. Send the portal URL.
2. Client downloads the installer.
3. Client runs the installer.
4. Client creates the first Admin account.
5. Client completes store setup.
6. Client tests a sample medicine and test invoice.
7. Client configures the printer and barcode scanner.
8. Client creates an initial backup.
9. Client removes test data after verification.

For a multi-counter store:

1. Install MediHisaab on the primary server computer.
2. Start LAN mode on that computer.
3. Connect counter computers to the same private Wi-Fi or Ethernet network.
4. Open the server computer's LAN address in each counter browser.
5. Do not install separate databases on the counter computers.

## 11. Offline operation

The download portal requires internet only for downloading the installer and documentation.

After installation:

- Billing works locally.
- Inventory works locally.
- Reports work locally.
- The database remains on the pharmacy computer.
- Internet is not required for normal operations.

An offline computer cannot receive an update automatically without some transfer method. For a completely offline client, download the new installer on another computer and transfer it using a temporary network connection or removable media.

## 12. Security checklist

- Use HTTPS for the portal.
- Do not expose the local pharmacy API to the public internet.
- Do not publish client databases or backups.
- Do not publish secrets or private keys.
- Use unique Admin credentials for every client.
- Digitally sign the Windows installer when possible.
- Verify the installer checksum after upload.
- Keep old release installers available for controlled rollback.
- Keep a tested backup and restore process.
- Use a private network for LAN mode.

## 13. Final acceptance checklist

The release is ready for clients only when all of the following are true:

- The installer runs on a clean Windows machine.
- Node.js is not required.
- Manual Python setup is not required.
- The application starts from a desktop shortcut.
- The application works without internet after installation.
- The database survives an upgrade.
- Backup and restore work.
- The portal download works from a clean browser.
- The checksum matches the downloaded installer.
- The portal does not expose private data.
- A pilot pharmacy can complete setup using the documentation.

## 14. Recommended rollout

```text
Local development
        ↓
Clean Windows installer test
        ↓
3–5 pilot pharmacies
        ↓
Fix installer and documentation issues
        ↓
Publish Render download portal
        ↓
Distribute to remaining clients
```

Do not distribute the installer to all 100 clients until the clean-machine test and pilot rollout are successful.

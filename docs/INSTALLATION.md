# MediHisaab — Windows Installation Guide

## 1. System Requirements

| Specification | Minimum | Recommended |
| :--- | :--- | :--- |
| **Operating System** | Windows 10 (64-bit, Build 19041+) | Windows 11 (64-bit, 22H2+) |
| **Processor** | Dual-core 2.0 GHz x64 | Quad-core 2.5 GHz+ (Intel Core i3/i5 or AMD Ryzen) |
| **RAM** | 4 GB | 8 GB+ |
| **Storage** | 1 GB free SSD storage | 10 GB+ SSD (allows years of automated backups) |
| **Runtime** | Python 3.12 (64-bit) | Python 3.12+ added to system `PATH` |
| **Display** | 1280 × 720 | 1920 × 1080 Full HD (optimized for high-density counter POS) |
| **Networking** | Offline standalone (none required) | 100/1000 Mbps Ethernet / Wi-Fi for multi-counter LAN |

---

## 2. Installation Methods

### Method A: Automated Windows Installer (Recommended)
1. Double-click `MediHisaab-Setup-1.0.0.exe`.
2. Follow the setup wizard prompts. By default, the application installs to:
   ```
   C:\Program Files\MediHisaab
   ```
   (or `%LOCALAPPDATA%\Programs\MediHisaab` if running without administrator elevation).
3. The installer creates:
   - **Start Menu Shortcuts:**
     - `MediHisaab` (Standard single-workstation launcher)
     - `MediHisaab (LAN Server Mode)` (Multi-counter network server)
     - `Hardware & Printer Test` (Hardware diagnostics)
     - `Pharmacy Backups Folder` (Direct link to backup archives)
   - **Desktop Shortcut:** `MediHisaab`
4. The installer automatically preserves any existing database or transaction history.

---

### Method B: Portable ZIP Package
1. Extract `MediHisaab-v1.0.0-Portable.zip` to your preferred folder (e.g. `C:\MediHisaab`).
2. Verify that Python 3.12+ is installed and in `PATH`:
   ```powershell
   python --version
   ```
3. Launch `start-pharmacy.bat` to start the application.

---

### Method C: Deploying from Source Code
1. Clone or copy the project repository:
   ```cmd
   cd "C:\Users\hp\Desktop\Major Project\Good to Go\Pharmacy project"
   ```
2. Build the production frontend assets:
   ```cmd
   npm run build --workspace=apps/web
   ```
3. Launch using production launchers:
   ```cmd
   scripts\start-pharmacy.bat
   ```

---

## 3. Storage Architecture & Directory Layout

To comply with Windows NTFS permissions and avoid privilege escalation, MediHisaab stores all runtime state in user application data:

```
%LOCALAPPDATA%\PharmacyApp\
├── data\
│   ├── pharmacy.db          # Authoritative SQLite transactional database (WAL mode)
│   ├── pharmacy.db-wal      # Write-Ahead Log buffer
│   └── pharmacy.db-shm      # Shared memory index
├── backups\                 # Compressed .pbk hot backup archives
├── logs\
│   └── spooler_simulation.log # Hardware printer simulation log
└── secret.key               # 256-bit cryptographically secure JWT signing secret
```

> [!IMPORTANT]
> **Data Preservation Guarantee:**
> When upgrading to a newer version of MediHisaab, the installer replaces only application executables and web assets in the Program Files folder. Your `%LOCALAPPDATA%\PharmacyApp\data\pharmacy.db` and backup files are never overwritten.
> On uninstall, the uninstaller explicitly prompts:
> *"Do you want to DELETE your store database and transaction history? Select NO to preserve all sales invoices, ledger balances, and backup archives."*

---

## 4. Upgrading to a New Version

1. Close any running instances of MediHisaab (`Ctrl+C` in daemon windows or close browser tabs).
2. Run the new version installer `Pharmacy_POS_Setup_vX.X.X.exe`.
3. The setup wizard replaces program files while leaving `%LOCALAPPDATA%\PharmacyApp\data\pharmacy.db` untouched.
4. Launch MediHisaab. The daemon automatically runs any pending database migrations within an atomic transaction.

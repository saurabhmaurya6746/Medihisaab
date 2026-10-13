# MediHisaab — Troubleshooting & Maintenance Guide

## 1. Port 38291 Conflict ("Address already in use")

### Symptom:
Launching the daemon outputs:
```
[ERROR] [Errno 10048] error while attempting to bind on address ('127.0.0.1', 38291): address already in use
```

### Cause:
An existing instance of MediHisaab is already running in the background.

### Resolution:
1. Open PowerShell or Command Prompt.
2. Find the Process ID (PID) occupying port 38291:
   ```cmd
   netstat -ano | findstr :38291
   ```
3. Terminate the stale process using its PID (replace `12345` with the actual PID):
   ```cmd
   taskkill /F /PID 12345
   ```
4. Re-run `scripts\start-pharmacy.bat`.

---

## 2. Python Not Detected in PATH

### Symptom:
Double-clicking launcher scripts outputs:
```
[ERROR] Python runtime is not installed or not in system PATH.
```

### Resolution:
1. Download Python 3.12+ from [python.org](https://www.python.org/downloads/).
2. During installation, **ensure you check the box:**  
   `☑ Add python.exe to PATH`.
3. Restart your command prompt or computer.

---

## 3. Secondary LAN Terminal Cannot Connect ("Connection Refused" / "Timeout")

### Diagnostic Steps:
1. **Verify Ping:** From the secondary computer, open Command Prompt and ping the server:
   ```cmd
   ping 192.168.1.100
   ```
   If ping fails, ensure both computers are connected to the same Wi-Fi/router and that the Windows Network Profile is set to **Private Network** (not Public).
2. **Verify Firewall Rule:** On the server machine, execute:
   ```cmd
   netsh advfirewall firewall show rule name="MediHisaab LAN Server (TCP 38291)"
   ```
   If the rule is missing, add it via the administrator command in [LAN Setup Guide](LAN_SETUP_GUIDE.md).
3. **Verify Server Binding:** Ensure the server was started in LAN mode (`start-lan-server.bat`), which binds to `0.0.0.0` rather than `127.0.0.1`.

---

## 4. Printer Issues

### Symptom A: Printer Prints Gibberish or Hex Characters
- **Cause:** A thermal ESC/POS stream was sent to a standard Windows GDI postscript driver.
- **Resolution:** In Windows Printer Properties, ensure the printer uses its official manufacturer RAW ESC/POS driver or the **Generic / Text Only** driver.

### Symptom B: Cash Drawer Does Not Kick Open
- **Check Cable:** Ensure the RJ11 cable is plugged into the printer's drawer kick port, not a telephone modem or cash machine serial port.
- **Check Solenoid Voltage:** Verify whether the drawer solenoid is 12V or 24V. Standard Epson printers provide 24V on Pin 2.

---

## 5. Database Busy or Lock Contention

### Symptom:
Log outputs `sqlite3.OperationalError: database is locked`.

### Resolution:
MediHisaab uses SQLite Write-Ahead Logging (`PRAGMA journal_mode = WAL`) and sets a 10-second busy timeout (`PRAGMA busy_timeout = 10000;`).
If lock contention occurs:
1. Ensure the database file is stored on a **local NTFS SSD** (`%LOCALAPPDATA%\PharmacyApp\data\pharmacy.db`).
2. **Never store the active SQLite database file on a network share (SMB/NFS)** or a synchronizing cloud folder (Dropbox, Google Drive, OneDrive). SQLite WAL locks fail over network shares.
3. To checkpoint the WAL journal manually, restart the daemon or run a hot backup.

---

## 6. Emergency Database Recovery

If a sudden hardware power cut damaged the database:
1. Verify the current database integrity:
   ```cmd
   python -c "import sqlite3; conn = sqlite3.connect('%LOCALAPPDATA%\\PharmacyApp\\data\\pharmacy.db'); print(conn.execute('PRAGMA integrity_check;').fetchall())"
   ```
2. If `integrity_check` reports errors, restore from the latest verified `.pbk` hot backup located in `%LOCALAPPDATA%\PharmacyApp\backups\` using the Disaster Recovery wizard.

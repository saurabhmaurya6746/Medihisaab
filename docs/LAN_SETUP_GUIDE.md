# MediHisaab — Multi-Counter Local Network (LAN) Activation Guide

## 1. Network Topology & Deployment Overview

MediHisaab supports multi-terminal counter billing over a local Wi-Fi or wired Ethernet network:

```
                  +-----------------------------------+
                  |      PRIMARY SERVER MACHINE       |
                  |  Runs: MediHisaab in LAN Mode   |
                  |  Database: %LOCALAPPDATA%\...db   |
                  |  Host IP: 192.168.1.100:38291     |
                  +-----------------+-----------------+
                                    |
          +-------------------------+-------------------------+
          | (Local Ethernet Switch / Store Wi-Fi Router)      |
          +-------------------------+-------------------------+
                                    |
            +-----------------------+-----------------------+
            |                                               |
  +---------+---------+                           +---------+---------+
  | COUNTER TERMINAL 1|                           | COUNTER TERMINAL 2|
  | Any Web Browser   |                           | Any Web Browser   |
  | Opens:            |                           | Opens:            |
  | http://192.168.   |                           | http://192.168.   |
  | 1.100:38291       |                           | 1.100:38291       |
  +-------------------+                           +-------------------+
```

---

## 2. Server Configuration

### Step 1: Set Server to LAN Mode
On the primary server computer:
1. Open MediHisaab and log in as **ADMIN**.
2. Navigate to **LAN Setup & Store Settings (F9)**.
3. In **Operational Mode**, change the dropdown from `STANDALONE` to `LAN_SERVER (Multi-PC Counter LAN - 0.0.0.0)`.
4. Click **Save Settings**.
5. Close and restart the server using:
   ```cmd
   scripts\start-lan-server.bat
   ```
   (or launch via the Start Menu shortcut `MediHisaab (LAN Server Mode)`).

---

## 3. Windows Defender Firewall Configuration

Windows Defender Firewall blocks incoming TCP connections by default on private networks. You must allow inward traffic on port `38291`.

### Exact Firewall Enable Command (Run as Administrator):
Open Windows PowerShell or Command Prompt as Administrator and run:

```cmd
netsh advfirewall firewall add rule name="MediHisaab LAN Server (TCP 38291)" dir=in action=allow protocol=TCP localport=38291 profile=private
```

---

### Exact Firewall Rollback / Removal Command:
To revoke the firewall rule and close the port:

```cmd
netsh advfirewall firewall delete rule name="MediHisaab LAN Server (TCP 38291)"
```

---

## 4. Connecting from Secondary Billing Terminals

1. On the primary server machine, open **LAN Setup (F9)** to view your active local IP addresses (e.g., `192.168.1.100`).
2. On any secondary computer, laptop, or tablet connected to the same Wi-Fi/Ethernet network:
   - Open Google Chrome, Microsoft Edge, or Mozilla Firefox.
   - In the address bar, type:
     ```
     http://192.168.1.100:38291
     ```
     *(Replace `192.168.1.100` with your actual server IP)*.
3. The complete, full-featured MediHisaab application loads instantly.
4. Cashiers log in with their assigned username and password or quick PIN.

> [!NOTE]
> Secondary client terminals do **NOT** require Python, Node.js, or any database drivers installed. They operate completely inside standard modern web browsers.

---

## 5. Concurrency Safety & Multi-Counter Integrity

- **SQLite WAL Mode:** The database operates in Write-Ahead Log (`WAL`) mode with `PRAGMA busy_timeout = 10000;`.
- Multiple terminals can read catalog data and search medicines simultaneously without locking writers.
- When two counters check out sales at the exact same millisecond:
  - Transactions execute sequentially with microsecond locking.
  - Sequential invoice numbers (`INV-YYYYMM-XXXX`) are assigned uniquely without collision.
  - Real-time stock counts update atomically across all terminals.
- **JWT & Role Enforcement:** All requests originating from LAN terminals must transmit valid JWT bearer tokens. Unauthenticated requests are rejected with `HTTP 401 Unauthorized`.

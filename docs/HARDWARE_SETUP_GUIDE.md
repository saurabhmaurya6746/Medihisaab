# MediHisaab — Hardware & Peripherals Setup Guide

## 1. Supported Peripherals Overview

MediHisaab supports standard retail pharmacy hardware:

| Hardware Type | Interface | Standard Protocols / Formats |
| :--- | :--- | :--- |
| **Receipt Printer** | USB / Windows Spooler | 80mm ESC/POS Thermal (48-column format) |
| **Network Printer** | Ethernet / Wi-Fi | Raw TCP Socket on Port 9100 |
| **Laser / Inkjet** | USB / Network Spooler | A4 / A5 Tax Invoice HTML (GST Rule 46 Compliant) |
| **Cash Drawer** | RJ11 Cable to Printer | Standard Pin 2 kick pulse (`\x1bp\x00\x19\xfa`) |
| **Barcode Scanner** | USB / Bluetooth | HID Keyboard Wedge (with CR/LF enter suffix) |

---

## 2. ESC/POS 80mm Thermal Receipt Printers (USB)

### Compatible Models
- Epson TM-T82, TM-T88 series
- TVS RP-3200, RP-3150
- Citizen CT-S310II
- Posiflex Aura series
- Any generic 80mm ESC/POS printer with Windows Generic/Text or Vendor RAW driver

### Setup Procedure
1. Connect the USB printer to the computer and install manufacturer Windows drivers.
2. In Windows **Settings > Bluetooth & devices > Printers & scanners**, ensure the printer is listed and set as default (or take note of its exact Windows printer name).
3. The daemon dispatches raw ESC/POS byte streams directly to the Windows print spooler (`RAW` datatype), bypassing Windows GDI rendering for maximum print speed (<100ms per ticket).

---

## 3. Network Thermal Printers (Ethernet / Wi-Fi)

For billing counters where the printer is connected directly to the store network router via Ethernet:
1. Assign a static IP address to the printer (e.g., `192.168.1.200`).
2. Verify network connectivity from the server:
   ```cmd
   ping 192.168.1.200
   ```
3. In MediHisaab, specify the target as `192.168.1.200:9100`.
4. The daemon sends raw ESC/POS bytes directly over a TCP socket to port 9100 with an automatic 3-second timeout protection.

---

## 4. Cash Drawer (RJ11) Setup

1. Connect the RJ11 cable from the bottom of the cash drawer to the **DK** (Drawer Kick) port on the back of the thermal printer.
2. When a cash sale is checked out or an authorized drawer kick is triggered, the receipt stream automatically sends:
   ```
   ESC p 0 25 250 (\x1bp\x00\x19\xfa)
   ```
3. This sends a 24V 50ms solenoid pulse to pin 2, popping open the cash drawer latch before cutting the receipt paper.

---

## 5. Barcode Scanner Keyboard Wedge

### Configuration
1. Connect any 1D/2D USB or 2.4GHz wireless barcode scanner.
2. No software drivers are required. The scanner registers as an **HID Keyboard Device**.
3. **Important Configuration:** Ensure your barcode scanner is configured to send a carriage return (`[ENTER]`) suffix after each scan (this is the default factory setting for 99% of retail scanners).
4. **Counter Operation:** In the Counter POS screen (**F2**), scanning any medicine barcode auto-populates the medicine, selects the earliest-expiry batch (FEFO), and adds it to the bill instantly.

---

## 6. Offline / Disconnected Hardware Resilience

> [!IMPORTANT]
> **Decoupled Architecture:**
> If a thermal printer runs out of paper, jams, gets unplugged, or network Wi-Fi drops:
> - **The sales transaction is NEVER aborted or rolled back.**
> - The sale invoice is committed safely to the database.
> - The print dispatcher logs a warning, records the generated print stream to the simulation spool log, and displays a non-blocking notification to the cashier:
>   *`"Sale committed safely. Printer offline or spooler unavailable."`*
> - Cashiers can reprint any committed invoice from the Sales Register (**F9 / F2**) once the printer is back online.

---

## 7. Hardware Diagnostics & Simulation Mode

Field technicians can test peripherals at any time using the included diagnostic utility:

### Running from Command Line:
```cmd
scripts\test-hardware.bat --simulate
```
or to test physical hardware:
```cmd
scripts\test-hardware.bat --action all --target "Your_Printer_Name"
```

### Unverified Hardware Disclosure Checklist:
When running in testing or development environments without physical USB printers attached:
- [x] ESC/POS 80mm layout generation: **Verified in software**
- [x] RJ11 drawer pulse byte sequence (`\x1bp\x00\x19\xfa`): **Verified in software**
- [x] A4 Laser invoice HTML generation: **Verified in software**
- [x] Network socket timeout and offline decoupling: **Verified in software**
- [ ] Physical mechanical paper cutter and physical solenoid latch: **Requires physical hardware test on-site during deployment**.

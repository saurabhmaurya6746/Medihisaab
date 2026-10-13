"""Hardware & Printer Validation Diagnostic Utility.

Allows administrators and field technicians to test:
- 80mm USB ESC/POS thermal printers
- Network thermal printers (IP:9100)
- RJ11 Cash drawer kick pulse
- A4/A5 Laser invoice HTML rendering
- Barcode scanner keyboard wedge input
- Offline simulation mode (logs raw hex and ASCII spool output)
"""

import argparse
import os
from pathlib import Path
import sys
import time

# Add daemon source to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DAEMON_SRC = REPO_ROOT / "apps" / "daemon" / "src"
if str(DAEMON_SRC) not in sys.path:
    sys.path.insert(0, str(DAEMON_SRC))

from pharmacy_daemon.printing.service import PrinterService


def list_windows_printers():
    """List installed Windows printers if win32print is available."""
    printers = []
    if sys.platform == "win32":
        try:
            import win32print

            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            for p in win32print.EnumPrinters(flags):
                printers.append(p[2])
        except Exception as e:
            print(f"[WARN] win32print enumeration failed: {e}")
    return printers


def run_diagnostics(args):
    print("=" * 70)
    print(" PHARMACY POS HARDWARE & PRINTER VALIDATION DIAGNOSTIC")
    print("=" * 70)

    printers = list_windows_printers()
    if printers:
        print(f"[INFO] Installed Windows Printers Detected ({len(printers)}):")
        for idx, p in enumerate(printers, 1):
            print(f"   {idx}. {p}")
    else:
        print("[INFO] No local Windows spoolers enumerated (or non-Windows system).")

    service = PrinterService(mock_mode=args.simulate)
    store_info = {
        "store_name": args.store_name,
        "address": "Diagnostic Suite, POS Terminal 1",
        "phone": "+91 00000 00000",
        "gstin": "27TESTG1234F1Z5",
        "dl_number": "DL-20B/21B-TEST",
    }

    print(f"\n[EXEC] Test Target: {args.target or 'Default System Spooler'}")
    print(f"[EXEC] Test Mode: {'SIMULATION' if args.simulate else 'PHYSICAL HARDWARE'}")
    print(f"[EXEC] Action: {args.action.upper()}")

    # 1. Cash Drawer Kick Pulse Test
    if args.action in ("drawer", "all"):
        print("\n--- [TEST 1/3] RJ11 Cash Drawer Pulse Test ---")
        pulse = service.generate_drawer_pulse_bytes()
        service.log_simulation(pulse, "Drawer Kick Pulse")
        print(f"-> Generated {len(pulse)} pulse bytes: {pulse.hex()}")
        print("-> Standard ESC/POS Pin 2 pulse: <ESC> p 0 25 250 (50ms duration)")
        if not args.simulate and sys.platform == "win32" and printers:
            target_p = args.target or printers[0]
            try:
                import win32print

                hprinter = win32print.OpenPrinter(target_p)
                try:
                    hjob = win32print.StartDocPrinter(hprinter, 1, ("DrawerTest", None, "RAW"))
                    win32print.StartPagePrinter(hprinter)
                    win32print.WritePrinter(hprinter, pulse)
                    win32print.EndPagePrinter(hprinter)
                    win32print.EndDocPrinter(hprinter)
                finally:
                    win32print.ClosePrinter(hprinter)
                print(f"[PASS] Pulse dispatched to printer {target_p}.")
            except Exception as ex:
                print(f"[WARN] Direct spool to {target_p} failed: {ex}")
        else:
            print("[SIMULATION] Drawer pulse recorded in spooler_simulation.log.")

    # 2. ESC/POS 80mm Receipt Test
    if args.action in ("thermal", "network", "all"):
        print("\n--- [TEST 2/3] 80mm ESC/POS Receipt Ticket Test ---")
        raw_receipt = service.generate_test_receipt_bytes(store_info)
        print(f"-> Generated {len(raw_receipt)} ESC/POS formatted bytes.")
        print(f"-> Hex sample (first 32 bytes): {raw_receipt[:32].hex()}")

        if args.action == "network" or (args.target and ":" in args.target):
            host, port_str = args.target.split(":", 1) if ":" in args.target else (args.target, "9100")
            print(f"-> Dispatching via raw TCP socket to {host}:{port_str}...")
            res = service.send_network_raw_bytes(host, int(port_str), raw_receipt)
            print(f"[{'PASS' if res.success else 'WARN'}] {res.message}")
        elif args.simulate:
            service.log_simulation(raw_receipt, "Diagnostic 80mm Receipt (Simulated)")
            print("[SIMULATION] 80mm receipt saved to spooler_simulation.log.")
        elif sys.platform == "win32" and printers:
            target_p = args.target or printers[0]
            sample_inv = {"invoice_no": "HW-DIAG-001", "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"), "items": []}
            res = service.print_invoice(sample_inv, printer_type="thermal", printer_name=target_p, store_info=store_info)
            print(f"[{'PASS' if res.success else 'WARN'}] {res.message}")
        else:
            service.log_simulation(raw_receipt, "Diagnostic 80mm Receipt (Headless Fallback)")
            print("[INFO] Non-Windows or no printer attached. Output safely spooled to log.")

    # 3. Laser A4 Tax Invoice Test
    if args.action in ("laser", "all"):
        print("\n--- [TEST 3/3] A4/A5 Laser Tax Invoice Template Test ---")
        sample_inv = {
            "invoice_no": "TEST-A4-001",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "customer_name": "Diagnostic Customer",
            "payment_mode": "CASH",
            "items": [],
            "subtotal_taxable_paise": 50000,
            "total_cgst_paise": 3000,
            "total_sgst_paise": 3000,
            "grand_total_paise": 56000,
        }
        html_doc = service.generate_invoice_html(sample_inv, store_info, page_size="A4")
        print(f"-> Generated {len(html_doc)} HTML characters (GST Rule 46 Compliant).")
        out_html = REPO_ROOT / "test_invoice_sample.html"
        try:
            out_html.write_text(html_doc, encoding="utf-8")
            print(f"[PASS] Sample laser invoice HTML saved to: {out_html}")
        except Exception:
            pass

    # 4. Barcode Scanner Keyboard Wedge Verification Instruction
    print("\n--- [HARDWARE NOTICE] Barcode Scanner Wedge Validation ---")
    print("-> Standard retail USB/Wireless barcode scanners (Honeywell, Zebra, TVS, Datalogic)")
    print("   operate as HID Keyboard Wedge devices.")
    print("-> When scanning a barcode, the scanner types the barcode string followed by [ENTER].")
    print("-> In the Pharmacy POS Counter Billing screen (F2):")
    print("   1. Ensure search input is focused.")
    print("   2. Scan a medicine barcode.")
    print("   3. The POS automatically identifies the batch by barcode and selects FEFO units.")

    local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    log_path = Path(local_app_data) / "PharmacyApp" / "logs" / "spooler_simulation.log"
    print("\n" + "=" * 70)
    print(f"[SUMMARY] Hardware diagnostic completed.")
    if log_path.exists():
        print(f"[LOG] Simulation spool log: {log_path}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Pharmacy POS Hardware & Printer Diagnostic")
    parser.add_argument(
        "--action",
        choices=["thermal", "network", "laser", "drawer", "all"],
        default="all",
        help="Target test type (default: all)",
    )
    parser.add_argument(
        "--target",
        default=None,
        help="Windows printer name or Network IP:PORT (e.g., 192.168.1.200:9100)",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run in simulation mode without sending bytes to physical hardware",
    )
    parser.add_argument(
        "--store-name",
        default="APEX HEALTH PHARMACY",
        help="Store name to render on test tickets",
    )
    args = parser.parse_args()
    run_diagnostics(args)


if __name__ == "__main__":
    main()

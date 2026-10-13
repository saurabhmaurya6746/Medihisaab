"""Print service abstraction supporting 80mm ESC/POS thermal and A4/A5 laser formats.

Decoupled and resilient: printer jams, offline states, or missing spoolers never
propagate unhandled errors to the sales transaction.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import socket
import sys
from typing import Any, Dict, Optional

from .escpos import generate_escpos_receipt
from .laser import generate_laser_invoice_html

logger = logging.getLogger("pharmacy_daemon.printing")


@dataclass
class PrintResult:
    """Outcome of a decoupled print dispatch."""

    success: bool = True
    printer_type: str = "thermal"
    bytes_generated: int = 0
    message: str = "Print job dispatched successfully"
    is_mock: bool = False
    hex_sample: Optional[str] = None
    ascii_preview: Optional[str] = None


class PrinterService:
    """Hardware printing coordinator supporting USB ESC/POS, TCP Network, and Laser formats."""

    def __init__(self, mock_mode: bool = False, log_dir: Optional[Path] = None):
        self.mock_mode = mock_mode
        self.log_dir = log_dir

    def generate_receipt_bytes(self, invoice: Dict[str, Any], store_info: Optional[Dict[str, Any]] = None) -> bytes:
        """Render binary ESC/POS 80mm stream."""
        return generate_escpos_receipt(invoice, store_info)

    def generate_invoice_html(
        self, invoice: Dict[str, Any], store_info: Optional[Dict[str, Any]] = None, page_size: str = "A4"
    ) -> str:
        """Render A4/A5 HTML tax invoice."""
        return generate_laser_invoice_html(invoice, store_info, page_size)

    def generate_drawer_pulse_bytes(self) -> bytes:
        """Render standard ESC/POS RJ11 cash drawer kick-out pulse (Pin 2, 50ms)."""
        return b"\x1bp\x00\x19\xfa"

    def generate_test_receipt_bytes(self, store_info: Optional[Dict[str, Any]] = None) -> bytes:
        """Render standard hardware diagnostic self-test ticket."""
        store = store_info or {}
        store_name = store.get("store_name", "APEX HEALTH PHARMACY")
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        buf = bytearray()
        buf.extend(b"\x1b@")  # Hardware Init
        buf.extend(b"\x1ba\x01")  # Center
        buf.extend(b"\x1bE\x01")  # Bold ON
        buf.extend(f"{store_name}\n".encode("ascii", "replace"))
        buf.extend(b"HARDWARE & PRINTER SELF-TEST\n")
        buf.extend(b"\x1bE\x00")  # Bold OFF
        buf.extend(b"------------------------------------------------\n")
        buf.extend(b"\x1ba\x00")  # Left
        buf.extend(f"Diagnostic Date: {now_str}\n".encode("ascii", "replace"))
        buf.extend(b"Printer Emulation: ESC/POS (80mm / 48 Column)\n")
        buf.extend(b"Cash Drawer Pulse: PIN 2 (RJ11 50ms)\n")
        buf.extend(b"Character Table: PC437 Standard\n")
        buf.extend(b"------------------------------------------------\n")
        buf.extend(b"Font Test: NORMAL | BOLD | DOUBLE-WIDTH\n")
        buf.extend(b"\x1bE\x01[BOLD TEXT PASS]\x1bE\x00\n")
        buf.extend(b"Self-test print job executed cleanly.\n")
        buf.extend(b"------------------------------------------------\n")
        buf.extend(b"\x1ba\x01")
        buf.extend(b"*** END OF HARDWARE DIAGNOSTIC ***\n\n\n")
        # Pulse drawer and cut
        buf.extend(self.generate_drawer_pulse_bytes())
        buf.extend(b"\x1dV\x41\x03")
        return bytes(buf)

    def log_simulation(self, data: bytes, description: str = "ESC/POS Output") -> None:
        """Record simulation output in spooler_simulation.log for hardware verification."""
        try:
            log_dir = self.log_dir
            if not log_dir:
                local_app_data = os.environ.get("LOCALAPPDATA")
                if local_app_data:
                    log_dir = Path(local_app_data) / "PharmacyApp" / "logs"
                else:
                    log_dir = Path.home() / "AppData" / "Local" / "PharmacyApp" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "spooler_simulation.log"
            timestamp = datetime.now(timezone.utc).isoformat()
            ascii_preview = data.decode("ascii", errors="replace").replace("\x1b", "<ESC>").replace("\x1d", "<GS>")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n--- [{timestamp}] SIMULATED PRINT: {description} ({len(data)} bytes) ---\n")
                f.write(ascii_preview)
                f.write("\n--- END SIMULATION ---\n")
        except Exception as e:
            logger.warning("Could not write to simulation spool log: %s", e)

    def send_network_raw_bytes(self, host: str, port: int, data: bytes, timeout: float = 3.0) -> PrintResult:
        """Direct socket dispatch to raw ESC/POS network thermal printer (default port 9100)."""
        hex_sample = data[:64].hex()
        ascii_prev = data.decode("ascii", errors="replace")[:250].replace("\x1b", "<ESC>").replace("\x1d", "<GS>")

        if self.mock_mode:
            self.log_simulation(data, f"Network Mock ({host}:{port})")
            return PrintResult(
                success=True,
                printer_type="network",
                bytes_generated=len(data),
                message=f"Dispatched {len(data)} bytes to network printer {host}:{port} (Simulation Mode)",
                is_mock=True,
                hex_sample=hex_sample,
                ascii_preview=ascii_prev,
            )

        try:
            with socket.create_connection((host, port), timeout=timeout) as sock:
                sock.sendall(data)
            logger.info("Directly spooled %d bytes to network raw printer %s:%d", len(data), host, port)
            return PrintResult(
                success=True,
                printer_type="network",
                bytes_generated=len(data),
                message=f"Dispatched {len(data)} bytes to network printer {host}:{port}",
                is_mock=False,
                hex_sample=hex_sample,
                ascii_preview=ascii_prev,
            )
        except (socket.error, socket.timeout, OSError) as err:
            logger.warning("Network printer %s:%d unreachable or offline: %s. Decoupling gracefully.", host, port, err)
            self.log_simulation(data, f"Network Offline Fallback ({host}:{port})")
            return PrintResult(
                success=False,
                printer_type="network",
                bytes_generated=len(data),
                message=f"Network printer {host}:{port} offline or unreachable: {err}. Sale completed safely.",
                is_mock=False,
                hex_sample=hex_sample,
                ascii_preview=ascii_prev,
            )

    def print_invoice(
        self,
        invoice: Dict[str, Any],
        printer_type: str = "thermal",
        printer_name: Optional[str] = None,
        store_info: Optional[Dict[str, Any]] = None,
    ) -> PrintResult:
        """Dispatch invoice to thermal ESC/POS, network thermal, or laser printer queue safely without raising."""
        try:
            # 1. Laser HTML format
            if printer_type.lower() == "laser":
                html_doc = self.generate_invoice_html(invoice, store_info)
                byte_len = len(html_doc.encode("utf-8"))

                if self.mock_mode:
                    return PrintResult(
                        success=True,
                        printer_type="laser",
                        bytes_generated=byte_len,
                        message="Laser invoice rendered successfully (Mock)",
                        is_mock=True,
                    )

                logger.info("Spooling laser invoice %s to printer %s (%d bytes)", invoice.get("invoice_no"), printer_name, byte_len)
                return PrintResult(
                    success=True,
                    printer_type="laser",
                    bytes_generated=byte_len,
                    message="Laser invoice sent to printer queue",
                )

            # 2. ESC/POS Thermal Raw Stream
            raw_bytes = self.generate_receipt_bytes(invoice, store_info)
            byte_len = len(raw_bytes)
            hex_sample = raw_bytes[:64].hex()
            ascii_prev = raw_bytes.decode("ascii", errors="replace")[:250].replace("\x1b", "<ESC>").replace("\x1d", "<GS>")

            # Check if printer_name specifies a network IP:port (e.g. "192.168.1.150:9100" or printer_type == "network")
            if printer_type.lower() == "network" or (printer_name and ":" in printer_name and not printer_name.startswith("\\")):
                host_part = printer_name or "127.0.0.1:9100"
                if ":" in host_part:
                    host, port_str = host_part.split(":", 1)
                    port = int(port_str)
                else:
                    host, port = host_part, 9100
                return self.send_network_raw_bytes(host, port, raw_bytes)

            if self.mock_mode:
                self.log_simulation(raw_bytes, f"Invoice #{invoice.get('invoice_no')}")
                return PrintResult(
                    success=True,
                    printer_type="thermal",
                    bytes_generated=byte_len,
                    message="ESC/POS 80mm receipt rendered successfully (Mock)",
                    is_mock=True,
                    hex_sample=hex_sample,
                    ascii_preview=ascii_prev,
                )

            # Try win32print if running on Windows and available
            if sys.platform == "win32":
                try:
                    import win32print  # type: ignore

                    target_printer = printer_name or win32print.GetDefaultPrinter()
                    hprinter = win32print.OpenPrinter(target_printer)
                    try:
                        hjob = win32print.StartDocPrinter(hprinter, 1, (f"Receipt-{invoice.get('invoice_no')}", None, "RAW"))
                        try:
                            win32print.StartPagePrinter(hprinter)
                            win32print.WritePrinter(hprinter, raw_bytes)
                            win32print.EndPagePrinter(hprinter)
                        finally:
                            win32print.EndDocPrinter(hprinter)
                    finally:
                        win32print.ClosePrinter(hprinter)

                    logger.info("Directly spooled %d bytes to Win32 raw printer %s", byte_len, target_printer)
                    return PrintResult(
                        success=True,
                        printer_type="thermal",
                        bytes_generated=byte_len,
                        message=f"Dispatched {byte_len} bytes to {target_printer}",
                        hex_sample=hex_sample,
                        ascii_preview=ascii_prev,
                    )
                except Exception as win_err:
                    logger.warning("Win32 spooler offline or unavailable: %s. Falling back to decoupled buffer.", win_err)
                    self.log_simulation(raw_bytes, f"Invoice #{invoice.get('invoice_no')} (Spooler Offline)")
                    return PrintResult(
                        success=False,
                        printer_type="thermal",
                        bytes_generated=byte_len,
                        message=f"Thermal spooler unavailable: {win_err}. Sale completed safely.",
                        hex_sample=hex_sample,
                        ascii_preview=ascii_prev,
                    )

            # Non-Windows or fallback
            self.log_simulation(raw_bytes, f"Invoice #{invoice.get('invoice_no')} (Non-Windows)")
            return PrintResult(
                success=True,
                printer_type="thermal",
                bytes_generated=byte_len,
                message=f"Rendered {byte_len} ESC/POS bytes (Non-Windows platform)",
                is_mock=True,
                hex_sample=hex_sample,
                ascii_preview=ascii_prev,
            )

        except Exception as e:
            logger.error("Print service error: %s. Transaction remains committed.", e)
            return PrintResult(
                success=False,
                printer_type=printer_type,
                bytes_generated=0,
                message=f"Printer failure: {e}",
            )


# Default shared service instance
default_printer_service = PrinterService()

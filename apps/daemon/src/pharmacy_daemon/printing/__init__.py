"""Printing subsystem package for thermal receipts and laser invoices."""

from .service import PrinterService, PrintResult, default_printer_service
from .escpos import generate_escpos_receipt
from .laser import generate_laser_invoice_html

__all__ = [
    "PrinterService",
    "PrintResult",
    "default_printer_service",
    "generate_escpos_receipt",
    "generate_laser_invoice_html",
]

import React, { useCallback, useEffect, useRef, useState } from "react";
import type {
  Customer,
  HeldBill,
  HeldBillItem,
  PaymentAllocationInput,
  SaleCheckoutRequest,
  SaleInvoice,
  SalePaymentMode,
  ScheduleH1Input,
  SubstituteMedicine,
} from "@pharmacy/api-contracts";
import { formatRupees } from "@pharmacy/api-contracts";
import * as salesApi from "../../api/sales";
import * as mastersApi from "../../api/masters";
import { BatchSelectionModal } from "./BatchSelectionModal";
import { SubstituteModal } from "./SubstituteModal";
import { ScheduleH1Modal } from "./ScheduleH1Modal";
import { PaymentModal } from "./PaymentModal";
import { HeldBillsModal } from "./HeldBillsModal";
import { InvoiceReceiptModal } from "./InvoiceReceiptModal";
import { QuickWantBookModal } from "./QuickWantBookModal";
import { QuickCustomerDepositModal } from "./QuickCustomerDepositModal";
import { useSettings } from "../../context/SettingsContext";

interface CartLine {
  tempId: string;
  medicine_id: number;
  medicine_name: string;
  generic_salt: string;
  dosage_form: string;
  pack_size: number;
  is_schedule_h1: boolean;
  gst_rate: number;
  batch_id: number;
  batch_number: string;
  expiry_date: string;
  available_stock_units: number;
  quantity_units: number;
  quantity_input_raw: string; // e.g. "1", "/5", "1/5"
  unit_mrp_paise: number;
  unit_rate_paise: number;
  discount_percent: number;
  discount_amount_paise: number;
  taxable_amount_paise: number;
  cgst_amount_paise: number;
  sgst_amount_paise: number;
  total_amount_paise: number;
  schedule_h1?: ScheduleH1Input | null;
}

const LOCAL_STORAGE_KEY = "pharmacy_pos_active_cart";

export const BillingView: React.FC = () => {
  const { isPreferenceEnabled } = useSettings();
  const allowDiscounts = isPreferenceEnabled("allowDiscounts");
  const barcodeScannerEnabled = isPreferenceEnabled("barcodeScanner");
  const autoPrintReceipt = isPreferenceEnabled("autoPrintReceipt");
  const lowStockAlerts = isPreferenceEnabled("lowStockAlerts");
  const expiryAlerts = isPreferenceEnabled("expiryAlerts");

  // Header / Customer Info
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [doctorName, setDoctorName] = useState<string>("");
  const [notes, setNotes] = useState<string>("");

  // Search Strip State
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [searchResults, setSearchResults] = useState<salesApi.SearchMedicineResult[]>([]);
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [selectedMedIndex, setSelectedMedIndex] = useState<number>(0);
  const [activeMedicine, setActiveMedicine] = useState<salesApi.SearchMedicineResult | null>(null);

  // Active Batch & Qty Entry
  const [activeBatch, setActiveBatch] = useState<salesApi.BatchItemResult | null>(null);
  const [allBatchesForActiveMed, setAllBatchesForActiveMed] = useState<salesApi.BatchItemResult[]>([]);
  const [quantityInput, setQuantityInput] = useState<string>("1");
  const [discountPercentInput, setDiscountPercentInput] = useState<string>("0");
  const [activeScheduleH1, setActiveScheduleH1] = useState<ScheduleH1Input | null>(null);

  // Cart Table State
  const [cartLines, setCartLines] = useState<CartLine[]>([]);
  const [selectedCartLineIndex, setSelectedCartLineIndex] = useState<number>(-1);
  const [invoiceDiscountRupees, setInvoiceDiscountRupees] = useState<string>("0");
  const [roundOffRupees, setRoundOffRupees] = useState<string>("0");

  // Modals
  const [showBatchModal, setShowBatchModal] = useState<boolean>(false);
  const [showSubstituteModal, setShowSubstituteModal] = useState<boolean>(false);
  const [substitutesList, setSubstitutesList] = useState<SubstituteMedicine[]>([]);
  const [showH1Modal, setShowH1Modal] = useState<boolean>(false);
  const [h1ModalTargetIndex, setH1ModalTargetIndex] = useState<number | null>(null);
  const [showPaymentModal, setShowPaymentModal] = useState<boolean>(false);
  const [showHeldBillsModal, setShowHeldBillsModal] = useState<boolean>(false);
  const [heldBillsList, setHeldBillsList] = useState<HeldBill[]>([]);
  const [activeHeldBillId, setActiveHeldBillId] = useState<number | null>(null);
  const [showWantBookModal, setShowWantBookModal] = useState<boolean>(false);
  const [showDepositModal, setShowDepositModal] = useState<boolean>(false);
  const [completedInvoice, setCompletedInvoice] = useState<SaleInvoice | null>(null);
  const [isSubmittingCheckout, setIsSubmittingCheckout] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Refs for keyboard focus progression
  const searchInputRef = useRef<HTMLInputElement>(null);
  const quantityInputRef = useRef<HTMLInputElement>(null);
  const discountInputRef = useRef<HTMLInputElement>(null);

  // Barcode Wedge Timing Detector
  const lastKeyTimeRef = useRef<number>(0);
  const barcodeBufferRef = useRef<string>("");

  // Load Customers on Mount
  useEffect(() => {
    mastersApi
      .listCustomers({ page_size: 100, is_active: true })
      .then((res) => setCustomers(res.items))
      .catch((err) => console.error("Failed to load customers:", err));
  }, []);

  // Rehydrate Cart from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed.cartLines) && parsed.cartLines.length > 0) {
          setCartLines(parsed.cartLines);
          if (parsed.selectedCustomer) setSelectedCustomer(parsed.selectedCustomer);
          if (parsed.doctorName) setDoctorName(parsed.doctorName);
          if (parsed.notes) setNotes(parsed.notes);
        }
      }
    } catch (err) {
      console.warn("Failed to restore cart from localStorage:", err);
    }
  }, []);

  // Persist Cart to localStorage
  useEffect(() => {
    try {
      if (cartLines.length > 0) {
        localStorage.setItem(
          LOCAL_STORAGE_KEY,
          JSON.stringify({
            cartLines,
            selectedCustomer,
            doctorName,
            notes,
          })
        );
      } else {
        localStorage.removeItem(LOCAL_STORAGE_KEY);
      }
    } catch (err) {
      console.warn("Failed to write cart to localStorage:", err);
    }
  }, [cartLines, selectedCustomer, doctorName, notes]);

  // Focus Search automatically on load
  useEffect(() => {
    setTimeout(() => searchInputRef.current?.focus(), 100);
  }, []);

  // ==========================================
  // SEARCH MEDICINES DEBOUNCE & LOOKUP
  // ==========================================
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const results = await salesApi.searchMedicines({ query: searchQuery.trim(), limit: 15 });
        setSearchResults(results);
        setSelectedMedIndex(0);
      } catch (err) {
        console.error("Medicine search failed:", err);
      } finally {
        setIsSearching(false);
      }
    }, 180);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Pick Medicine from Search
  const handleSelectMedicine = useCallback(
    async (med: salesApi.SearchMedicineResult) => {
      setActiveMedicine(med);
      setSearchQuery(med.brand_name);
      setSearchResults([]);

      // Fetch all batches for FEFO selection
      try {
        const batches = await salesApi.listBatchesFEFO({ medicine_id: med.id, include_expired: true, include_out_of_stock: true });
        setAllBatchesForActiveMed(batches);

        // Pick earliest valid available batch (FEFO)
        const fefoBatch = batches.find((b) => b.is_available);
        if (fefoBatch) {
          setActiveBatch(fefoBatch);
        } else if (batches.length > 0) {
          setActiveBatch(batches[0]);
        } else {
          setActiveBatch(null);
        }
      } catch (err) {
        console.error("Failed to load batches:", err);
      }

      // Check if Schedule H1: prepare prompt if needed
      if (med.is_schedule_h1) {
        setActiveScheduleH1({
          patient_name: selectedCustomer?.name || "",
          patient_address: selectedCustomer?.address || "",
          doctor_name: doctorName || selectedCustomer?.default_doctor || "",
          doctor_address: "",
        });
      } else {
        setActiveScheduleH1(null);
      }

      // Progression: Advance focus to Quantity input
      setTimeout(() => {
        quantityInputRef.current?.focus();
        quantityInputRef.current?.select();
      }, 50);
    },
    [selectedCustomer, doctorName]
  );

  // Parse Loose Tablet Quantity Syntax (e.g. "1", "/5", "2/4")
  const parseQuantityInput = useCallback(
    (raw: string, packSize: number): { units: number; label: string } => {
      const clean = raw.trim();
      if (!clean) return { units: 1, label: "1 unit" };

      // Case 1: Loose only, starting with slash e.g. "/5"
      if (clean.startsWith("/")) {
        const loose = parseInt(clean.slice(1), 10) || 1;
        return { units: loose, label: `${loose} loose tab(s)` };
      }

      // Case 2: Full packs + loose e.g. "2/5"
      if (clean.includes("/")) {
        const parts = clean.split("/");
        const packs = parseInt(parts[0], 10) || 0;
        const loose = parseInt(parts[1], 10) || 0;
        const total = packs * packSize + loose;
        return { units: total, label: `${packs} pack(s) + ${loose} loose (${total} tabs)` };
      }

      // Case 3: Plain integer: means full packs if packSize > 1, or loose units
      const num = parseInt(clean, 10) || 1;
      const totalUnits = packSize > 1 ? num * packSize : num;
      const label = packSize > 1 ? `${num} pack(s) (${totalUnits} tabs)` : `${num} unit(s)`;
      return { units: totalUnits, label };
    },
    []
  );

  // Commercial Math for Line Item
  const calculateLineAmounts = (
    units: number,
    unitRatePaise: number,
    _unitMrpPaise: number,
    discountPercent: number,
    gstRate: number
  ) => {
    const grossPaise = units * unitRatePaise;
    const discountAmountPaise = Math.round((grossPaise * discountPercent) / 100);
    const lineTotalPaise = grossPaise - discountAmountPaise;

    let taxablePaise = lineTotalPaise;
    let cgstPaise = 0;
    let sgstPaise = 0;

    if (gstRate > 0) {
      const gstBasisPoints = Math.round(gstRate * 100);
      taxablePaise = Math.round((lineTotalPaise * 10000) / (10000 + gstBasisPoints));
      const totalTaxPaise = lineTotalPaise - taxablePaise;
      cgstPaise = Math.floor(totalTaxPaise / 2);
      sgstPaise = totalTaxPaise - cgstPaise;
    }

    return {
      grossPaise,
      discountAmountPaise,
      lineTotalPaise,
      taxablePaise,
      cgstPaise,
      sgstPaise,
    };
  };

  // Add Item to Cart
  const handleAddLineToCart = () => {
    setErrorMessage(null);
    if (!activeMedicine) {
      setErrorMessage("Please select a medicine first.");
      searchInputRef.current?.focus();
      return;
    }
    if (!activeBatch) {
      setErrorMessage("No batch selected for this medicine.");
      return;
    }
    if (!activeBatch.is_available) {
      setErrorMessage(`Cannot add batch ${activeBatch.batch_number}: batch is expired or out of stock.`);
      return;
    }

    const { units } = parseQuantityInput(quantityInput, activeMedicine.pack_size);
    if (units <= 0) {
      setErrorMessage("Quantity must be greater than zero.");
      return;
    }
    if (units > activeBatch.current_quantity) {
      setErrorMessage(
        `Insufficient stock for batch ${activeBatch.batch_number}. Available: ${activeBatch.current_quantity}, Requested: ${units}.`
      );
      return;
    }

    const discPct = allowDiscounts ? Math.min(100, Math.max(0, parseFloat(discountPercentInput) || 0)) : 0;
    const math = calculateLineAmounts(
      units,
      activeBatch.unit_mrp_paise,
      activeBatch.unit_mrp_paise,
      discPct,
      activeMedicine.gst_rate
    );

    // If Schedule H1 and missing info, prompt modal
    if (activeMedicine.is_schedule_h1) {
      if (!activeScheduleH1 || !activeScheduleH1.patient_name.trim() || !activeScheduleH1.doctor_name.trim()) {
        setShowH1Modal(true);
        return;
      }
    }

    const newLine: CartLine = {
      tempId: Math.random().toString(36).substring(2, 9),
      medicine_id: activeMedicine.id,
      medicine_name: activeMedicine.brand_name,
      generic_salt: activeMedicine.generic_salt,
      dosage_form: activeMedicine.dosage_form,
      pack_size: activeMedicine.pack_size,
      is_schedule_h1: activeMedicine.is_schedule_h1,
      gst_rate: activeMedicine.gst_rate,
      batch_id: activeBatch.id,
      batch_number: activeBatch.batch_number,
      expiry_date: activeBatch.expiry_date,
      available_stock_units: activeBatch.current_quantity,
      quantity_units: units,
      quantity_input_raw: quantityInput,
      unit_mrp_paise: activeBatch.unit_mrp_paise,
      unit_rate_paise: activeBatch.unit_mrp_paise,
      discount_percent: discPct,
      discount_amount_paise: math.discountAmountPaise,
      taxable_amount_paise: math.taxablePaise,
      cgst_amount_paise: math.cgstPaise,
      sgst_amount_paise: math.sgstPaise,
      total_amount_paise: math.lineTotalPaise,
      schedule_h1: activeMedicine.is_schedule_h1 ? activeScheduleH1 : null,
    };

    setCartLines((prev) => [...prev, newLine]);

    // Reset entry strip and focus back on Search Input
    setActiveMedicine(null);
    setActiveBatch(null);
    setSearchQuery("");
    setQuantityInput("1");
    setDiscountPercentInput("0");
    setActiveScheduleH1(null);
    searchInputRef.current?.focus();
  };

  // Remove Line from Cart
  const handleRemoveCartLine = (tempId: string) => {
    setCartLines((prev) => prev.filter((l) => l.tempId !== tempId));
  };

  // Inline Quantity Edit in Cart
  const handleUpdateCartLineQuantity = (index: number, newRaw: string) => {
    setCartLines((prev) => {
      const line = prev[index];
      if (!line) return prev;
      const { units } = parseQuantityInput(newRaw, line.pack_size);
      if (units <= 0) return prev;
      if (units > line.available_stock_units) {
        alert(`Stock limit exceeded. Only ${line.available_stock_units} units available.`);
        return prev;
      }
      const math = calculateLineAmounts(
        units,
        line.unit_rate_paise,
        line.unit_mrp_paise,
        line.discount_percent,
        line.gst_rate
      );
      const updated = {
        ...line,
        quantity_units: units,
        quantity_input_raw: newRaw,
        discount_amount_paise: math.discountAmountPaise,
        taxable_amount_paise: math.taxablePaise,
        cgst_amount_paise: math.cgstPaise,
        sgst_amount_paise: math.sgstPaise,
        total_amount_paise: math.lineTotalPaise,
      };
      const copy = [...prev];
      copy[index] = updated;
      return copy;
    });
  };

  // Totals calculations
  const subtotalTaxablePaise = cartLines.reduce((acc, l) => acc + l.taxable_amount_paise, 0);
  const totalCgstPaise = cartLines.reduce((acc, l) => acc + l.cgst_amount_paise, 0);
  const totalSgstPaise = cartLines.reduce((acc, l) => acc + l.sgst_amount_paise, 0);
  const totalTaxPaise = totalCgstPaise + totalSgstPaise;
  const grossLinesTotalPaise = cartLines.reduce((acc, l) => acc + l.total_amount_paise, 0);

  const invDiscountPaise = allowDiscounts ? Math.round((parseFloat(invoiceDiscountRupees) || 0) * 100) : 0;
  const roundOffPaise = Math.round((parseFloat(roundOffRupees) || 0) * 100);
  const grandTotalPaise = Math.max(0, grossLinesTotalPaise - invDiscountPaise + roundOffPaise);

  // Substitute Search (F3)
  const handleOpenSubstitutes = async () => {
    const med = activeMedicine || (selectedCartLineIndex >= 0 ? cartLines[selectedCartLineIndex] : null);
    if (!med) {
      alert("Select a medicine first to view its generic substitutes [F3].");
      return;
    }
    try {
      const targetMedId = "medicine_id" in med ? (med as CartLine).medicine_id : med.id;
      const subs = await salesApi.findSubstitutes({
        medicine_id: targetMedId,
        generic_salt: med.generic_salt,
        dosage_form: med.dosage_form,
      });
      setSubstitutesList(subs);
      setShowSubstituteModal(true);
    } catch (err) {
      alert("Failed to fetch substitutes.");
    }
  };

  // Switch to Substitute Medicine
  const handleSelectSubstitute = (sub: SubstituteMedicine) => {
    handleSelectMedicine({
      id: sub.id,
      brand_name: sub.brand_name,
      generic_salt: sub.generic_salt,
      dosage_form: sub.dosage_form,
      pack_size: sub.pack_size,
      hsn_code: "3004",
      gst_rate: sub.gst_rate,
      is_schedule_h1: sub.is_schedule_h1,
      total_available_stock: sub.total_stock_units,
    });
  };

  // Park / Hold Bill (Ctrl+H)
  const handleHoldBill = async () => {
    if (cartLines.length === 0) {
      alert("Cart is empty. Nothing to park / hold.");
      return;
    }
    const refPrompt = window.prompt("Enter Hold Reference / Note (e.g. Customer Name):", selectedCustomer?.name || "");
    if (refPrompt === null) return;

    try {
      const heldItems: HeldBillItem[] = cartLines.map((l) => ({
        medicine_id: l.medicine_id,
        medicine_name: l.medicine_name,
        dosage_form: l.dosage_form,
        generic_salt: l.generic_salt,
        is_schedule_h1: l.is_schedule_h1,
        batch_id: l.batch_id,
        batch_number: l.batch_number,
        expiry_date: l.expiry_date,
        pack_size: l.pack_size,
        quantity_units: l.quantity_units,
        unit_mrp_paise: l.unit_mrp_paise,
        unit_rate_paise: l.unit_rate_paise,
        discount_percent: l.discount_percent,
        gst_rate: l.gst_rate,
        total_amount_paise: l.total_amount_paise,
        schedule_h1: l.schedule_h1,
      }));

      await salesApi.holdBill({
        hold_reference: refPrompt.trim() || undefined,
        customer_id: selectedCustomer?.id,
        customer_name: selectedCustomer?.name,
        customer_phone: selectedCustomer?.phone,
        doctor_name: doctorName || undefined,
        notes,
        items: heldItems,
      });

      // Clear active cart and reset
      setCartLines([]);
      setSelectedCustomer(null);
      setDoctorName("");
      setNotes("");
      setActiveHeldBillId(null);
      localStorage.removeItem(LOCAL_STORAGE_KEY);
      searchInputRef.current?.focus();
      alert("Active bill parked into held queue successfully.");
    } catch (err: any) {
      alert(`Failed to hold bill: ${err.message || "Unknown error"}`);
    }
  };

  // Open Recall Modal (Ctrl+R)
  const handleOpenRecall = async () => {
    try {
      const bills = await salesApi.listHeldBills();
      setHeldBillsList(bills);
      setShowHeldBillsModal(true);
    } catch (err) {
      alert("Failed to load held bills.");
    }
  };

  // Recall Bill into Active Cart
  const handleRecallBill = (bill: HeldBill) => {
    const lines: CartLine[] = bill.items.map((it) => {
      const math = calculateLineAmounts(
        it.quantity_units,
        it.unit_rate_paise,
        it.unit_mrp_paise,
        it.discount_percent,
        it.gst_rate
      );
      return {
        tempId: Math.random().toString(36).substring(2, 9),
        medicine_id: it.medicine_id,
        medicine_name: it.medicine_name,
        generic_salt: it.generic_salt || "",
        dosage_form: it.dosage_form,
        pack_size: it.pack_size,
        is_schedule_h1: it.is_schedule_h1,
        gst_rate: it.gst_rate,
        batch_id: it.batch_id,
        batch_number: it.batch_number,
        expiry_date: it.expiry_date,
        available_stock_units: 9999,
        quantity_units: it.quantity_units,
        quantity_input_raw: it.quantity_units.toString(),
        unit_mrp_paise: it.unit_mrp_paise,
        unit_rate_paise: it.unit_rate_paise,
        discount_percent: it.discount_percent,
        discount_amount_paise: math.discountAmountPaise,
        taxable_amount_paise: math.taxablePaise,
        cgst_amount_paise: math.cgstPaise,
        sgst_amount_paise: math.sgstPaise,
        total_amount_paise: math.lineTotalPaise,
        schedule_h1: it.schedule_h1,
      };
    });

    setCartLines(lines);
    if (bill.customer_id) {
      const c = customers.find((cust) => cust.id === bill.customer_id) || null;
      setSelectedCustomer(c);
    } else {
      setSelectedCustomer(null);
    }
    setDoctorName(bill.doctor_name || "");
    setNotes(bill.notes || "");
    setActiveHeldBillId(bill.id);
  };

  const handleDeleteHeldBill = async (id: number) => {
    try {
      await salesApi.deleteHeldBill(id);
      setHeldBillsList((prev) => prev.filter((b) => b.id !== id));
    } catch (err) {
      alert("Failed to delete held bill.");
    }
  };

  // Open Tender / Payment Modal (F9)
  const handleOpenTender = () => {
    setErrorMessage(null);
    if (cartLines.length === 0) {
      setErrorMessage("Cart is empty! Add items before payment [F9].");
      return;
    }

    // Check Schedule H1 compliance on all lines
    const missingH1 = cartLines.find(
      (l) => l.is_schedule_h1 && (!l.schedule_h1 || !l.schedule_h1.patient_name.trim() || !l.schedule_h1.doctor_name.trim())
    );
    if (missingH1) {
      const idx = cartLines.indexOf(missingH1);
      setH1ModalTargetIndex(idx);
      setShowH1Modal(true);
      return;
    }

    setShowPaymentModal(true);
  };

  // Confirm Sale Checkout
  const handleConfirmCheckout = async (paymentDetails: {
    payment_mode: SalePaymentMode;
    payments?: PaymentAllocationInput[];
    cash_tendered_paise: number;
  }) => {
    setIsSubmittingCheckout(true);
    setErrorMessage(null);

    try {
      const payload: SaleCheckoutRequest = {
        customer_id: selectedCustomer?.id,
        customer_name: selectedCustomer?.name,
        customer_phone: selectedCustomer?.phone,
        doctor_name: doctorName || undefined,
        lines: cartLines.map((l) => ({
          medicine_id: l.medicine_id,
          batch_id: l.batch_id,
          quantity_units: l.quantity_units,
          unit_rate_paise: l.unit_rate_paise,
          discount_percent: l.discount_percent,
          schedule_h1: l.schedule_h1,
        })),
        payment_mode: paymentDetails.payment_mode,
        payments: paymentDetails.payments,
        cash_tendered_paise: paymentDetails.cash_tendered_paise,
        discount_paise: invDiscountPaise,
        round_off_paise: roundOffPaise,
        notes: notes || undefined,
        held_bill_id: activeHeldBillId || undefined,
      };

      const committed = await salesApi.checkoutSale(payload);
      setShowPaymentModal(false);
      setCompletedInvoice(committed);

      // Auto-print receipt if preference is enabled
      if (autoPrintReceipt) {
        salesApi.printInvoice(committed.id, { printer_type: "thermal" }).catch(() => {});
      }

      // Clear active cart & localStorage
      setCartLines([]);
      setSelectedCustomer(null);
      setDoctorName("");
      setNotes("");
      setActiveHeldBillId(null);
      localStorage.removeItem(LOCAL_STORAGE_KEY);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to commit sale checkout.");
    } finally {
      setIsSubmittingCheckout(false);
    }
  };

  // Keyboard Shortcuts (Window Level)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if a modal is open
      if (showPaymentModal || showBatchModal || showSubstituteModal || showH1Modal || showHeldBillsModal || showWantBookModal) {
        return;
      }

      if (e.key === "F1") {
        e.preventDefault();
        searchInputRef.current?.focus();
        searchInputRef.current?.select();
      } else if (e.key === "F2") {
        e.preventDefault();
        if (allBatchesForActiveMed.length > 0 || (activeMedicine && allBatchesForActiveMed.length > 0)) {
          setShowBatchModal(true);
        }
      } else if (e.key === "F3") {
        e.preventDefault();
        handleOpenSubstitutes();
      } else if (e.key === "F9") {
        e.preventDefault();
        handleOpenTender();
      } else if (e.ctrlKey && (e.key === "h" || e.key === "H")) {
        e.preventDefault();
        handleHoldBill();
      } else if (e.ctrlKey && (e.key === "r" || e.key === "R")) {
        e.preventDefault();
        handleOpenRecall();
      } else if (e.ctrlKey && (e.key === "w" || e.key === "W")) {
        e.preventDefault();
        setShowWantBookModal(true);
      } else if (e.ctrlKey && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        setShowDepositModal(true);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  });

  return (
    <div className="pos-billing-container" style={{ display: "flex", flexDirection: "column", height: "100%", gap: 10 }}>
      {/* 1. TOP HEADER & CUSTOMER STRIP */}
      <div
        className="pos-panel"
        style={{
          padding: "10px 16px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: "0.92rem", color: "var(--text-main)" }}>Counter 1</div>
          </div>

          {/* Customer Selection */}
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: "0.82rem", color: "var(--text-dim)" }}>Cust:</span>
            <select
              className="pos-input"
              style={{ width: 190, padding: "4px 8px", fontSize: "0.85rem" }}
              value={selectedCustomer?.id || ""}
              onChange={(e) => {
                const c = customers.find((cust) => cust.id === Number(e.target.value)) || null;
                setSelectedCustomer(c);
              }}
            >
              <option value="">Walk-in Customer</option>
              {customers
                .filter((c) => c.is_active)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.phone || "No ph"})
                  </option>
                ))}
            </select>
            {selectedCustomer && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setShowDepositModal(true)}
                title="Customer Khata Deposit (Ctrl+K)"
                style={{ fontSize: "0.76rem", padding: "2px 8px", color: "var(--accent-success)" }}
              >
                Khata: ₹{formatRupees(selectedCustomer.current_balance_paise)}
              </button>
            )}
          </div>

          {/* Doctor Input */}
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: "0.82rem", color: "var(--text-dim)" }}>Dr:</span>
            <input
              type="text"
              className="pos-input"
              style={{ width: 160, padding: "4px 8px", fontSize: "0.85rem" }}
              placeholder="Prescribing Doctor"
              value={doctorName}
              onChange={(e) => setDoctorName(e.target.value)}
            />
          </div>
        </div>

        {/* Hold & Recall Action Buttons */}
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={handleHoldBill}
            title="Hold Current Bill (Ctrl+H)"
          >
            Hold Bill
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={handleOpenRecall}
            title="Recall Held Bill (Ctrl+R)"
          >
            Recall Bill
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => setShowWantBookModal(true)}
            title="Quick Want-Book (Ctrl+W)"
          >
            Want-Book
          </button>
          <button
            type="button"
            className="btn btn-danger btn-sm"
            onClick={() => {
              if (cartLines.length > 0 && window.confirm("Clear active cart?")) {
                setCartLines([]);
                setSelectedCustomer(null);
                setDoctorName("");
                localStorage.removeItem(LOCAL_STORAGE_KEY);
              }
            }}
          >
            Clear
          </button>
        </div>
      </div>

      {/* ERROR ALERT BANNER */}
      {errorMessage && (
        <div className="pos-alert pos-alert-error" style={{ margin: "0 4px", padding: "8px 14px", fontSize: "0.85rem" }}>
          <strong>Error: </strong> {errorMessage}
        </div>
      )}

      {/* 2. FAST ITEM ENTRY STRIP (KEYBOARD WORKFLOW: ITEM -> BATCH -> QTY -> ENTER) */}
      <div
        className="pos-panel"
        style={{
          padding: "10px 16px",
          display: "grid",
          gridTemplateColumns: "2.5fr 1.6fr 1.1fr 0.9fr auto",
          gap: 12,
          alignItems: "end",
          backgroundColor: "var(--bg-secondary, #1e293b)",
          border: "1px solid var(--border-color)",
        }}
      >
        {/* Medicine / Barcode Search Input */}
        <div style={{ position: "relative" }}>
          <label className="pos-label" htmlFor="pos-medicine-search" style={{ display: "flex", justifyContent: "space-between" }}>
            <span>
              Item Search / Barcode Scanner
              {isSearching && <span style={{ color: "var(--accent-primary)", marginLeft: 8, fontSize: "0.75rem" }}>Searching...</span>}
            </span>
          </label>
          <input
            id="pos-medicine-search"
            ref={searchInputRef}
            type="text"
            className="pos-input"
            style={{ fontWeight: 600, fontSize: "0.95rem" }}
            placeholder="Search medicine name, salt, or scan barcode..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              // Barcode scanner wedge character timing accumulation
              if (barcodeScannerEnabled) {
                const now = Date.now();
                if (now - lastKeyTimeRef.current > 100) {
                  barcodeBufferRef.current = "";
                }
                lastKeyTimeRef.current = now;
                if (e.key.length === 1) {
                  barcodeBufferRef.current += e.key;
                }
              }

              if (searchResults.length > 0) {
                if (e.key === "ArrowDown") {
                  e.preventDefault();
                  setSelectedMedIndex((prev) => (prev < searchResults.length - 1 ? prev + 1 : prev));
                } else if (e.key === "ArrowUp") {
                  e.preventDefault();
                  setSelectedMedIndex((prev) => (prev > 0 ? prev - 1 : prev));
                } else if (e.key === "Enter") {
                  e.preventDefault();
                  if (searchResults[selectedMedIndex]) {
                    handleSelectMedicine(searchResults[selectedMedIndex]);
                  }
                }
              } else if (e.key === "Enter" && (searchQuery.trim() || (barcodeScannerEnabled && barcodeBufferRef.current.trim()))) {
                // If barcode scanned, immediately perform exact search
                const codeToSearch = (barcodeScannerEnabled && barcodeBufferRef.current.trim()) ? barcodeBufferRef.current.trim() : searchQuery.trim();
                salesApi.searchMedicines({ barcode: codeToSearch, limit: 1 }).then((res) => {
                  if (res && res.length > 0) {
                    handleSelectMedicine(res[0]);
                  }
                });
              }
            }}
          />

          {/* Autocomplete Dropdown */}
          {searchResults.length > 0 && (
            <div
              className="pos-dropdown"
              style={{
                position: "absolute",
                top: "100%",
                left: 0,
                right: 0,
                zIndex: 90,
                maxHeight: 280,
                overflowY: "auto",
                backgroundColor: "var(--bg-card, #0f172a)",
                border: "1px solid var(--border-color)",
                boxShadow: "0 10px 25px rgba(0,0,0,0.5)",
                borderRadius: 4,
                marginTop: 2,
              }}
            >
              {searchResults.map((med, idx) => (
                <div
                  key={med.id}
                  style={{
                    padding: "8px 12px",
                    cursor: "pointer",
                    backgroundColor: idx === selectedMedIndex ? "var(--bg-active, #334155)" : undefined,
                    borderBottom: "1px solid rgba(255,255,255,0.05)",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                  onClick={() => handleSelectMedicine(med)}
                  onMouseEnter={() => setSelectedMedIndex(idx)}
                >
                  <div>
                    <div style={{ fontWeight: 600, color: "var(--text-title)" }}>
                      {med.brand_name}
                      {med.is_schedule_h1 && (
                        <span className="badge badge-danger" style={{ marginLeft: 6, fontSize: "0.65rem" }}>
                          H1
                        </span>
                      )}
                      {lowStockAlerts && med.total_available_stock > 0 && med.total_available_stock <= 10 && (
                        <span className="badge badge-warning" style={{ marginLeft: 6, fontSize: "0.65rem" }}>
                          Low Stock
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>
                      {med.generic_salt} • {med.dosage_form} ({med.pack_size}s)
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: "0.85rem", fontWeight: 700, color: med.total_available_stock > 0 ? "#10b981" : "#ef4444" }}>
                      {med.total_available_stock} units
                    </div>
                    {med.fefo_batch && (
                      <div style={{ fontSize: "0.72rem", color: "#38bdf8" }}>
                        FEFO: {med.fefo_batch.batch_number} ({formatRupees(med.fefo_batch.unit_mrp_paise)}/u)
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Selected Batch Box */}
        <div>
          <label className="pos-label" style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Batch & Expiry</span>
            <button
              type="button"
              className="btn btn-link btn-xs"
              style={{ padding: 0, color: "#38bdf8", textDecoration: "underline" }}
              onClick={() => {
                if (allBatchesForActiveMed.length > 0) setShowBatchModal(true);
              }}
              disabled={!activeMedicine}
              title="Change batch (F2)"
            >
              Change
            </button>
          </label>
          <div
            style={{
              padding: "6px 10px",
              backgroundColor: "var(--bg-card, #0f172a)",
              border: "1px solid var(--border-color)",
              borderRadius: 4,
              fontSize: "0.85rem",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              minHeight: 38,
            }}
          >
            {activeBatch ? (
              <>
                <div>
                  <strong style={{ fontFamily: "monospace" }}>{activeBatch.batch_number}</strong>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", marginLeft: 6 }}>
                    ({activeBatch.expiry_date})
                  </span>
                  {expiryAlerts && new Date(activeBatch.expiry_date).getTime() - Date.now() < 60 * 24 * 3600 * 1000 && (
                    <span className="badge badge-warning" style={{ marginLeft: 6, fontSize: "0.65rem" }}>
                      Expiring Soon
                    </span>
                  )}
                </div>
                <div style={{ fontSize: "0.78rem", fontWeight: 600, color: "#10b981" }}>
                  {activeBatch.current_quantity} in stock
                </div>
              </>
            ) : (
              <span style={{ color: "var(--text-dim)" }}>No batch selected</span>
            )}
          </div>
        </div>

        {/* Quantity Input (Supports /5 loose syntax) */}
        <div>
          <label className="pos-label" htmlFor="pos-qty-input" style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Qty (Packs or /Loose)</span>
          </label>
          <input
            id="pos-qty-input"
            ref={quantityInputRef}
            type="text"
            className="pos-input"
            style={{ fontWeight: 700, fontSize: "0.95rem" }}
            placeholder="e.g. 1 or /5"
            value={quantityInput}
            onChange={(e) => setQuantityInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleAddLineToCart();
              }
            }}
          />
        </div>

        {/* Discount % Input */}
        <div>
          <label className="pos-label" htmlFor="pos-disc-input">Disc %</label>
          <input
            id="pos-disc-input"
            ref={discountInputRef}
            type="number"
            step="0.5"
            min="0"
            max="100"
            disabled={!allowDiscounts}
            title={!allowDiscounts ? "Discounts disabled in Admin Settings" : undefined}
            className="pos-input"
            value={allowDiscounts ? discountPercentInput : "0"}
            onChange={(e) => setDiscountPercentInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleAddLineToCart();
              }
            }}
          />
        </div>

        {/* Action Buttons */}
        <div style={{ display: "flex", gap: 6 }}>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={handleOpenSubstitutes}
            title="Search Generic Substitutes (F3)"
          >
            Substitutes
          </button>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            style={{ fontWeight: 700 }}
            onClick={handleAddLineToCart}
            title="Add to cart (Enter)"
          >
            + Add
          </button>
        </div>
      </div>

      {/* 3. ACTIVE CART TABLE */}
      <div
        className="pos-panel"
        style={{
          flex: 1,
          overflowY: "auto",
          padding: 0,
          display: "flex",
          flexDirection: "column",
          backgroundColor: "var(--bg-card, #0f172a)",
        }}
      >
        <table className="pos-table" style={{ width: "100%", margin: 0 }}>
          <thead>
            <tr>
              <th style={{ width: 35 }}>#</th>
              <th>Item / Medicine</th>
              <th>Batch</th>
              <th>Expiry</th>
              <th style={{ textAlign: "right", width: 120 }}>Qty (Units)</th>
              <th style={{ textAlign: "right" }}>Pack MRP</th>
              <th style={{ textAlign: "right" }}>Unit Rate</th>
              <th style={{ textAlign: "right", width: 80 }}>Disc%</th>
              <th style={{ textAlign: "right" }}>Taxable</th>
              <th style={{ textAlign: "center", width: 60 }}>GST</th>
              <th style={{ textAlign: "right" }}>Total</th>
              <th style={{ textAlign: "center", width: 60 }}>Del</th>
            </tr>
          </thead>
          <tbody>
            {cartLines.length === 0 ? (
              <tr>
                <td colSpan={12} style={{ textAlign: "center", padding: 48, color: "var(--text-dim)" }}>
                  <div style={{ fontSize: "1.1rem", marginBottom: 6 }}>Cart is empty</div>
                  <div style={{ fontSize: "0.85rem" }}>
                    Scan a barcode or search medicines above to add items.
                  </div>
                </td>
              </tr>
            ) : (
              cartLines.map((line, idx) => (
                <tr
                  key={line.tempId}
                  style={{
                    backgroundColor: idx === selectedCartLineIndex ? "rgba(56, 189, 248, 0.08)" : undefined,
                  }}
                  onClick={() => setSelectedCartLineIndex(idx)}
                >
                  <td style={{ textAlign: "center", color: "var(--text-dim)" }}>{idx + 1}</td>
                  <td>
                    <strong>{line.medicine_name}</strong>
                    {line.is_schedule_h1 && (
                      <span
                        className="badge badge-danger"
                        style={{ marginLeft: 6, fontSize: "0.65rem", cursor: "pointer" }}
                        onClick={() => {
                          setH1ModalTargetIndex(idx);
                          setShowH1Modal(true);
                        }}
                        title="Click to edit Schedule H1 Patient/Doctor details"
                      >
                        H1 {line.schedule_h1 ? "✓" : "!"}
                      </span>
                    )}
                    <div style={{ fontSize: "0.72rem", color: "var(--text-dim)" }}>
                      {line.generic_salt} • {line.dosage_form}
                    </div>
                  </td>
                  <td style={{ fontFamily: "monospace" }}>{line.batch_number}</td>
                  <td>{line.expiry_date}</td>
                  <td style={{ textAlign: "right" }}>
                    <input
                      type="text"
                      className="pos-input"
                      style={{ width: 70, textAlign: "right", padding: "2px 4px", fontSize: "0.82rem" }}
                      value={line.quantity_input_raw}
                      onChange={(e) => handleUpdateCartLineQuantity(idx, e.target.value)}
                    />
                    <div style={{ fontSize: "0.7rem", color: "#38bdf8" }}>{line.quantity_units} u</div>
                  </td>
                  <td style={{ textAlign: "right" }}>{formatRupees(line.unit_mrp_paise * line.pack_size)}</td>
                  <td style={{ textAlign: "right", color: "#38bdf8" }}>{formatRupees(line.unit_rate_paise)}</td>
                  <td style={{ textAlign: "right" }}>{line.discount_percent.toFixed(1)}%</td>
                  <td style={{ textAlign: "right" }}>{formatRupees(line.taxable_amount_paise)}</td>
                  <td style={{ textAlign: "center", fontSize: "0.75rem" }}>{line.gst_rate}%</td>
                  <td style={{ textAlign: "right", fontWeight: 700, color: "#10b981" }}>
                    {formatRupees(line.total_amount_paise)}
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <button
                      type="button"
                      className="btn btn-link btn-xs"
                      style={{ color: "#ef4444" }}
                      onClick={() => handleRemoveCartLine(line.tempId)}
                    >
                      &times;
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* 4. BOTTOM TOTALS, TAX BREAKDOWN & TENDER ACTION */}
      <div
        className="pos-panel"
        style={{
          padding: "12px 20px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 16,
          backgroundColor: "var(--bg-secondary, #0f172a)",
          border: "1px solid var(--border-color)",
        }}
      >
        {/* Tax breakdown summary & Discounts */}
        <div style={{ display: "flex", gap: 16, fontSize: "0.85rem", alignItems: "center", flexWrap: "wrap" }}>
          <div>
            <div style={{ color: "var(--text-dim)" }}>Subtotal (Taxable)</div>
            <strong>{formatRupees(subtotalTaxablePaise)}</strong>
          </div>
          <div>
            <div style={{ color: "var(--text-dim)" }}>CGST</div>
            <strong>{formatRupees(totalCgstPaise)}</strong>
          </div>
          <div>
            <div style={{ color: "var(--text-dim)" }}>SGST</div>
            <strong>{formatRupees(totalSgstPaise)}</strong>
          </div>
          <div>
            <div style={{ color: "var(--text-dim)" }}>Total Tax</div>
            <strong style={{ color: "#38bdf8" }}>{formatRupees(totalTaxPaise)}</strong>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 6, marginLeft: 8 }}>
            <span style={{ color: "var(--text-dim)" }}>Bill Disc (₹):</span>
            <input
              type="number"
              min="0"
              step="1"
              disabled={!allowDiscounts}
              title={!allowDiscounts ? "Discounts disabled in Admin Settings" : undefined}
              className="pos-input"
              style={{ width: 70, padding: "3px 6px", fontSize: "0.85rem", textAlign: "right" }}
              value={allowDiscounts ? invoiceDiscountRupees : "0"}
              onChange={(e) => setInvoiceDiscountRupees(e.target.value)}
            />
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ color: "var(--text-dim)" }}>Round Off (₹):</span>
            <input
              type="number"
              step="0.05"
              className="pos-input"
              style={{ width: 65, padding: "3px 6px", fontSize: "0.85rem", textAlign: "right" }}
              value={roundOffRupees}
              onChange={(e) => setRoundOffRupees(e.target.value)}
            />
          </div>
        </div>

        {/* Invoice Grand Total & Payment Button */}
        <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: "0.75rem", color: "var(--text-dim)" }}>Grand Total</div>
            <div style={{ fontSize: "2rem", fontWeight: 800, color: "var(--accent-success)", lineHeight: 1 }}>
              ₹{formatRupees(grandTotalPaise)}
            </div>
          </div>

          <button
            type="button"
            className="btn btn-success"
            style={{ fontSize: "1rem", padding: "10px 28px", fontWeight: 700 }}
            onClick={handleOpenTender}
            disabled={cartLines.length === 0}
            title="Proceed to payment (F9)"
          >
            Pay & Print
          </button>
        </div>
      </div>

      {/* MODALS */}
      {/* 1. Batch Selection Modal (F2) */}
      <BatchSelectionModal
        isOpen={showBatchModal}
        onClose={() => setShowBatchModal(false)}
        medicineName={activeMedicine?.brand_name || ""}
        batches={allBatchesForActiveMed}
        selectedBatchId={activeBatch?.id}
        onSelectBatch={(batch) => setActiveBatch(batch)}
      />

      {/* 2. Generic Substitutes Modal (F3) */}
      <SubstituteModal
        isOpen={showSubstituteModal}
        onClose={() => setShowSubstituteModal(false)}
        originalMedicineName={activeMedicine?.brand_name || "Medicine"}
        genericSalt={activeMedicine?.generic_salt || ""}
        substitutes={substitutesList}
        onSelectSubstitute={handleSelectSubstitute}
      />

      {/* 3. Schedule H1 Modal */}
      <ScheduleH1Modal
        isOpen={showH1Modal}
        onClose={() => {
          setShowH1Modal(false);
          setH1ModalTargetIndex(null);
        }}
        medicineName={
          h1ModalTargetIndex !== null && cartLines[h1ModalTargetIndex]
            ? cartLines[h1ModalTargetIndex].medicine_name
            : activeMedicine?.brand_name || "Schedule H1 Drug"
        }
        initialData={
          h1ModalTargetIndex !== null && cartLines[h1ModalTargetIndex]
            ? cartLines[h1ModalTargetIndex].schedule_h1
            : activeScheduleH1
        }
        defaultCustomerName={selectedCustomer?.name || ""}
        defaultDoctorName={doctorName || selectedCustomer?.default_doctor || ""}
        onSave={(data) => {
          if (h1ModalTargetIndex !== null) {
            setCartLines((prev) => {
              const copy = [...prev];
              copy[h1ModalTargetIndex] = { ...copy[h1ModalTargetIndex], schedule_h1: data };
              return copy;
            });
          } else {
            setActiveScheduleH1(data);
          }
        }}
      />

      {/* 4. Payment / Tender Modal (F9) */}
      <PaymentModal
        isOpen={showPaymentModal}
        onClose={() => setShowPaymentModal(false)}
        grandTotalPaise={grandTotalPaise}
        selectedCustomer={selectedCustomer}
        customers={customers}
        onSelectCustomer={setSelectedCustomer}
        onConfirmCheckout={handleConfirmCheckout}
        isSubmitting={isSubmittingCheckout}
      />

      {/* 5. Recall Held Bills Modal (Ctrl+R) */}
      <HeldBillsModal
        isOpen={showHeldBillsModal}
        onClose={() => setShowHeldBillsModal(false)}
        heldBills={heldBillsList}
        onRecallBill={handleRecallBill}
        onDeleteBill={handleDeleteHeldBill}
      />

      {/* 6. Completed Invoice Receipt Modal */}
      <InvoiceReceiptModal
        isOpen={completedInvoice !== null}
        onClose={() => setCompletedInvoice(null)}
        invoice={completedInvoice}
        onNewBill={() => {
          setCompletedInvoice(null);
          searchInputRef.current?.focus();
        }}
      />

      {/* 7. Quick Want-Book Modal (Ctrl+W) */}
      <QuickWantBookModal
        isOpen={showWantBookModal}
        onClose={() => setShowWantBookModal(false)}
        initialMedicineId={activeMedicine?.id}
        initialMedicineName={activeMedicine?.brand_name}
      />

      {/* 8. Quick Customer Deposit Modal (Ctrl+K) */}
      <QuickCustomerDepositModal
        isOpen={showDepositModal}
        onClose={() => setShowDepositModal(false)}
        initialCustomer={selectedCustomer}
        onSuccess={() => {
          if (selectedCustomer) {
            mastersApi.getCustomer(selectedCustomer.id).then(setSelectedCustomer).catch(console.error);
          }
        }}
      />
    </div>
  );
};

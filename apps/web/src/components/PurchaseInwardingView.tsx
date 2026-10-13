import React, { useState, useEffect, useCallback, useRef } from "react";
import type {
  PurchaseInvoice,
  PurchaseInvoiceStatus,
  Supplier,
  Medicine,
  SupplierPayableHistoryResponse,
} from "@pharmacy/api-contracts";
import { formatRupees, rupeesToPaise } from "@pharmacy/api-contracts";
import { useAuth } from "../context/AuthContext";
import * as purchasesApi from "../api/purchases";
import * as mastersApi from "../api/masters";
import { PaginationBar } from "./PaginationBar";
import { ConfirmModal } from "./ConfirmModal";

interface FormLineItem {
  tempId: string;
  medicine_id: number;
  medicine_name: string;
  dosage_form?: string;
  batch_number: string;
  expiry_date: string;
  pack_size: number;
  paid_quantity: number;
  free_quantity: number;
  purchase_rate_rupees: string;
  mrp_rupees: string;
  gst_percentage: number;
  discount_rupees: string;
  medicineSearchText: string;
  showMedicineDropdown: boolean;
  medicineOptions: Medicine[];
  highlightedMedIndex: number;
}

export const PurchaseInwardingView: React.FC = () => {
  const { user } = useAuth();
  const canEdit = user?.role === "ADMIN" || user?.role === "PHARMACIST";

  // Mode: "list" or "form"
  const [viewMode, setViewMode] = useState<"list" | "form">("list");

  // ==========================================
  // LIST STATE
  // ==========================================
  const [invoices, setInvoices] = useState<PurchaseInvoice[]>([]);
  const [totalInvoices, setTotalInvoices] = useState<number>(0);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(20);

  // List Filters
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [debouncedSearch, setDebouncedSearch] = useState<string>("");
  const [selectedSupplierFilter, setSelectedSupplierFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [fromDateFilter, setFromDateFilter] = useState<string>("");
  const [toDateFilter, setToDateFilter] = useState<string>("");

  const [isLoadingList, setIsLoadingList] = useState<boolean>(true);
  const [listError, setListError] = useState<string | null>(null);

  // Master Suppliers list (for dropdowns)
  const [suppliersList, setSuppliersList] = useState<Supplier[]>([]);

  // ==========================================
  // FORM / ENTRY STATE
  // ==========================================
  const [editingInvoiceId, setEditingInvoiceId] = useState<number | null>(null);
  const [invoiceStatus, setInvoiceStatus] = useState<PurchaseInvoiceStatus>("DRAFT");
  const [supplierId, setSupplierId] = useState<number | "">("");
  const [supplierInvoiceNumber, setSupplierInvoiceNumber] = useState<string>("");
  const [invoiceDate, setInvoiceDate] = useState<string>(
    new Date().toISOString().split("T")[0]
  );
  const [entryDate, setEntryDate] = useState<string>(
    new Date().toISOString().split("T")[0]
  );
  const [invoiceDiscountRupees, setInvoiceDiscountRupees] = useState<string>("0.00");
  const [notes, setNotes] = useState<string>("");
  const [postedAt, setPostedAt] = useState<string | null>(null);
  const [creatorName, setCreatorName] = useState<string | null>(null);

  const [lines, setLines] = useState<FormLineItem[]>([]);
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isPosting, setIsPosting] = useState<boolean>(false);
  const [formSuccessMessage, setFormSuccessMessage] = useState<string | null>(null);

  // Supplier Payables
  const [supplierPayableData, setSupplierPayableData] = useState<SupplierPayableHistoryResponse | null>(null);
  const [showPayablesLedgerModal, setShowPayablesLedgerModal] = useState<boolean>(false);

  // Confirmation modal for posting
  const [showPostConfirmModal, setShowPostConfirmModal] = useState<boolean>(false);

  // Ref to focus elements
  const supplierSelectRef = useRef<HTMLSelectElement | null>(null);

  // ==========================================
  // INITIAL DATA & SUPPLIER LOOKUP
  // ==========================================
  useEffect(() => {
    const fetchSuppliers = async () => {
      try {
        const resp = await mastersApi.listSuppliers({ is_active: true, page_size: 100 });
        setSuppliersList(resp.items);
      } catch (err) {
        console.error("Failed to load suppliers for filter", err);
      }
    };
    fetchSuppliers();
  }, []);

  // Search debounce
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery.trim());
      setPage(1);
    }, 250);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Load Invoices List
  const loadInvoices = useCallback(async () => {
    setIsLoadingList(true);
    setListError(null);
    try {
      const resp = await purchasesApi.listPurchases({
        query: debouncedSearch || undefined,
        supplier_id: selectedSupplierFilter ? Number(selectedSupplierFilter) : undefined,
        status: (statusFilter as PurchaseInvoiceStatus) || undefined,
        from_date: fromDateFilter || undefined,
        to_date: toDateFilter || undefined,
        page,
        page_size: pageSize,
      });
      setInvoices(resp.items);
      setTotalInvoices(resp.total);
      setTotalPages(resp.total_pages);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load purchases.";
      setListError(msg);
    } finally {
      setIsLoadingList(false);
    }
  }, [debouncedSearch, selectedSupplierFilter, statusFilter, fromDateFilter, toDateFilter, page, pageSize]);

  useEffect(() => {
    if (viewMode === "list") {
      loadInvoices();
    }
  }, [loadInvoices, viewMode]);

  // Load selected supplier's payable history when supplier changes in form
  useEffect(() => {
    if (supplierId && typeof supplierId === "number") {
      purchasesApi
        .getSupplierPayablesHistory(supplierId)
        .then((data) => setSupplierPayableData(data))
        .catch((err) => {
          console.error("Failed to load supplier payables", err);
          setSupplierPayableData(null);
        });
    } else {
      setSupplierPayableData(null);
    }
  }, [supplierId]);

  // ==========================================
  // LINE MANAGEMENT & CALCULATIONS
  // ==========================================
  const createEmptyLine = (): FormLineItem => ({
    tempId: `line_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
    medicine_id: 0,
    medicine_name: "",
    batch_number: "",
    expiry_date: "",
    pack_size: 1,
    paid_quantity: 1,
    free_quantity: 0,
    purchase_rate_rupees: "0.00",
    mrp_rupees: "0.00",
    gst_percentage: 12.0,
    discount_rupees: "0.00",
    medicineSearchText: "",
    showMedicineDropdown: false,
    medicineOptions: [],
    highlightedMedIndex: -1,
  });

  const handleAddLine = () => {
    if (invoiceStatus === "POSTED" || !canEdit) return;
    setLines((prev) => [...prev, createEmptyLine()]);
  };

  const handleRemoveLine = (index: number) => {
    if (invoiceStatus === "POSTED" || !canEdit) return;
    setLines((prev) => prev.filter((_, i) => i !== index));
  };

  const handleLineChange = <K extends keyof FormLineItem>(
    index: number,
    field: K,
    value: FormLineItem[K]
  ) => {
    setLines((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], [field]: value };
      return copy;
    });
  };

  // Medicine Autocomplete Search
  const searchMedicineForLine = async (index: number, query: string) => {
    handleLineChange(index, "medicineSearchText", query);
    if (!query.trim()) {
      handleLineChange(index, "medicineOptions", []);
      handleLineChange(index, "showMedicineDropdown", false);
      return;
    }

    try {
      const resp = await mastersApi.listMedicines({
        query: query.trim(),
        is_active: true,
        page_size: 10,
      });
      handleLineChange(index, "medicineOptions", resp.items);
      handleLineChange(index, "showMedicineDropdown", true);
      handleLineChange(index, "highlightedMedIndex", 0);
    } catch (err) {
      console.error("Medicine search failed", err);
    }
  };

  const selectMedicineForLine = (index: number, med: Medicine) => {
    setLines((prev) => {
      const copy = [...prev];
      copy[index] = {
        ...copy[index],
        medicine_id: med.id,
        medicine_name: med.brand_name,
        dosage_form: med.dosage_form,
        pack_size: med.pack_size || 1,
        gst_percentage: med.gst_rate ?? 12.0,
        medicineSearchText: med.brand_name,
        showMedicineDropdown: false,
        medicineOptions: [],
      };
      return copy;
    });

    // Auto focus batch number input for this row
    setTimeout(() => {
      const batchInput = document.getElementById(`batch_input_${index}`);
      if (batchInput) {
        batchInput.focus();
      }
    }, 50);
  };

  // Pure Integer Calculations for Line & Invoice
  const calculateLineValues = (line: FormLineItem) => {
    const ratePaise = rupeesToPaise(line.purchase_rate_rupees);
    const discPaise = rupeesToPaise(line.discount_rupees);
    const grossPaise = Math.max(0, line.paid_quantity) * Math.max(0, ratePaise);
    const lineDiscountPaise = Math.min(Math.max(0, discPaise), grossPaise);
    const taxablePaise = grossPaise - lineDiscountPaise;
    const gstBp = Math.round((line.gst_percentage || 0) * 100);
    const taxPaise = Math.floor((taxablePaise * gstBp + 5000) / 10000);
    const lineTotalPaise = taxablePaise + taxPaise;
    const totalUnits = (Math.max(0, line.paid_quantity) + Math.max(0, line.free_quantity)) * Math.max(1, line.pack_size);

    return {
      grossPaise,
      lineDiscountPaise,
      taxablePaise,
      taxPaise,
      lineTotalPaise,
      totalUnits,
    };
  };

  // Grand totals across all lines
  const calculatedTotals = lines.reduce(
    (acc, line) => {
      const res = calculateLineValues(line);
      acc.subtotalPaise += res.taxablePaise;
      acc.taxPaise += res.taxPaise;
      acc.totalUnits += res.totalUnits;
      return acc;
    },
    { subtotalPaise: 0, taxPaise: 0, totalUnits: 0 }
  );

  const rawInvDiscountPaise = rupeesToPaise(invoiceDiscountRupees);
  const invDiscountPaise = Math.min(Math.max(0, rawInvDiscountPaise), calculatedTotals.subtotalPaise);
  const grandTotalPaise = calculatedTotals.subtotalPaise + calculatedTotals.taxPaise - invDiscountPaise;

  // ==========================================
  // OPEN FORMS: CREATE, EDIT, VIEW
  // ==========================================
  const handleOpenNewInward = () => {
    if (!canEdit) return;
    setEditingInvoiceId(null);
    setInvoiceStatus("DRAFT");
    setSupplierId("");
    setSupplierInvoiceNumber("");
    setInvoiceDate(new Date().toISOString().split("T")[0]);
    setEntryDate(new Date().toISOString().split("T")[0]);
    setInvoiceDiscountRupees("0.00");
    setNotes("");
    setPostedAt(null);
    setCreatorName(user?.full_name || null);
    setLines([createEmptyLine()]);
    setFormErrors({});
    setFormSuccessMessage(null);
    setViewMode("form");

    setTimeout(() => {
      supplierSelectRef.current?.focus();
    }, 100);
  };

  const handleOpenExistingInvoice = async (invoiceId: number) => {
    setIsLoadingList(true);
    setFormErrors({});
    setFormSuccessMessage(null);
    try {
      const inv = await purchasesApi.getPurchaseInvoice(invoiceId);
      setEditingInvoiceId(inv.id);
      setInvoiceStatus(inv.status);
      setSupplierId(inv.supplier_id);
      setSupplierInvoiceNumber(inv.supplier_invoice_number);
      setInvoiceDate(inv.invoice_date);
      setEntryDate(inv.entry_date);
      setInvoiceDiscountRupees(formatRupees(inv.discount_paise));
      setNotes(inv.notes || "");
      setPostedAt(inv.posted_at || null);
      setCreatorName(inv.creator_name || null);

      if (inv.lines && inv.lines.length > 0) {
        setLines(
          inv.lines.map((l) => ({
            tempId: `line_${l.id}`,
            medicine_id: l.medicine_id,
            medicine_name: l.medicine_name || `Medicine #${l.medicine_id}`,
            dosage_form: l.dosage_form,
            batch_number: l.batch_number,
            expiry_date: l.expiry_date,
            pack_size: l.pack_size,
            paid_quantity: l.paid_quantity,
            free_quantity: l.free_quantity,
            purchase_rate_rupees: formatRupees(l.purchase_rate_paise),
            mrp_rupees: formatRupees(l.mrp_paise),
            gst_percentage: l.gst_percentage,
            discount_rupees: formatRupees(l.discount_paise),
            medicineSearchText: l.medicine_name || "",
            showMedicineDropdown: false,
            medicineOptions: [],
            highlightedMedIndex: -1,
          }))
        );
      } else {
        setLines([createEmptyLine()]);
      }

      setViewMode("form");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load invoice details.";
      setListError(msg);
    } finally {
      setIsLoadingList(false);
    }
  };

  // ==========================================
  // SAVE DRAFT & POST INVOICE
  // ==========================================
  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (!supplierId) {
      errors.supplier = "Supplier is required.";
    }
    if (!supplierInvoiceNumber.trim()) {
      errors.supplierInvoiceNumber = "Supplier Invoice Number is required.";
    }
    if (!invoiceDate) {
      errors.invoiceDate = "Invoice Date is required.";
    }
    if (lines.length === 0) {
      errors.lines = "At least one line item is required.";
    }

    lines.forEach((l, idx) => {
      if (!l.medicine_id) {
        errors[`line_${idx}_med`] = `Line #${idx + 1}: Select a medicine.`;
      }
      if (!l.batch_number.trim()) {
        errors[`line_${idx}_batch`] = `Line #${idx + 1}: Batch number is required.`;
      }
      if (!l.expiry_date.trim()) {
        errors[`line_${idx}_expiry`] = `Line #${idx + 1}: Expiry date required (MM/YY or YYYY-MM-DD).`;
      }
      if (l.paid_quantity + l.free_quantity <= 0) {
        errors[`line_${idx}_qty`] = `Line #${idx + 1}: Paid + Free quantity must be > 0.`;
      }
      const ratePaise = rupeesToPaise(l.purchase_rate_rupees);
      const discPaise = rupeesToPaise(l.discount_rupees);
      const grossPaise = l.paid_quantity * ratePaise;
      if (discPaise > grossPaise) {
        errors[`line_${idx}_disc`] = `Line #${idx + 1}: Discount cannot exceed gross amount.`;
      }
    });

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSaveDraft = async (): Promise<number | null> => {
    if (!canEdit || invoiceStatus === "POSTED") return null;
    if (!validateForm()) return null;

    setIsSaving(true);
    setFormSuccessMessage(null);
    try {
      const payloadLines = lines.map((l) => ({
        medicine_id: l.medicine_id,
        batch_number: l.batch_number.trim().toUpperCase(),
        expiry_date: l.expiry_date.trim(),
        pack_size: Number(l.pack_size) || 1,
        paid_quantity: Number(l.paid_quantity) || 0,
        free_quantity: Number(l.free_quantity) || 0,
        purchase_rate_paise: rupeesToPaise(l.purchase_rate_rupees),
        mrp_paise: rupeesToPaise(l.mrp_rupees),
        discount_paise: rupeesToPaise(l.discount_rupees),
        gst_percentage: Number(l.gst_percentage) || 12.0,
      }));

      const payload = {
        supplier_id: Number(supplierId),
        supplier_invoice_number: supplierInvoiceNumber.trim().toUpperCase(),
        invoice_date: invoiceDate,
        entry_date: entryDate,
        discount_paise: invDiscountPaise,
        notes: notes.trim() || null,
        lines: payloadLines,
      };

      let savedInv: PurchaseInvoice;
      if (editingInvoiceId) {
        savedInv = await purchasesApi.updatePurchaseInvoice(editingInvoiceId, payload);
      } else {
        savedInv = await purchasesApi.createPurchaseInvoice(payload);
        setEditingInvoiceId(savedInv.id);
      }

      setInvoiceStatus(savedInv.status);
      setFormSuccessMessage(`Draft invoice #${savedInv.supplier_invoice_number} saved successfully.`);
      return savedInv.id;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save draft invoice.";
      setFormErrors({ submit: msg });
      return null;
    } finally {
      setIsSaving(false);
    }
  };

  const handleConfirmPost = async () => {
    setShowPostConfirmModal(false);
    if (!canEdit) return;

    let targetId = editingInvoiceId;
    if (!targetId) {
      targetId = await handleSaveDraft();
      if (!targetId) return;
    }

    setIsPosting(true);
    setFormErrors({});
    try {
      const postedInv = await purchasesApi.postPurchaseInvoice(targetId);
      setInvoiceStatus("POSTED");
      setPostedAt(postedInv.posted_at || new Date().toISOString());
      setFormSuccessMessage(
        `Invoice #${postedInv.supplier_invoice_number} posted successfully! Inventory stock updated and supplier balance accrued.`
      );

      // Refresh supplier payables
      if (supplierId && typeof supplierId === "number") {
        const payables = await purchasesApi.getSupplierPayablesHistory(supplierId);
        setSupplierPayableData(payables);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to post invoice.";
      setFormErrors({ submit: msg });
    } finally {
      setIsPosting(false);
    }
  };

  // ==========================================
  // KEYBOARD SHORTCUTS IN VIEW
  // ==========================================
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // List Mode: Alt+N opens new bill
      if (viewMode === "list") {
        if (e.altKey && (e.key === "n" || e.key === "N") && canEdit) {
          e.preventDefault();
          handleOpenNewInward();
        }
        return;
      }

      // Form Mode Shortcuts
      if (viewMode === "form") {
        // Escape returns to list (if not inside confirm modal)
        if (e.key === "Escape" && !showPostConfirmModal && !showPayablesLedgerModal) {
          e.preventDefault();
          setViewMode("list");
          loadInvoices();
          return;
        }

        // Alt+A or Insert adds a new line
        if ((e.altKey && (e.key === "a" || e.key === "A")) || e.key === "Insert") {
          if (canEdit && invoiceStatus !== "POSTED") {
            e.preventDefault();
            handleAddLine();
          }
        }

        // Ctrl+S saves draft
        if ((e.ctrlKey || e.metaKey) && (e.key === "s" || e.key === "S")) {
          e.preventDefault();
          handleSaveDraft();
        }

        // Ctrl+P opens post confirmation modal
        if ((e.ctrlKey || e.metaKey) && (e.key === "p" || e.key === "P")) {
          e.preventDefault();
          if (canEdit && invoiceStatus !== "POSTED") {
            setShowPostConfirmModal(true);
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    viewMode,
    canEdit,
    invoiceStatus,
    showPostConfirmModal,
    showPayablesLedgerModal,
    loadInvoices,
  ]);

  // Selected supplier object
  const currentSupplierObj = suppliersList.find((s) => s.id === Number(supplierId));

  // ============================================================================
  // RENDER: LIST VIEW
  // ============================================================================
  if (viewMode === "list") {
    return (
      <div className="master-view-container">
        {/* 1. Toolbar & Filters */}
        <div className="master-toolbar">
          <div className="toolbar-left">
            <div className="search-input-wrapper">
              <svg
                className="search-icon-left"
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                type="text"
                className="form-input"
                placeholder="Search invoice number or supplier..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                autoFocus
              />
              {searchQuery && (
                <button
                  type="button"
                  className="search-clear-btn"
                  onClick={() => setSearchQuery("")}
                  title="Clear Search"
                >
                  ✕
                </button>
              )}
            </div>

            {/* Supplier Filter */}
            <select
              className="select-filter"
              value={selectedSupplierFilter}
              onChange={(e) => {
                setSelectedSupplierFilter(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All Suppliers</option>
              {suppliersList.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>

            {/* Status Filter */}
            <select
              className="select-filter"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All Statuses</option>
              <option value="DRAFT">DRAFT</option>
              <option value="POSTED">POSTED</option>
              <option value="CANCELLED">CANCELLED</option>
            </select>

            {/* Date Filters */}
            <input
              type="date"
              className="select-filter"
              title="From Invoice Date"
              value={fromDateFilter}
              onChange={(e) => {
                setFromDateFilter(e.target.value);
                setPage(1);
              }}
            />
            <input
              type="date"
              className="select-filter"
              title="To Invoice Date"
              value={toDateFilter}
              onChange={(e) => {
                setToDateFilter(e.target.value);
                setPage(1);
              }}
            />
          </div>

          <div className="toolbar-right">
            {canEdit && (
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleOpenNewInward}
                title="New Purchase Bill (Alt+N)"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                <span>New Purchase Bill</span>
              </button>
            )}
          </div>
        </div>

        {/* 2. Error Message */}
        {listError && (
          <div className="auth-error-banner">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span>{listError}</span>
          </div>
        )}

        {/* 3. Invoices Table */}
        <div className="data-table-card">
          <div className="data-table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Invoice Number</th>
                  <th>Supplier</th>
                  <th>Invoice Date</th>
                  <th>Entry Date</th>
                  <th>Status</th>
                  <th>Payment</th>
                  <th style={{ textAlign: "right" }}>Grand Total (₹)</th>
                  <th style={{ textAlign: "center" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {isLoadingList ? (
                  <tr>
                    <td colSpan={8}>
                      <div className="table-loading-overlay">
                        <span>Loading purchases...</span>
                      </div>
                    </td>
                  </tr>
                ) : invoices.length === 0 ? (
                  <tr>
                    <td colSpan={8}>
                      <div className="table-empty-state">
                        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <rect x="2" y="4" width="20" height="16" rx="2" />
                          <path d="M7 15h0M2 9.5h20" />
                        </svg>
                        <p style={{ fontWeight: 600 }}>No purchase invoices found</p>
                        <span style={{ fontSize: "0.8rem", color: "var(--text-dim)" }}>
                          Create a new purchase bill to add stock.
                        </span>
                      </div>
                    </td>
                  </tr>
                ) : (
                  invoices.map((inv) => (
                    <tr key={inv.id}>
                      <td className="col-code">
                        <strong>{inv.supplier_invoice_number}</strong>
                        {inv.creator_name && (
                          <div className="col-subtext">By {inv.creator_name}</div>
                        )}
                      </td>
                      <td className="col-name">{inv.supplier_name || `Supplier #${inv.supplier_id}`}</td>
                      <td>{inv.invoice_date}</td>
                      <td style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>{inv.entry_date}</td>
                      <td>
                        <span
                          className={`pill-badge ${
                            inv.status === "POSTED"
                              ? "pill-posted"
                              : inv.status === "DRAFT"
                              ? "pill-draft"
                              : "pill-cancelled"
                          }`}
                        >
                          {inv.status}
                        </span>
                      </td>
                      <td>
                        <span
                          className={`pill-badge ${
                            inv.payment_status === "PAID"
                              ? "pill-paid"
                              : inv.payment_status === "PARTIAL"
                              ? "pill-partial"
                              : "pill-unpaid"
                          }`}
                        >
                          {inv.payment_status}
                        </span>
                      </td>
                      <td className="col-amount" style={{ fontSize: "0.95rem", color: "#38bdf8" }}>
                        ₹{formatRupees(inv.grand_total_paise)}
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <div style={{ display: "inline-flex", gap: "6px" }}>
                          {inv.status === "DRAFT" && canEdit ? (
                            <button
                              type="button"
                              className="btn btn-secondary btn-sm"
                              onClick={() => handleOpenExistingInvoice(inv.id)}
                              title="Edit Draft"
                            >
                              Edit
                            </button>
                          ) : (
                            <button
                              type="button"
                              className="btn btn-ghost btn-sm"
                              onClick={() => handleOpenExistingInvoice(inv.id)}
                              title="View Details"
                            >
                              View
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* 4. Pagination */}
          <PaginationBar
            page={page}
            totalPages={totalPages}
            total={totalInvoices}
            pageSize={pageSize}
            onPageChange={setPage}
            onPageSizeChange={(newSize) => {
              setPageSize(newSize);
              setPage(1);
            }}
          />
        </div>
      </div>
    );
  }

  // ============================================================================
  // RENDER: FORM / ENTRY VIEW
  // ============================================================================
  const isReadOnly = invoiceStatus === "POSTED" || !canEdit;

  return (
    <div className="purchase-entry-container">
      {/* 1. Header Toolbar */}
      <div className="master-toolbar">
        <div className="toolbar-left">
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => {
              setViewMode("list");
              loadInvoices();
            }}
            title="Back to Invoices (Esc)"
          >
            ← Back
          </button>

          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <h2 style={{ fontSize: "1.1rem", fontWeight: 700, color: "#ffffff" }}>
              {editingInvoiceId
                ? `Purchase Invoice #${supplierInvoiceNumber || editingInvoiceId}`
                : "New Purchase Invoice"}
            </h2>
            <span
              className={`pill-badge ${
                invoiceStatus === "POSTED"
                  ? "pill-posted"
                  : invoiceStatus === "DRAFT"
                  ? "pill-draft"
                  : "pill-cancelled"
              }`}
            >
              {invoiceStatus}
            </span>
            {creatorName && (
              <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                Operator: {creatorName}
              </span>
            )}
            {postedAt && (
              <span style={{ fontSize: "0.78rem", color: "#34d399", fontFamily: "var(--font-mono)" }}>
                • Posted: {postedAt.slice(0, 10)}
              </span>
            )}
          </div>
        </div>

        <div className="toolbar-right">
          {!isReadOnly && (
            <>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => handleSaveDraft()}
                disabled={isSaving}
                title="Save Draft (Ctrl+S)"
              >
                {isSaving ? "Saving..." : "Save Draft"}
              </button>

              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => setShowPostConfirmModal(true)}
                disabled={isPosting || isSaving}
                title="Post to Stock & Ledger (Ctrl+P)"
              >
                {isPosting ? "Posting..." : "Post Bill"}
              </button>
            </>
          )}

          {invoiceStatus === "POSTED" && (
            <span style={{ fontSize: "0.8rem", color: "#34d399", fontWeight: 600 }}>
              ✓ Invoice Posted & Stock Added
            </span>
          )}
        </div>
      </div>

      {/* Success Banner */}
      {formSuccessMessage && (
        <div className="auth-success-banner" style={{ margin: "0 0 8px 0" }}>
          {formSuccessMessage}
        </div>
      )}

      {/* Error Banner */}
      {formErrors.submit && (
        <div className="auth-error-banner" style={{ margin: "0 0 8px 0" }}>
          {formErrors.submit}
        </div>
      )}

      {/* 2. Invoice Metadata Card */}
      <div className="purchase-header-card">
        <div className="purchase-meta-grid">
          {/* Supplier */}
          <div>
            <label className="form-label">
              Supplier <span style={{ color: "#ef4444" }}>*</span>
            </label>
            <select
              ref={supplierSelectRef}
              className={`form-input ${formErrors.supplier ? "has-error" : ""}`}
              value={supplierId}
              disabled={isReadOnly}
              onChange={(e) => {
                setSupplierId(e.target.value ? Number(e.target.value) : "");
                setFormErrors((prev) => ({ ...prev, supplier: "" }));
              }}
            >
              <option value="">-- Select Supplier --</option>
              {suppliersList.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} {s.gstin ? `(${s.gstin})` : ""}
                </option>
              ))}
            </select>
            {formErrors.supplier && (
              <span className="field-error-text">{formErrors.supplier}</span>
            )}
          </div>

          {/* Supplier Invoice # */}
          <div>
            <label className="form-label">
              Supplier Invoice # <span style={{ color: "#ef4444" }}>*</span>
            </label>
            <input
              type="text"
              className={`form-input ${formErrors.supplierInvoiceNumber ? "has-error" : ""}`}
              placeholder="e.g. INV-9042"
              value={supplierInvoiceNumber}
              disabled={isReadOnly}
              onChange={(e) => {
                setSupplierInvoiceNumber(e.target.value.toUpperCase());
                setFormErrors((prev) => ({ ...prev, supplierInvoiceNumber: "" }));
              }}
            />
            {formErrors.supplierInvoiceNumber && (
              <span className="field-error-text">{formErrors.supplierInvoiceNumber}</span>
            )}
          </div>

          {/* Invoice Date */}
          <div>
            <label className="form-label">
              Invoice Date <span style={{ color: "#ef4444" }}>*</span>
            </label>
            <input
              type="date"
              className={`form-input ${formErrors.invoiceDate ? "has-error" : ""}`}
              value={invoiceDate}
              disabled={isReadOnly}
              onChange={(e) => {
                setInvoiceDate(e.target.value);
                setFormErrors((prev) => ({ ...prev, invoiceDate: "" }));
              }}
            />
            {formErrors.invoiceDate && (
              <span className="field-error-text">{formErrors.invoiceDate}</span>
            )}
          </div>

          {/* Notes */}
          <div>
            <label className="form-label">Notes / Remarks</label>
            <input
              type="text"
              className="form-input"
              placeholder="Optional remarks..."
              value={notes}
              disabled={isReadOnly}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
        </div>

        {/* Selected Supplier Payables Banner */}
        {supplierPayableData && (
          <div className="payable-summary-banner">
            <div className="payable-stat-group">
              <div className="payable-stat">
                <span className="payable-stat-label">Supplier</span>
                <span style={{ fontWeight: 700, color: "#ffffff" }}>
                  {supplierPayableData.supplier_name}
                </span>
              </div>
              <div className="payable-stat">
                <span className="payable-stat-label">Current Outstanding Payable</span>
                <span className="payable-stat-value">
                  ₹{formatRupees(supplierPayableData.current_payable_paise)}
                </span>
              </div>
              {currentSupplierObj?.credit_days !== undefined && (
                <div className="payable-stat">
                  <span className="payable-stat-label">Credit Terms</span>
                  <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-main)" }}>
                    {currentSupplierObj.credit_days} Days
                  </span>
                </div>
              )}
            </div>

            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setShowPayablesLedgerModal(true)}
            >
              View Recent Ledger ({supplierPayableData.entries.length})
            </button>
          </div>
        )}
      </div>

      {/* 3. Keyboard-Driven Line-Entry Grid */}
      <div className="purchase-grid-wrapper">
        <div className="purchase-grid-scroll">
          <table className="purchase-grid-table">
            <thead>
              <tr>
                <th style={{ width: "32px", textAlign: "center" }}>#</th>
                <th style={{ minWidth: "240px" }}>Medicine Name *</th>
                <th style={{ width: "110px" }}>Batch No *</th>
                <th style={{ width: "95px" }}>Expiry *</th>
                <th style={{ width: "70px" }} className="text-right">Pack</th>
                <th style={{ width: "80px" }} className="text-right">Paid Qty</th>
                <th style={{ width: "80px" }} className="text-right">Free Qty</th>
                <th style={{ width: "95px" }} className="text-right">PTR/Rate (₹)</th>
                <th style={{ width: "95px" }} className="text-right">MRP (₹)</th>
                <th style={{ width: "75px" }} className="text-center">GST %</th>
                <th style={{ width: "85px" }} className="text-right">Disc (₹)</th>
                <th style={{ width: "85px" }} className="text-right">Total Units</th>
                <th style={{ width: "105px" }} className="text-right">Line Total (₹)</th>
                {!isReadOnly && <th style={{ width: "45px", textAlign: "center" }}>✕</th>}
              </tr>
            </thead>
            <tbody>
              {lines.map((line, idx) => {
                const calcs = calculateLineValues(line);
                const hasMedError = !!formErrors[`line_${idx}_med`];
                const hasBatchError = !!formErrors[`line_${idx}_batch`];
                const hasExpError = !!formErrors[`line_${idx}_expiry`];
                const hasQtyError = !!formErrors[`line_${idx}_qty`];
                const hasDiscError = !!formErrors[`line_${idx}_disc`];

                return (
                  <tr key={line.tempId}>
                    {/* Line Index */}
                    <td style={{ textAlign: "center", color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                      {idx + 1}
                    </td>

                    {/* Medicine Autocomplete */}
                    <td className="medicine-search-cell">
                      <input
                        type="text"
                        className={`grid-cell-input ${hasMedError ? "has-error" : ""}`}
                        placeholder="Search brand or salt..."
                        value={line.medicineSearchText}
                        disabled={isReadOnly}
                        onChange={(e) => searchMedicineForLine(idx, e.target.value)}
                        onFocus={() => {
                          if (line.medicineOptions.length > 0) {
                            handleLineChange(idx, "showMedicineDropdown", true);
                          }
                        }}
                        onBlur={() => {
                          // Slight delay to allow clicking dropdown item
                          setTimeout(() => {
                            handleLineChange(idx, "showMedicineDropdown", false);
                          }, 200);
                        }}
                      />
                      {line.showMedicineDropdown && line.medicineOptions.length > 0 && (
                        <div className="medicine-autocomplete-dropdown">
                          {line.medicineOptions.map((med, medIdx) => (
                            <div
                              key={med.id}
                              className={`medicine-dropdown-item ${
                                line.highlightedMedIndex === medIdx ? "active" : ""
                              }`}
                              onMouseDown={() => selectMedicineForLine(idx, med)}
                            >
                              <span className="medicine-dropdown-brand">{med.brand_name}</span>
                              <span className="medicine-dropdown-meta">
                                {med.generic_salt} • Pack of {med.pack_size} • GST {med.gst_rate}%
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                      {hasMedError && <span className="field-error-text">{formErrors[`line_${idx}_med`]}</span>}
                    </td>

                    {/* Batch Number */}
                    <td>
                      <input
                        id={`batch_input_${idx}`}
                        type="text"
                        className={`grid-cell-input ${hasBatchError ? "has-error" : ""}`}
                        placeholder="BATCH"
                        value={line.batch_number}
                        disabled={isReadOnly}
                        onChange={(e) => handleLineChange(idx, "batch_number", e.target.value.toUpperCase())}
                      />
                      {hasBatchError && <span className="field-error-text">{formErrors[`line_${idx}_batch`]}</span>}
                    </td>

                    {/* Expiry Date */}
                    <td>
                      <input
                        type="text"
                        className={`grid-cell-input ${hasExpError ? "has-error" : ""}`}
                        placeholder="MM/YY"
                        value={line.expiry_date}
                        disabled={isReadOnly}
                        onChange={(e) => handleLineChange(idx, "expiry_date", e.target.value)}
                      />
                      {hasExpError && <span className="field-error-text">{formErrors[`line_${idx}_expiry`]}</span>}
                    </td>

                    {/* Pack Size */}
                    <td>
                      <input
                        type="number"
                        min="1"
                        className="grid-cell-input num-input"
                        value={line.pack_size}
                        disabled={isReadOnly}
                        onChange={(e) => handleLineChange(idx, "pack_size", Math.max(1, parseInt(e.target.value) || 1))}
                      />
                    </td>

                    {/* Paid Quantity */}
                    <td>
                      <input
                        type="number"
                        min="0"
                        className={`grid-cell-input num-input ${hasQtyError ? "has-error" : ""}`}
                        value={line.paid_quantity}
                        disabled={isReadOnly}
                        onChange={(e) =>
                          handleLineChange(idx, "paid_quantity", Math.max(0, parseInt(e.target.value) || 0))
                        }
                      />
                      {hasQtyError && <span className="field-error-text">{formErrors[`line_${idx}_qty`]}</span>}
                    </td>

                    {/* Free Quantity (e.g. 10 + 1 free scheme) */}
                    <td>
                      <input
                        type="number"
                        min="0"
                        className="grid-cell-input num-input"
                        title="Free scheme bonus packs (e.g. 1 in a 10+1 scheme)"
                        value={line.free_quantity}
                        disabled={isReadOnly}
                        onChange={(e) =>
                          handleLineChange(idx, "free_quantity", Math.max(0, parseInt(e.target.value) || 0))
                        }
                      />
                    </td>

                    {/* Purchase Rate (PTR) */}
                    <td>
                      <input
                        type="text"
                        className="grid-cell-input num-input"
                        value={line.purchase_rate_rupees}
                        disabled={isReadOnly}
                        onChange={(e) => handleLineChange(idx, "purchase_rate_rupees", e.target.value)}
                      />
                    </td>

                    {/* MRP */}
                    <td>
                      <input
                        type="text"
                        className="grid-cell-input num-input"
                        value={line.mrp_rupees}
                        disabled={isReadOnly}
                        onChange={(e) => handleLineChange(idx, "mrp_rupees", e.target.value)}
                      />
                    </td>

                    {/* GST % */}
                    <td>
                      <select
                        className="grid-cell-input"
                        style={{ textAlign: "center" }}
                        value={line.gst_percentage}
                        disabled={isReadOnly}
                        onChange={(e) => handleLineChange(idx, "gst_percentage", Number(e.target.value) || 0)}
                      >
                        <option value={0}>0%</option>
                        <option value={5}>5%</option>
                        <option value={12}>12%</option>
                        <option value={18}>18%</option>
                        <option value={28}>28%</option>
                      </select>
                    </td>

                    {/* Line Discount */}
                    <td>
                      <input
                        type="text"
                        className={`grid-cell-input num-input ${hasDiscError ? "has-error" : ""}`}
                        value={line.discount_rupees}
                        disabled={isReadOnly}
                        onChange={(e) => handleLineChange(idx, "discount_rupees", e.target.value)}
                      />
                      {hasDiscError && <span className="field-error-text">{formErrors[`line_${idx}_disc`]}</span>}
                    </td>

                    {/* Calculated Total Units */}
                    <td className="text-right" style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>
                      {calcs.totalUnits}
                    </td>

                    {/* Calculated Line Total */}
                    <td
                      className="text-right"
                      style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: "#38bdf8" }}
                    >
                      ₹{formatRupees(calcs.lineTotalPaise)}
                    </td>

                    {/* Delete Line */}
                    {!isReadOnly && (
                      <td style={{ textAlign: "center" }}>
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          style={{ padding: "2px 6px", color: "var(--text-muted)" }}
                          onClick={() => handleRemoveLine(idx)}
                          title="Remove Line"
                        >
                          ✕
                        </button>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Action bar for adding lines */}
        {!isReadOnly && (
          <div style={{ padding: "8px 12px", borderTop: "1px solid var(--border-subtle)" }}>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={handleAddLine}
              title="Add Line Item (Alt+A or Insert)"
            >
              + Add Line Item
            </button>
          </div>
        )}
      </div>

      {/* 4. Bottom Summary Bar */}
      <div className="purchase-footer-summary">
        <div className="summary-stats-left">
          <span>Items: <strong>{lines.length}</strong></span>
          <span>•</span>
          <span>Total Units: <strong>{calculatedTotals.totalUnits}</strong></span>
        </div>

        <div className="summary-figures-right">
          <div className="figure-block">
            <span className="figure-label">Subtotal</span>
            <span className="figure-value">₹{formatRupees(calculatedTotals.subtotalPaise)}</span>
          </div>

          <div className="figure-block">
            <span className="figure-label">Inv Discount (₹)</span>
            <input
              type="text"
              className="grid-cell-input num-input"
              style={{ width: "100px", padding: "4px 8px" }}
              value={invoiceDiscountRupees}
              disabled={isReadOnly}
              onChange={(e) => setInvoiceDiscountRupees(e.target.value)}
            />
          </div>

          <div className="figure-block">
            <span className="figure-label">Tax (GST)</span>
            <span className="figure-value">₹{formatRupees(calculatedTotals.taxPaise)}</span>
          </div>

          <div className="figure-block">
            <span className="figure-label">Grand Total</span>
            <span className="figure-value grand-total">₹{formatRupees(grandTotalPaise)}</span>
          </div>
        </div>
      </div>

      {/* 5. Post Confirmation Modal */}
      <ConfirmModal
        isOpen={showPostConfirmModal}
        title="Confirm Purchase Posting"
        message={`Are you sure you want to finalize and post Purchase Bill #${
          supplierInvoiceNumber || "DRAFT"
        }? This will permanently add ${calculatedTotals.totalUnits} units into inventory and update ${currentSupplierObj?.name || "the supplier"}'s balance.`}
        confirmLabel="Post Invoice"
        confirmVariant="primary"
        isLoading={isPosting}
        onConfirm={handleConfirmPost}
        onCancel={() => setShowPostConfirmModal(false)}
      />

      {/* 6. Supplier Payables Ledger History Modal */}
      {showPayablesLedgerModal && supplierPayableData && (
        <div className="modal-backdrop" onClick={() => setShowPayablesLedgerModal(false)}>
          <div className="modal-dialog supplier-payables-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title">
                <span>Supplier Ledger: {supplierPayableData.supplier_name}</span>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={() => setShowPayablesLedgerModal(false)}>
                ✕
              </button>
            </div>

            <div className="modal-body">
              <div style={{ marginBottom: "16px", display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
                  Current Outstanding Payable:
                </span>
                <span style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: "#38bdf8", fontSize: "1.1rem" }}>
                  ₹{formatRupees(supplierPayableData.current_payable_paise)}
                </span>
              </div>

              <div style={{ maxHeight: "300px", overflowY: "auto", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)" }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Ref Type</th>
                      <th>Entry</th>
                      <th style={{ textAlign: "right" }}>Amount (₹)</th>
                      <th style={{ textAlign: "right" }}>Balance (₹)</th>
                      <th>Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {supplierPayableData.entries.length === 0 ? (
                      <tr>
                        <td colSpan={6} style={{ textAlign: "center", color: "var(--text-muted)", padding: "24px" }}>
                          No transactions recorded yet.
                        </td>
                      </tr>
                    ) : (
                      supplierPayableData.entries.map((entry) => (
                        <tr key={entry.id}>
                          <td style={{ fontSize: "0.78rem" }}>{entry.created_at.slice(0, 10)}</td>
                          <td>{entry.reference_type}</td>
                          <td>
                            <span
                              className={`pill-badge ${entry.entry_type === "CREDIT" ? "pill-unpaid" : "pill-paid"}`}
                            >
                              {entry.entry_type}
                            </span>
                          </td>
                          <td className="col-amount">₹{formatRupees(entry.amount_paise)}</td>
                          <td className="col-amount" style={{ color: "#38bdf8" }}>
                            ₹{formatRupees(entry.balance_paise)}
                          </td>
                          <td style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>{entry.notes || "-"}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setShowPayablesLedgerModal(false)}
              >
                Close [Esc]
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

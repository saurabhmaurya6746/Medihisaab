import { Link, useNavigate } from "react-router-dom";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Download,
  FileKey,
  KeyRound,
  LayoutDashboard,
  LifeBuoy,
  ListFilter,
  Loader2,
  LogOut,
  RefreshCcw,
  Search,
  Settings,
  ShieldAlert,
  Users,
  XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/site/Logo";
import { signOut, useSession } from "@/lib/auth";
import {
  api,
  type AuditEventItem,
  type ClientProfile,
  type DashboardStats,
  type LicenseInfo,
  type RenewalRequestItem,
  type SubscriptionInfo,
  type SystemSettingsData,
} from "@/lib/api";
import { usePageTitle } from "@/hooks/use-page-title";

type AdminTab = "overview" | "clients" | "renewals" | "licenses" | "subscriptions" | "settings" | "audit";

export function AdminPortalPage() {
  usePageTitle("Vendor Administration — MediHisaab");

  const { ready, session, token } = useSession();
  const navigate = useNavigate();

  const [currentTab, setCurrentTab] = useState<AdminTab>("overview");
  const [loading, setLoading] = useState(true);

  // Data states
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [clients, setClients] = useState<ClientProfile[]>([]);
  const [renewals, setRenewals] = useState<RenewalRequestItem[]>([]);
  const [licenses, setLicenses] = useState<LicenseInfo[]>([]);
  const [subscriptions, setSubscriptions] = useState<SubscriptionInfo[]>([]);
  const [settings, setSettings] = useState<SystemSettingsData | null>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEventItem[]>([]);

  // Search & Filter states
  const [clientSearch, setClientSearch] = useState("");
  const [renewalFilter, setRenewalFilter] = useState<string>("ALL");

  // Selected client for detail view
  const [selectedClient, setSelectedClient] = useState<{
    client: ClientProfile;
    subscriptions: SubscriptionInfo[];
    licenses: LicenseInfo[];
  } | null>(null);

  // Action modals/states
  const [actionLoading, setActionLoading] = useState(false);
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const [trialDaysInput, setTrialDaysInput] = useState<number>(15);
  const [graceDaysInput, setGraceDaysInput] = useState<number>(7);
  const [supportPhoneInput, setSupportPhoneInput] = useState("");
  const [supportEmailInput, setSupportEmailInput] = useState("");
  const [vendorNotificationEmailInput, setVendorNotificationEmailInput] = useState("");

  useEffect(() => {
    if (ready) {
      if (!session || !token) {
        navigate("/account?next=/admin", { replace: true });
        return;
      }
      if (session.role !== "admin") {
        toast.error("Access restricted: Administrator role required.");
        navigate("/client", { replace: true });
        return;
      }
    }
  }, [ready, session, token, navigate]);

  const loadAllData = async () => {
    if (!token) return;
    try {
      setLoading(true);
      const [statsData, clientsData, renewalsData, settingsData] = await Promise.all([
        api.vendorGetStats(token).catch(() => null),
        api.vendorGetClients({}, token).catch(() => []),
        api.vendorGetRenewalRequests({}, token).catch(() => []),
        api.vendorGetSettings(token).catch(() => null),
      ]);

      setStats(statsData);
      setClients(clientsData);
      setRenewals(renewalsData);
      if (settingsData) {
        setSettings(settingsData);
        setTrialDaysInput(settingsData.default_trial_days);
        setGraceDaysInput(settingsData.default_grace_days);
        setSupportPhoneInput(settingsData.support_contacts.phone || "");
        setSupportEmailInput(settingsData.support_contacts.email || "");
        setVendorNotificationEmailInput(settingsData.support_contacts.vendor_notification_email || "");
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to load administration data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token && session?.role === "admin") {
      loadAllData();
    }
  }, [token, session]);

  // Lazy load tab data
  useEffect(() => {
    if (!token) return;
    if (currentTab === "licenses" && licenses.length === 0) {
      api.vendorGetLicenses({}, token).then(setLicenses).catch(() => {});
    } else if (currentTab === "subscriptions" && subscriptions.length === 0) {
      api.vendorGetSubscriptions({}, token).then(setSubscriptions).catch(() => {});
    } else if (currentTab === "audit" && auditEvents.length === 0) {
      api.vendorGetAuditEvents({ limit: 50 }, token).then(setAuditEvents).catch(() => {});
    }
  }, [currentTab, token]);

  const handleLogout = () => {
    signOut();
    toast.success("Administrator signed out.");
    navigate("/account");
  };

  // Actions
  const handleClientStatusChange = async (clientId: number, newStatus: string) => {
    if (!token) return;
    try {
      setActionLoading(true);
      await api.vendorChangeClientStatus(clientId, newStatus, `Manual administrative transition to ${newStatus}`, token);
      toast.success(`Client operational status updated to ${newStatus}.`);
      const updatedClients = await api.vendorGetClients({ q: clientSearch }, token);
      setClients(updatedClients);
      if (selectedClient && selectedClient.client.id === clientId) {
        const refreshed = await api.vendorGetClientDetail(clientId, token);
        setSelectedClient(refreshed);
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to update client status.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleApproveRenewal = async (request: RenewalRequestItem) => {
    if (!token) return;
    try {
      setActionLoading(true);
      const res = await api.vendorApproveRenewal(
        request.id,
        {
          payment_reference: request.payment_reference || undefined,
          amount: request.payment_amount || undefined,
          notes: "Approved via Vendor Administration Console",
        },
        token
      );
      toast.success(`Renewal #${request.id} approved!`, {
        description: `Subscription extended to ${res.new_expiry_date}. Signed license generated.`,
      });
      const updatedRenewals = await api.vendorGetRenewalRequests({}, token);
      setRenewals(updatedRenewals);
      // Reload stats
      api.vendorGetStats(token).then(setStats).catch(() => {});
    } catch (err: any) {
      toast.error(err.message || "Failed to approve renewal request.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRejectRenewal = async (requestId: number) => {
    if (!token || !rejectReason.trim()) {
      toast.error("Please provide a rejection reason.");
      return;
    }
    try {
      setActionLoading(true);
      await api.vendorRejectRenewal(requestId, rejectReason.trim(), token);
      toast.success(`Renewal request #${requestId} marked as rejected.`);
      setRejectingId(null);
      setRejectReason("");
      const updatedRenewals = await api.vendorGetRenewalRequests({}, token);
      setRenewals(updatedRenewals);
    } catch (err: any) {
      toast.error(err.message || "Failed to reject renewal request.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveTrialSettings = async () => {
    if (!token) return;
    try {
      setActionLoading(true);
      const res = await api.vendorUpdateTrialSettings(
        { default_trial_days: trialDaysInput, default_grace_days: graceDaysInput },
        token
      );
      toast.success("Trial and grace period settings updated successfully.", {
        description: `Default trial: ${res.default_trial_days} days, Grace: ${res.default_grace_days} days.`,
      });
    } catch (err: any) {
      toast.error(err.message || "Failed to update trial settings.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveSupportContacts = async () => {
    if (!token) return;
    try {
      setActionLoading(true);
      const res = await api.vendorUpdateSupportContacts(
        {
          phone: supportPhoneInput,
          email: supportEmailInput,
          vendor_notification_email: vendorNotificationEmailInput,
        },
        token
      );
      toast.success("Support contact details and vendor notifications updated.");
      if (settings) {
        setSettings({ ...settings, support_contacts: res });
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to update support contacts.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleSelectClient = async (clientId: number) => {
    if (!token) return;
    try {
      const detail = await api.vendorGetClientDetail(clientId, token);
      setSelectedClient(detail);
    } catch (err: any) {
      toast.error(err.message || "Failed to load client profile details.");
    }
  };

  const handleDownloadLicenseFile = async (licenseId: string) => {
    if (!token) return;
    try {
      const payload = await api.vendorDownloadLicenseFile(licenseId, token);
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(payload, null, 2));
      const downloadAnchor = document.createElement("a");
      downloadAnchor.setAttribute("href", dataStr);
      downloadAnchor.setAttribute("download", `${licenseId}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
      toast.success(`License token ${licenseId}.json downloaded.`);
    } catch (err: any) {
      toast.error(err.message || "Failed to download license file.");
    }
  };

  if (!ready || loading || !session) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 size-5 animate-spin" /> Initializing Vendor Administration Console…
      </div>
    );
  }

  const filteredClients = clients.filter(
    (c) =>
      c.business_name.toLowerCase().includes(clientSearch.toLowerCase()) ||
      c.owner_name.toLowerCase().includes(clientSearch.toLowerCase()) ||
      c.email.toLowerCase().includes(clientSearch.toLowerCase()) ||
      c.client_code.toLowerCase().includes(clientSearch.toLowerCase()) ||
      c.phone.includes(clientSearch)
  );

  const filteredRenewals = renewals.filter((r) => {
    if (renewalFilter === "ALL") return true;
    return r.status === renewalFilter;
  });

  return (
    <div className="min-h-screen bg-background lg:grid lg:grid-cols-[16rem_1fr]">
      {/* Sidebar */}
      <aside className="sticky top-0 hidden h-screen flex-col border-r bg-sidebar lg:flex">
        <div className="border-b p-4">
          <Logo className="h-7" />
          <p className="mt-1 text-xs font-semibold text-primary">Vendor Administration Console</p>
        </div>
        <nav aria-label="Admin Navigation" className="flex h-full flex-col gap-1 p-3">
          {[
            { id: "overview", label: "Overview & KPIs", icon: LayoutDashboard },
            { id: "clients", label: "Clients & Stores", icon: Users },
            { id: "renewals", label: "Renewal Requests", icon: RefreshCcw, count: renewals.filter((r) => r.status === "PENDING").length },
            { id: "licenses", label: "Issued Licenses", icon: FileKey },
            { id: "subscriptions", label: "Subscriptions", icon: Clock },
            { id: "settings", label: "System Settings", icon: Settings },
            { id: "audit", label: "Audit History", icon: ShieldAlert },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => {
                setCurrentTab(item.id as AdminTab);
                setSelectedClient(null);
              }}
              className={`flex items-center justify-between rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                currentTab === item.id
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <item.icon className="size-4" />
                <span>{item.label}</span>
              </div>
              {item.count ? (
                <span className="rounded-full bg-destructive px-1.5 py-0.5 text-[10px] font-bold text-destructive-foreground">
                  {item.count}
                </span>
              ) : null}
            </button>
          ))}
          <div className="mt-auto space-y-1 border-t pt-3">
            <Link
              to="/"
              className="block rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-sidebar-accent"
            >
              ← Public Website
            </Link>
            <button
              onClick={handleLogout}
              className="flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-sidebar-accent"
            >
              <LogOut className="size-4" /> Sign Out
            </button>
          </div>
        </nav>
      </aside>

      {/* Main Content Area */}
      <div>
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-4 border-b bg-background/95 px-4 backdrop-blur-sm md:px-8">
          <div>
            <h1 className="text-base font-bold capitalize">
              {currentTab === "overview" && "Executive Dashboard & KPI Metrics"}
              {currentTab === "clients" && "Pharmacy Clients Directory"}
              {currentTab === "renewals" && "License Renewal Requests"}
              {currentTab === "licenses" && "Cryptographic Ed25519 Licenses"}
              {currentTab === "subscriptions" && "Client Subscriptions & Trials"}
              {currentTab === "settings" && "Configurable System & Trial Settings"}
              {currentTab === "audit" && "System Audit Log & Immutable Activity"}
            </h1>
            <p className="text-xs text-muted-foreground">
              Authenticated as {session.email} ({session.vendorRole || "ADMIN"})
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={loadAllData} disabled={actionLoading}>
              <RefreshCcw className="size-3.5" /> Refresh Data
            </Button>
          </div>
        </header>

        <div className="p-4 md:p-8">
          {/* TAB 1: OVERVIEW */}
          {currentTab === "overview" && stats && (
            <div className="space-y-8">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-lg border bg-card p-5">
                  <dt className="text-xs text-muted-foreground">Total Registered Clients</dt>
                  <dd className="mt-2 text-3xl font-bold">{stats.total_clients}</dd>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {stats.trial_clients} active evaluation trials
                  </p>
                </div>
                <div className="rounded-lg border bg-card p-5">
                  <dt className="text-xs text-muted-foreground">Active Paid Subscriptions</dt>
                  <dd className="mt-2 text-3xl font-bold text-primary">{stats.active_subscriptions}</dd>
                  <p className="mt-1 text-xs text-muted-foreground">Commercial store counters</p>
                </div>
                <div className="rounded-lg border bg-card p-5">
                  <dt className="text-xs text-muted-foreground">Expiring in 14 Days</dt>
                  <dd className="mt-2 text-3xl font-bold text-warning">
                    {stats.expiring_soon_subscriptions}
                  </dd>
                  <p className="mt-1 text-xs text-muted-foreground">Recommend renewal outreach</p>
                </div>
                <div className="rounded-lg border bg-card p-5">
                  <dt className="text-xs text-muted-foreground">Total Issued Licenses</dt>
                  <dd className="mt-2 text-3xl font-bold">{stats.total_licenses_issued}</dd>
                  <p className="mt-1 text-xs text-muted-foreground">Ed25519 digital signatures</p>
                </div>
              </div>

              {/* Pending Renewals Alert */}
              {renewals.filter((r) => r.status === "PENDING").length > 0 && (
                <div className="flex items-center justify-between rounded-lg border border-warning/30 bg-warning-surface p-4 text-warning">
                  <div className="flex items-center gap-3">
                    <Clock className="size-5 shrink-0" />
                    <div>
                      <p className="font-semibold">
                        {renewals.filter((r) => r.status === "PENDING").length} Renewal Request(s) Pending Review
                      </p>
                      <p className="text-xs">
                        Review customer payment references and issue renewed signed licenses.
                      </p>
                    </div>
                  </div>
                  <Button size="sm" onClick={() => setCurrentTab("renewals")}>
                    Review Requests
                  </Button>
                </div>
              )}

              {/* Recent Licenses Table */}
              <div className="rounded-lg border bg-card">
                <div className="border-b p-4">
                  <h2 className="text-sm font-semibold">Recent Cryptographic Licenses Issued</h2>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b bg-muted/50 text-xs text-muted-foreground">
                      <tr>
                        <th className="p-3">License ID</th>
                        <th className="p-3">Client</th>
                        <th className="p-3">Edition</th>
                        <th className="p-3">Terminals</th>
                        <th className="p-3">Activation</th>
                        <th className="p-3">Expiry</th>
                        <th className="p-3">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y font-mono text-xs">
                      {stats.recent_licenses.map((lic) => (
                        <tr key={lic.id} className="hover:bg-muted/20">
                          <td className="p-3 font-semibold text-primary">{lic.license_id}</td>
                          <td className="p-3 font-sans font-medium">{lic.client_name}</td>
                          <td className="p-3">
                            <span
                              className={`rounded px-1.5 py-0.5 text-[10px] font-sans font-semibold ${
                                lic.edition === "TRIAL"
                                  ? "bg-info-surface text-info"
                                  : "bg-secondary text-secondary-foreground"
                              }`}
                            >
                              {lic.edition}
                            </span>
                          </td>
                          <td className="p-3 font-sans">{lic.terminal_count}</td>
                          <td className="p-3">{lic.activation_date}</td>
                          <td className="p-3">{lic.expiry_date || "Never"}</td>
                          <td className="p-3 font-sans">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDownloadLicenseFile(lic.license_id)}
                            >
                              <Download className="size-3 mr-1" /> Token (.json)
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: CLIENTS */}
          {currentTab === "clients" && (
            <div className="space-y-6">
              {selectedClient ? (
                // Selected Client Profile View
                <div className="space-y-6">
                  <div className="flex items-center justify-between">
                    <Button variant="outline" size="sm" onClick={() => setSelectedClient(null)}>
                      ← Back to Clients List
                    </Button>
                    <div className="flex items-center gap-2">
                      <Label className="text-xs">Operational Status:</Label>
                      {["ACTIVE", "SUSPENDED", "CLOSED"].map((st) => (
                        <Button
                          key={st}
                          variant={selectedClient.client.status === st ? "default" : "outline"}
                          size="sm"
                          disabled={actionLoading || selectedClient.client.status === st}
                          onClick={() => handleClientStatusChange(selectedClient.client.id, st)}
                        >
                          {st}
                        </Button>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-lg border bg-card p-6">
                    <div className="flex flex-wrap items-start justify-between gap-4 border-b pb-6">
                      <div>
                        <h2 className="text-2xl font-bold">{selectedClient.client.business_name}</h2>
                        <p className="text-sm text-muted-foreground">
                          Code: {selectedClient.client.client_code} · Owner: {selectedClient.client.owner_name}
                        </p>
                      </div>
                      <span
                        className={`rounded px-2.5 py-1 text-xs font-semibold ${
                          selectedClient.client.status === "ACTIVE"
                            ? "bg-secondary text-secondary-foreground"
                            : selectedClient.client.status === "TRIAL"
                              ? "bg-info-surface text-info"
                              : "bg-destructive-surface text-destructive"
                        }`}
                      >
                        {selectedClient.client.status}
                      </span>
                    </div>

                    <dl className="mt-6 grid gap-4 sm:grid-cols-3">
                      <div>
                        <dt className="text-xs text-muted-foreground">Email</dt>
                        <dd className="font-medium">{selectedClient.client.email}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-muted-foreground">Phone</dt>
                        <dd className="font-medium">{selectedClient.client.phone}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-muted-foreground">GSTIN / Drug License</dt>
                        <dd className="font-medium">
                          {selectedClient.client.gstin || selectedClient.client.retail_drug_license || "None recorded"}
                        </dd>
                      </div>
                    </dl>
                  </div>

                  {/* Authoritative Current Subscription & License State */}
                  {(() => {
                    const latestSub = selectedClient.subscriptions && selectedClient.subscriptions.length > 0
                      ? selectedClient.subscriptions[0]
                      : null;
                    const latestLic = selectedClient.licenses && selectedClient.licenses.length > 0
                      ? selectedClient.licenses[0]
                      : null;
                    
                    const todayDate = new Date();
                    todayDate.setHours(0, 0, 0, 0);

                    let daysRemaining: number | null = null;
                    let isGraceActive = false;
                    let displayStatus = latestSub ? latestSub.status : "INACTIVE";

                    if (latestSub && latestSub.current_period_end) {
                      const periodEnd = new Date(latestSub.current_period_end);
                      periodEnd.setHours(0, 0, 0, 0);
                      const graceEnd = latestSub.grace_period_end ? new Date(latestSub.grace_period_end) : periodEnd;
                      graceEnd.setHours(0, 0, 0, 0);

                      const diffTime = periodEnd.getTime() - todayDate.getTime();
                      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

                      if (diffDays >= 0) {
                        daysRemaining = diffDays;
                        isGraceActive = false;
                      } else {
                        const graceDiffTime = graceEnd.getTime() - todayDate.getTime();
                        const graceDiffDays = Math.ceil(graceDiffTime / (1000 * 60 * 60 * 24));
                        if (graceDiffDays >= 0) {
                          daysRemaining = graceDiffDays;
                          isGraceActive = true;
                          displayStatus = "GRACE_PERIOD";
                        } else {
                          daysRemaining = 0;
                          isGraceActive = false;
                          displayStatus = "EXPIRED";
                        }
                      }
                    }

                    return (
                      <div className="rounded-lg border bg-card p-6">
                        <div className="flex flex-wrap items-center justify-between gap-4 border-b pb-4">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                              Authoritative Subscription State
                            </p>
                            <h3 className="text-xl font-bold mt-1">
                              {latestSub?.plan?.name || (latestSub?.is_trial ? "Evaluation Trial Plan" : "Standard Plan")}
                            </h3>
                          </div>
                          <div className="flex items-center gap-3">
                            <span
                              className={`rounded px-2.5 py-1 text-xs font-semibold ${
                                displayStatus === "ACTIVE"
                                  ? "bg-secondary text-secondary-foreground"
                                  : displayStatus === "TRIALING"
                                    ? "bg-info-surface text-info"
                                    : displayStatus === "GRACE_PERIOD"
                                      ? "bg-warning-surface text-warning"
                                      : "bg-destructive-surface text-destructive"
                              }`}
                            >
                              {displayStatus === "TRIALING" ? "EVALUATION TRIAL" : displayStatus}
                            </span>
                            {daysRemaining !== null && (
                              <span className="font-mono text-sm font-semibold text-primary">
                                {daysRemaining} days remaining
                              </span>
                            )}
                          </div>
                        </div>

                        <dl className="mt-4 grid gap-4 sm:grid-cols-4">
                          <div>
                            <dt className="text-xs text-muted-foreground">Subscription Type</dt>
                            <dd className="font-medium text-sm">
                              {latestSub?.is_trial ? "15-Day Free Trial" : "Commercial Paid Subscription"}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-xs text-muted-foreground">Current Period</dt>
                            <dd className="font-medium text-sm">
                              {latestSub ? `${latestSub.current_period_start} to ${latestSub.current_period_end}` : "None"}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-xs text-muted-foreground">Grace Period Status</dt>
                            <dd className="font-medium text-sm">
                              {isGraceActive
                                ? `Active (Ends: ${latestSub?.grace_period_end})`
                                : latestSub?.grace_period_end
                                  ? `Ends ${latestSub.grace_period_end}`
                                  : "None"}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-xs text-muted-foreground">Active License Token</dt>
                            <dd className="font-mono text-xs text-primary font-semibold truncate flex items-center justify-between">
                              <span>{latestLic?.license_id || "None Issued"}</span>
                              {latestLic && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-6 px-2 text-xs"
                                  onClick={() => handleDownloadLicenseFile(latestLic.license_id)}
                                >
                                  <Download className="size-3" />
                                </Button>
                              )}
                            </dd>
                          </div>
                        </dl>
                      </div>
                    );
                  })()}

                  {/* Subscriptions of this client */}
                  <div className="rounded-lg border bg-card">
                    <div className="border-b p-4">
                      <h3 className="font-semibold text-sm">Client Subscription History ({selectedClient.subscriptions.length})</h3>
                    </div>
                    <div className="divide-y text-sm">
                      {selectedClient.subscriptions.length === 0 ? (
                        <p className="p-4 text-xs text-muted-foreground">No subscription records found for this client.</p>
                      ) : (
                        selectedClient.subscriptions.map((s) => (
                          <div key={s.id} className="p-4 flex items-center justify-between">
                            <div>
                              <p className="font-semibold">
                                Subscription #{s.id} · {s.plan?.name || (s.is_trial ? "Evaluation Trial" : "Commercial Plan")}
                                <span className={`ml-2 rounded px-2 py-0.5 text-xs font-semibold ${
                                  s.status === "ACTIVE"
                                    ? "bg-secondary text-secondary-foreground"
                                    : s.status === "TRIALING"
                                      ? "bg-info-surface text-info"
                                      : "bg-destructive-surface text-destructive"
                                }`}>
                                  {s.status}
                                </span>
                              </p>
                              <p className="text-xs text-muted-foreground mt-1">
                                Period: {s.current_period_start} to {s.current_period_end} · Grace ends: {s.grace_period_end}
                                {s.payment_reference ? ` · Payment Ref: ${s.payment_reference}` : ""}
                              </p>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Issued licenses of this client */}
                  <div className="rounded-lg border bg-card">
                    <div className="border-b p-4">
                      <h3 className="font-semibold text-sm">Cryptographic Licenses</h3>
                    </div>
                    <div className="divide-y text-sm">
                      {selectedClient.licenses.map((l) => (
                        <div key={l.id} className="p-4 flex items-center justify-between">
                          <div>
                            <p className="font-mono font-semibold text-primary">{l.license_id}</p>
                            <p className="text-xs text-muted-foreground">
                              Edition: {l.edition} · Terminals: {l.terminal_count} · Expiry: {l.expiry_date}
                            </p>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleDownloadLicenseFile(l.license_id)}
                          >
                            <Download className="size-3 mr-1" /> Token (.json)
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                // Client List Table
                <>
                  <div className="flex items-center gap-4">
                    <div className="relative flex-1">
                      <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
                      <Input
                        placeholder="Search clients by pharmacy name, owner, phone, email, or client code…"
                        value={clientSearch}
                        onChange={(e) => setClientSearch(e.target.value)}
                        className="pl-9"
                      />
                    </div>
                  </div>

                  <div className="rounded-lg border bg-card overflow-hidden">
                    <table className="w-full text-left text-sm">
                      <thead className="border-b bg-muted/50 text-xs text-muted-foreground">
                        <tr>
                          <th className="p-3">Client Code</th>
                          <th className="p-3">Pharmacy Name</th>
                          <th className="p-3">Owner</th>
                          <th className="p-3">Contact</th>
                          <th className="p-3">Status</th>
                          <th className="p-3">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {filteredClients.map((client) => (
                          <tr key={client.id} className="hover:bg-muted/20">
                            <td className="p-3 font-mono text-xs font-semibold text-primary">
                              {client.client_code}
                            </td>
                            <td className="p-3 font-medium">{client.business_name}</td>
                            <td className="p-3">{client.owner_name}</td>
                            <td className="p-3 text-xs text-muted-foreground">
                              <p>{client.email}</p>
                              <p>{client.phone}</p>
                            </td>
                            <td className="p-3">
                              <span
                                className={`rounded px-2 py-0.5 text-xs font-semibold ${
                                  client.status === "ACTIVE"
                                    ? "bg-secondary text-secondary-foreground"
                                    : client.status === "TRIAL"
                                      ? "bg-info-surface text-info"
                                      : "bg-destructive-surface text-destructive"
                                }`}
                              >
                                {client.status}
                              </span>
                            </td>
                            <td className="p-3">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleSelectClient(client.id)}
                              >
                                View Details
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          )}

          {/* TAB 3: RENEWAL REQUESTS */}
          {currentTab === "renewals" && (
            <div className="space-y-6">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-muted-foreground">Filter status:</span>
                {["ALL", "PENDING", "APPROVED", "REJECTED"].map((st) => (
                  <Button
                    key={st}
                    variant={renewalFilter === st ? "default" : "outline"}
                    size="sm"
                    onClick={() => setRenewalFilter(st)}
                  >
                    {st}
                  </Button>
                ))}
              </div>

              <div className="overflow-hidden rounded-lg border bg-card">
                {filteredRenewals.length === 0 ? (
                  <div className="p-8 text-center text-sm text-muted-foreground">
                    No renewal requests matching filter criteria.
                  </div>
                ) : (
                  <div className="divide-y">
                    {filteredRenewals.map((r) => (
                      <div key={r.id} className="p-5 flex flex-wrap items-start justify-between gap-4">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-base">
                              Renewal #{r.id}: {r.store_name}
                            </span>
                            <span
                              className={`rounded px-2 py-0.5 text-xs font-semibold ${
                                r.status === "APPROVED"
                                  ? "bg-secondary text-secondary-foreground"
                                  : r.status === "REJECTED"
                                    ? "bg-destructive-surface text-destructive"
                                    : "bg-warning-surface text-warning"
                              }`}
                            >
                              {r.status}
                            </span>
                          </div>
                          <p className="text-sm text-muted-foreground">
                            Plan: <span className="font-medium text-foreground">{r.requested_plan_code}</span> ·
                            Contact: {r.contact_name} ({r.phone}, {r.email})
                          </p>
                          {r.payment_reference && (
                            <p className="text-xs font-mono font-medium text-primary">
                              Payment Ref / UTR: {r.payment_reference} (Amount: ₹{(r.payment_amount / 100).toLocaleString("en-IN")})
                            </p>
                          )}
                          {r.notes && (
                            <p className="text-xs text-muted-foreground italic">Client notes: "{r.notes}"</p>
                          )}
                          {r.rejection_reason && (
                            <p className="text-xs text-destructive">Rejection reason: {r.rejection_reason}</p>
                          )}
                          <p className="text-[11px] text-muted-foreground">
                            Submitted: {new Date(r.created_at).toLocaleString("en-IN")} ·
                            {r.vendor_notification_sent ? " Email notification sent" : " Email delivery unconfirmed"}
                          </p>
                        </div>

                        {r.status === "PENDING" && (
                          <div className="flex flex-col gap-2 sm:flex-row">
                            <Button
                              size="sm"
                              disabled={actionLoading}
                              onClick={() => handleApproveRenewal(r)}
                            >
                              <CheckCircle2 className="size-3.5 mr-1" /> Approve & Sign License
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={actionLoading}
                              onClick={() => setRejectingId(r.id)}
                            >
                              <XCircle className="size-3.5 mr-1" /> Reject
                            </Button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Rejection Modal / Prompt */}
              {rejectingId && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 p-4 backdrop-blur-sm">
                  <div className="w-full max-w-md rounded-lg border bg-card p-6 shadow-lg">
                    <h3 className="text-lg font-bold">Reject Renewal Request #{rejectingId}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Document the reason for rejection (e.g. UTR not found in bank statement).
                    </p>
                    <div className="mt-4 space-y-1.5">
                      <Label htmlFor="rej-reason">Rejection Reason</Label>
                      <Input
                        id="rej-reason"
                        placeholder="Enter reason for customer and audit record..."
                        value={rejectReason}
                        onChange={(e) => setRejectReason(e.target.value)}
                      />
                    </div>
                    <div className="mt-6 flex justify-end gap-2">
                      <Button
                        variant="outline"
                        onClick={() => {
                          setRejectingId(null);
                          setRejectReason("");
                        }}
                      >
                        Cancel
                      </Button>
                      <Button
                        variant="destructive"
                        disabled={actionLoading || !rejectReason.trim()}
                        onClick={() => handleRejectRenewal(rejectingId)}
                      >
                        Confirm Rejection
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 4: LICENSES */}
          {currentTab === "licenses" && (
            <div className="space-y-6">
              <div className="overflow-hidden rounded-lg border bg-card">
                <table className="w-full text-left text-sm font-mono">
                  <thead className="border-b bg-muted/50 text-xs font-sans text-muted-foreground">
                    <tr>
                      <th className="p-3">License ID</th>
                      <th className="p-3">Store Name</th>
                      <th className="p-3">Edition</th>
                      <th className="p-3">Counters</th>
                      <th className="p-3">Activation</th>
                      <th className="p-3">Expiry</th>
                      <th className="p-3">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y text-xs">
                    {licenses.map((lic) => (
                      <tr key={lic.id} className="hover:bg-muted/20">
                        <td className="p-3 font-semibold text-primary">{lic.license_id}</td>
                        <td className="p-3 font-sans font-medium">{lic.client_name}</td>
                        <td className="p-3 font-sans">
                          <span
                            className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                              lic.edition === "TRIAL"
                                ? "bg-info-surface text-info"
                                : "bg-secondary text-secondary-foreground"
                            }`}
                          >
                            {lic.edition}
                          </span>
                        </td>
                        <td className="p-3 font-sans">{lic.terminal_count}</td>
                        <td className="p-3">{lic.activation_date}</td>
                        <td className="p-3">{lic.expiry_date || "Never"}</td>
                        <td className="p-3 font-sans">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDownloadLicenseFile(lic.license_id)}
                          >
                            <Download className="size-3 mr-1" /> Token (.json)
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 5: SUBSCRIPTIONS */}
          {currentTab === "subscriptions" && (
            <div className="space-y-6">
              <div className="overflow-hidden rounded-lg border bg-card">
                <div className="divide-y text-sm">
                  {subscriptions.map((sub) => (
                    <div key={sub.id} className="p-4 flex items-center justify-between">
                      <div>
                        <p className="font-semibold">
                          Subscription #{sub.id} (Client #{sub.client_id}) — Status: {sub.status}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Start: {sub.start_date} · Current Period: {sub.current_period_start} to {sub.current_period_end} · Grace ends: {sub.grace_period_end}
                        </p>
                        {sub.payment_reference && (
                          <p className="text-xs font-mono text-primary">Payment Ref: {sub.payment_reference}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 6: SETTINGS */}
          {currentTab === "settings" && (
            <div className="max-w-2xl space-y-8">
              {/* Trial Duration Defaults */}
              <div className="rounded-lg border bg-card p-6 space-y-4">
                <div>
                  <h3 className="text-base font-semibold">Evaluation Trial & Grace Period Defaults</h3>
                  <p className="text-xs text-muted-foreground">
                    Applied automatically to newly registered pharmacy accounts and license generators.
                  </p>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="s-trial">Default Trial Duration (Days)</Label>
                    <Input
                      id="s-trial"
                      type="number"
                      min={1}
                      max={365}
                      value={trialDaysInput}
                      onChange={(e) => setTrialDaysInput(parseInt(e.target.value) || 15)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="s-grace">Default Grace Period (Days)</Label>
                    <Input
                      id="s-grace"
                      type="number"
                      min={0}
                      max={90}
                      value={graceDaysInput}
                      onChange={(e) => setGraceDaysInput(parseInt(e.target.value) || 7)}
                    />
                  </div>
                </div>
                <Button onClick={handleSaveTrialSettings} disabled={actionLoading}>
                  {actionLoading && <Loader2 className="size-4 animate-spin mr-1" />} Save Trial Settings
                </Button>
              </div>

              {/* Support Contacts & Notifications */}
              <div className="rounded-lg border bg-card p-6 space-y-4">
                <div>
                  <h3 className="text-base font-semibold">Vendor Support Contacts & Notification Dispatch</h3>
                  <p className="text-xs text-muted-foreground">
                    Displayed on client dashboards and used to notify the vendor team of renewal submissions.
                  </p>
                </div>
                <div className="space-y-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="s-phone">Support Hotline / WhatsApp Phone</Label>
                    <Input
                      id="s-phone"
                      value={supportPhoneInput}
                      onChange={(e) => setSupportPhoneInput(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="s-email">Customer Support Email</Label>
                    <Input
                      id="s-email"
                      type="email"
                      value={supportEmailInput}
                      onChange={(e) => setSupportEmailInput(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="s-vnotify">Vendor Inbound Notification Email</Label>
                    <Input
                      id="s-vnotify"
                      type="email"
                      placeholder="vendor-alerts@example.com"
                      value={vendorNotificationEmailInput}
                      onChange={(e) => setVendorNotificationEmailInput(e.target.value)}
                    />
                  </div>
                </div>
                <Button onClick={handleSaveSupportContacts} disabled={actionLoading}>
                  {actionLoading && <Loader2 className="size-4 animate-spin mr-1" />} Save Contact Settings
                </Button>
              </div>
            </div>
          )}

          {/* TAB 7: AUDIT */}
          {currentTab === "audit" && (
            <div className="space-y-6">
              <div className="overflow-hidden rounded-lg border bg-card">
                <table className="w-full text-left text-sm">
                  <thead className="border-b bg-muted/50 text-xs text-muted-foreground">
                    <tr>
                      <th className="p-3">Timestamp (UTC)</th>
                      <th className="p-3">User</th>
                      <th className="p-3">Action</th>
                      <th className="p-3">Entity</th>
                      <th className="p-3">IP Address</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y text-xs font-mono">
                    {auditEvents.map((ev) => (
                      <tr key={ev.id} className="hover:bg-muted/20">
                        <td className="p-3 text-muted-foreground">
                          {new Date(ev.timestamp).toLocaleString("en-IN")}
                        </td>
                        <td className="p-3 font-sans font-medium">{ev.user_email}</td>
                        <td className="p-3 font-semibold text-primary">{ev.action}</td>
                        <td className="p-3 font-sans">{ev.entity_type} {ev.entity_id ? `(#${ev.entity_id})` : ""}</td>
                        <td className="p-3 text-muted-foreground">{ev.ip_address || "unknown"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

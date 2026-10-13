import { Link, useNavigate } from "react-router-dom";
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Clock,
  Download,
  FileKey,
  LayoutDashboard,
  LifeBuoy,
  Loader2,
  LogOut,
  Menu,
  RefreshCcw,
  X,
} from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Field } from "@/components/site/Field";
import { Logo } from "@/components/site/Logo";
import { signOut, useSession } from "@/lib/auth";
import {
  api,
  type ClientDashboardData,
  type ClientPlan,
  type RenewalRequestItem,
  type SupportContacts,
} from "@/lib/api";
import { contactConfig, releaseConfig } from "@/config/site";
import { usePageTitle } from "@/hooks/use-page-title";

const sections = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "download", label: "Download", icon: Download },
  { id: "renewal", label: "Renewal", icon: RefreshCcw },
  { id: "activity", label: "Activity", icon: Activity },
  { id: "support", label: "Support", icon: LifeBuoy },
] as const;

export function ClientDashboardPage() {
  usePageTitle("Dashboard — MediHisaab");

  const { ready, session, token } = useSession();
  const navigate = useNavigate();
  const [navOpen, setNavOpen] = useState(false);

  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState<ClientDashboardData | null>(null);
  const [renewalRequests, setRenewalRequests] = useState<RenewalRequestItem[]>([]);
  const [plans, setPlans] = useState<ClientPlan[]>([]);
  const [supportContacts, setSupportContacts] = useState<SupportContacts | null>(null);
  const [licenseDownloading, setLicenseDownloading] = useState(false);

  useEffect(() => {
    if (ready) {
      if (!session || !token) {
        navigate("/account?next=/client", { replace: true });
        return;
      }
      if (session.role === "admin") {
        navigate("/admin", { replace: true });
        return;
      }
    }
  }, [ready, session, token, navigate]);

  useEffect(() => {
    if (!token || !session || session.role !== "client") return;

    let mounted = true;
    async function loadData() {
      try {
        setLoading(true);
        const [dashData, renewalsData, plansData, contactsData] = await Promise.all([
          api.clientGetDashboard(token!),
          api.clientGetRenewalRequests(token!),
          api.clientGetPlans().catch(() => []),
          api.clientGetSupportContacts().catch(() => null),
        ]);
        if (mounted) {
          setDashboard(dashData);
          setRenewalRequests(renewalsData);
          setPlans(plansData);
          if (contactsData) setSupportContacts(contactsData);
        }
      } catch (err: any) {
        if (mounted) {
          toast.error("Failed to load dashboard: " + (err.message || "Session error"));
        }
      } finally {
        if (mounted) setLoading(false);
      }
    }

    loadData();
    return () => {
      mounted = false;
    };
  }, [token, session]);

  if (!ready || loading || !session) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 size-5 animate-spin" /> Loading your pharmacy dashboard…
      </div>
    );
  }

  const logout = () => {
    signOut();
    toast.success("Signed out successfully");
    navigate("/");
  };

  const handleDownloadLicenseJson = async () => {
    if (!token) return;
    try {
      setLicenseDownloading(true);
      const payload = await api.clientDownloadLicense(token);
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(payload, null, 2));
      const downloadAnchor = document.createElement("a");
      const filename = `${dashboard?.active_license?.license_id || "license"}.json`;
      downloadAnchor.setAttribute("href", dataStr);
      downloadAnchor.setAttribute("download", filename);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
      toast.success("License file downloaded", { description: filename });
    } catch (err: any) {
      toast.error(err.message || "Failed to download license file.");
    } finally {
      setLicenseDownloading(false);
    }
  };

  const latestPendingRenewal = renewalRequests.find((r) => r.status === "PENDING");

  // Determine badge styling based on server subscription status
  const subStatus = dashboard?.status || "INACTIVE";
  let statusBadge = { label: "Active", tone: "bg-secondary text-secondary-foreground" };
  if (subStatus === "TRIALING") {
    statusBadge = { label: "Evaluation Trial", tone: "bg-info-surface text-info" };
  } else if (subStatus === "ACTIVE") {
    statusBadge = { label: "Active License", tone: "bg-secondary text-secondary-foreground" };
  } else if (subStatus === "PAST_DUE" || dashboard?.grace_period_active) {
    statusBadge = { label: "Grace Period", tone: "bg-warning-surface text-warning" };
  } else if (subStatus === "EXPIRED") {
    statusBadge = { label: "Expired", tone: "bg-destructive-surface text-destructive" };
  } else if (subStatus === "SUSPENDED") {
    statusBadge = { label: "Suspended", tone: "bg-destructive-surface text-destructive" };
  }

  const expiryDateFormatted = dashboard?.subscription?.current_period_end
    ? new Date(dashboard.subscription.current_period_end).toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
      })
    : dashboard?.active_license?.expiry_date
      ? new Date(dashboard.active_license.expiry_date).toLocaleDateString("en-IN", {
          day: "numeric",
          month: "short",
          year: "numeric",
        })
      : "Not available";

  const sidebar = (
    <nav aria-label="Dashboard" className="flex h-full flex-col gap-1 p-4">
      {sections.map((s) => (
        <a
          key={s.id}
          href={`#${s.id}`}
          onClick={() => setNavOpen(false)}
          className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
        >
          <s.icon className="size-4" /> {s.label}
        </a>
      ))}
      <div className="mt-auto space-y-1 border-t pt-4">
        <Link
          to="/"
          className="block rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-sidebar-accent"
        >
          ← Back to website
        </Link>
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-sidebar-accent"
        >
          <LogOut className="size-4" /> Log out
        </button>
      </div>
    </nav>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[16rem_1fr]">
      <aside className="sticky top-0 hidden h-screen flex-col border-r bg-sidebar lg:flex">
        <div className="border-b p-4">
          <Logo className="h-7" />
        </div>
        {sidebar}
      </aside>

      <div>
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-4 border-b bg-background/95 px-4 backdrop-blur-sm md:px-8">
          <div className="flex items-center gap-3">
            <button
              className="inline-flex size-10 items-center justify-center rounded-md border lg:hidden"
              aria-label={navOpen ? "Close menu" : "Open menu"}
              aria-expanded={navOpen}
              onClick={() => setNavOpen((o) => !o)}
            >
              {navOpen ? <X className="size-5" /> : <Menu className="size-5" />}
            </button>
            <div className="min-w-0">
              <p className="truncate font-semibold">{dashboard?.client.business_name || session.pharmacyName}</p>
              <p className="truncate text-xs text-muted-foreground">
                {session.email} · {dashboard?.client.client_code}
              </p>
            </div>
          </div>
          <span className="hidden rounded border border-border px-2.5 py-1 text-xs font-medium text-muted-foreground sm:inline">
            Production Client Portal
          </span>
        </header>
        {navOpen && <div className="border-b bg-sidebar lg:hidden">{sidebar}</div>}

        <div className="mx-auto max-w-5xl space-y-10 p-4 md:p-8">
          {/* Overview Section */}
          <section id="overview" className="scroll-mt-20">
            <h1 className="text-2xl font-bold">License overview</h1>
            <div className="mt-4 rounded-lg border bg-card">
              <div className="flex flex-wrap items-start justify-between gap-4 border-b p-6">
                <div>
                  <span
                    className={`inline-block rounded px-2.5 py-1 text-sm font-semibold ${statusBadge.tone}`}
                  >
                    {statusBadge.label}
                  </span>
                  <p className="mt-3 max-w-lg text-sm text-muted-foreground">
                    {subStatus === "TRIALING" &&
                      "Your evaluation trial is active. You have full access to billing, inventory, and FEFO batch dispensing."}
                    {subStatus === "ACTIVE" &&
                      "Your commercial license is fully active for all authorized billing counters."}
                    {dashboard?.grace_period_active &&
                      "Your subscription has entered the grace period. Please submit a renewal request to avoid billing interruption."}
                    {subStatus === "EXPIRED" &&
                      "Your license period has concluded. Counter transaction writes are currently locked until renewal."}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-mono text-4xl font-semibold text-primary-deep">
                    {dashboard?.days_remaining ?? 0}
                  </p>
                  <p className="text-xs text-muted-foreground">days remaining</p>
                </div>
              </div>
              <dl className="grid divide-y sm:grid-cols-4 sm:divide-x sm:divide-y-0">
                <div className="p-5">
                  <dt className="text-xs text-muted-foreground">
                    {subStatus === "TRIALING" ? "Trial ends" : "License ends"}
                  </dt>
                  <dd className="mt-1 font-medium">{expiryDateFormatted}</dd>
                </div>
                <div className="p-5">
                  <dt className="text-xs text-muted-foreground">Terminals</dt>
                  <dd className="mt-1 font-medium">{dashboard?.maximum_terminals ?? 1} counter(s)</dd>
                </div>
                <div className="p-5">
                  <dt className="text-xs text-muted-foreground">App version</dt>
                  <dd className="mt-1 font-mono">{releaseConfig.version ?? "1.0.0"}</dd>
                </div>
                <div className="p-5">
                  <dt className="text-xs text-muted-foreground">Renewal status</dt>
                  <dd className="mt-1 font-medium">
                    {latestPendingRenewal
                      ? `Pending · ${latestPendingRenewal.requested_plan_code}`
                      : "No pending request"}
                  </dd>
                </div>
              </dl>
            </div>

            {/* Offline License Download Card */}
            {dashboard?.active_license && (
              <div className="mt-4 flex flex-wrap items-center justify-between gap-4 rounded-lg border bg-surface p-4">
                <div className="flex items-center gap-3">
                  <FileKey className="size-5 text-primary" />
                  <div>
                    <p className="text-sm font-semibold">
                      Signed License Token ({dashboard.active_license.license_id})
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Ed25519 cryptographic token. Can be imported directly into the desktop app if running offline.
                    </p>
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleDownloadLicenseJson}
                  disabled={licenseDownloading}
                >
                  {licenseDownloading ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Download className="size-4" />
                  )}
                  Download License (.json)
                </Button>
              </div>
            )}
          </section>

          {/* Download & Installation Section */}
          <section id="download" className="scroll-mt-20 grid gap-6 md:grid-cols-2">
            <div className="rounded-lg border bg-card p-6">
              <h2 className="text-lg font-semibold">Download for Windows</h2>
              <p className="mt-2 text-sm text-muted-foreground">
                Get the official verified Windows installer binary and check cryptographic release metadata.
              </p>
              <Button asChild className="mt-4">
                <Link to="/download">
                  <Download className="size-4" /> Go to verified download
                </Link>
              </Button>
            </div>
            <div className="rounded-lg border bg-card p-6">
              <h2 className="text-lg font-semibold">Installation steps</h2>
              <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-sm text-muted-foreground">
                <li>Run the installer on your pharmacy billing PC.</li>
                <li>Sign in once using this online account to retrieve your signed license.</li>
                <li>Set up your separate local store administrator account.</li>
                <li>Configure an external USB/drive for regular hot SQLite backups.</li>
              </ol>
            </div>
          </section>

          {/* Renewal Section */}
          <section id="renewal" className="scroll-mt-20">
            <h2 className="text-xl font-bold">Request a license renewal</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Submit a renewal request when your evaluation trial or annual term approaches expiration.
            </p>
            <RenewalForm
              plans={plans}
              token={token!}
              hasPending={!!latestPendingRenewal}
              onSuccess={(item) => {
                setRenewalRequests((prev) => [item, ...prev.filter((r) => r.id !== item.id)]);
              }}
            />
          </section>

          {/* Recent Activity Section */}
          <section id="activity" className="scroll-mt-20">
            <h2 className="text-xl font-bold">Recent account activity</h2>
            <div className="mt-4 overflow-hidden rounded-lg border bg-card">
              {renewalRequests.length === 0 ? (
                <div className="p-6 text-center text-sm text-muted-foreground">
                  No renewal requests or manual payment submissions recorded yet.
                </div>
              ) : (
                <ul className="divide-y text-sm">
                  {renewalRequests.map((req) => (
                    <li key={req.id} className="flex flex-wrap items-center justify-between gap-4 p-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold">Request #{req.id}: {req.requested_plan_code}</span>
                          <span
                            className={`rounded px-2 py-0.5 text-xs font-medium ${
                              req.status === "APPROVED"
                                ? "bg-secondary text-secondary-foreground"
                                : req.status === "REJECTED"
                                  ? "bg-destructive-surface text-destructive"
                                  : "bg-warning-surface text-warning"
                            }`}
                          >
                            {req.status}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {req.payment_reference ? `Ref/UTR: ${req.payment_reference}` : "No payment reference"}
                          {req.notes ? ` · Notes: ${req.notes}` : ""}
                        </p>
                        {req.rejection_reason && (
                          <p className="mt-1 text-xs text-destructive">
                            Rejection reason: {req.rejection_reason}
                          </p>
                        )}
                      </div>
                      <div className="text-right text-xs text-muted-foreground">
                        <p>{new Date(req.created_at).toLocaleDateString("en-IN")}</p>
                        <p className="mt-0.5">
                          {req.vendor_notification_sent ? "Vendor notified via email" : "Recorded in vendor queue"}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>

          {/* Support Section */}
          <section id="support" className="scroll-mt-20 rounded-lg border bg-surface p-6">
            <h2 className="text-lg font-semibold">Vendor support channels</h2>
            <div className="mt-3 grid gap-3 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-xs text-muted-foreground">Email</dt>
                <dd className="mt-0.5 font-medium">
                  <a
                    href={`mailto:${supportContacts?.email || contactConfig.supportEmail}`}
                    className="text-primary hover:underline"
                  >
                    {supportContacts?.email || contactConfig.supportEmail || "support@apexhealth.com"}
                  </a>
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Phone</dt>
                <dd className="mt-0.5 font-medium">
                  <a
                    href={`tel:${supportContacts?.phone || contactConfig.supportPhone}`}
                    className="text-primary hover:underline"
                  >
                    {supportContacts?.phone || contactConfig.supportPhone || "+91 98765 43210"}
                  </a>
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">WhatsApp</dt>
                <dd className="mt-0.5 font-medium">
                  <a
                    href={`https://wa.me/${(supportContacts?.whatsapp || contactConfig.whatsapp || "919876543210").replace(/\D/g, "")}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary hover:underline"
                  >
                    {supportContacts?.whatsapp || contactConfig.whatsapp || "+91 98765 43210"}
                  </a>
                </dd>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function RenewalForm({
  plans,
  token,
  hasPending,
  onSuccess,
}: {
  plans: ClientPlan[];
  token: string;
  hasPending: boolean;
  onSuccess: (item: RenewalRequestItem) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const form = e.currentTarget;
    const planCode = String(f.get("plan") || "");
    const ref = String(f.get("reference") || "").trim();
    const notes = String(f.get("notes") || "").trim();

    if (!planCode) {
      setError("Please select a renewal plan.");
      return;
    }

    setError(undefined);
    setLoading(true);

    try {
      const selectedPlan = plans.find((p) => p.plan_code === planCode);
      const res = await api.clientSubmitRenewal(
        {
          requested_plan_code: planCode,
          payment_reference: ref || undefined,
          payment_amount: selectedPlan ? selectedPlan.price : 0,
          notes: notes || undefined,
        },
        token
      );

      if (res.vendor_notification_sent) {
        toast.success("Renewal request submitted!", {
          description: `Request #${res.id} recorded. Vendor has been notified via email.`,
        });
      } else {
        toast.info("Renewal request recorded", {
          description: `Request #${res.id} queued in vendor console. Email notification delivery was not confirmed, but our team will review it.`,
        });
      }

      onSuccess(res);
      form.reset();
    } catch (err: any) {
      setError(err.message || "Failed to submit renewal request.");
      toast.error(err.message || "Failed to submit renewal request.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="mt-4 space-y-4 rounded-lg border bg-card p-6">
      {hasPending && (
        <div className="flex items-start gap-3 rounded-md bg-info-surface p-3 text-sm text-info">
          <Clock className="mt-0.5 size-4 shrink-0" />
          <p>
            You already have a pending renewal request under review. Submitting another will record an additional request for vendor evaluation.
          </p>
        </div>
      )}
      <div className="space-y-1.5">
        <Label htmlFor="f-plan">Select Plan</Label>
        <select
          id="f-plan"
          name="plan"
          defaultValue=""
          aria-invalid={!!error}
          className="flex h-10 w-full rounded-md border border-input bg-transparent px-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="" disabled>
            Choose renewal plan
          </option>
          {plans.map((p) => (
            <option key={p.id} value={p.plan_code}>
              {p.name} — ₹{(p.price / 100).toLocaleString("en-IN")} / {p.billing_period.toLowerCase()} (up to {p.maximum_terminals} counters)
            </option>
          ))}
          {plans.length === 0 && (
            <>
              <option value="MONTHLY_STANDARD">Standard Counter (Monthly) — ₹999 / month</option>
              <option value="ANNUAL_STANDARD">Enterprise Multi-Counter (Annual) — ₹9,999 / year</option>
            </>
          )}
        </select>
        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>
      <Field label="Payment reference / UTR (optional if already paid via UPI/Bank)" name="reference" />
      <Field label="Notes or special counter requirements (optional)" name="notes" multiline />
      <Button type="submit" disabled={loading}>
        {loading && <Loader2 className="size-4 animate-spin" />} Submit Renewal Request
      </Button>
    </form>
  );
}

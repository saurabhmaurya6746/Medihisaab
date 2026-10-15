import { Link, useNavigate } from "react-router-dom";
import { Download, Loader2, PackageX, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { isValidInstallerUrl, NOT_CONFIGURED, releaseConfig } from "@/config/site";
import { useSession } from "@/lib/auth";
import { api, getApiBaseUrl } from "@/lib/api";
import { usePageTitle } from "@/hooks/use-page-title";

function buildAuthenticatedDownloadUrl(path: string, token: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    const url = new URL(path);
    url.searchParams.set("token", token);
    return url.toString();
  }
  const apiBase = getApiBaseUrl();
  const cleanPath = path.startsWith("/api/v1") ? path.slice(7) : path;
  const normalizedPath = cleanPath.startsWith("/") ? cleanPath : `/${cleanPath}`;
  return `${apiBase}${normalizedPath}?token=${encodeURIComponent(token)}`;
}

export function DownloadPage() {
  usePageTitle("Download for Windows — MediHisaab");

  const { ready, session, token } = useSession();
  const navigate = useNavigate();
  const [downloading, setDownloading] = useState(false);
  const [releaseInfo, setReleaseInfo] = useState({
    version: releaseConfig.version,
    fileSize: releaseConfig.fileSize,
    installerUrl: releaseConfig.installerUrl,
    sha256: releaseConfig.sha256,
    releaseDate: releaseConfig.releaseDate,
    requirements: releaseConfig.requirements,
    directDownloadUrl: "https://github.com/saurabhmaurya6746/Medihisaab/releases/download/v1.0.3/MediHisaab-Setup-1.0.3.exe",
    filename: "MediHisaab-Setup-1.0.3.exe",
  });

  useEffect(() => {
    if (ready && !session) {
      navigate("/account?next=/download", { replace: true });
    }
  }, [ready, session, navigate]);

  // Fetch real-time release artifact metadata directly from the licensing server
  useEffect(() => {
    if (!token) return;
    let active = true;
    api.clientGetDownloads(token)
      .then((downloads) => {
        if (!active) return;
        const installerItem = downloads.find((d) => d.id === "installer-windows" || d.is_installer);
        if (installerItem) {
          setReleaseInfo((prev) => ({
            ...prev,
            version: installerItem.version || prev.version,
            fileSize: installerItem.file_size || prev.fileSize,
            installerUrl: installerItem.download_url || prev.installerUrl,
            sha256: installerItem.sha256 || prev.sha256,
            releaseDate: installerItem.release_date || prev.releaseDate,
            directDownloadUrl: installerItem.direct_download_url || prev.directDownloadUrl,
            filename: installerItem.filename || prev.filename,
          }));
        }
      })
      .catch((err) => {
        console.warn("Could not fetch release metadata from licensing server:", err);
      });
    return () => {
      active = false;
    };
  }, [token]);

  if (!ready || !session) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-muted-foreground">
        <Loader2 className="mr-2 size-5 animate-spin" /> Verifying client authentication…
      </div>
    );
  }

  const r = releaseInfo;
  const hasInstaller = isValidInstallerUrl(r.installerUrl) || Boolean(r.directDownloadUrl);

  const handleDownloadClick = async () => {
    if (!token) return;
    try {
      setDownloading(true);
      // Record download request in the server audit log before starting delivery
      const record = await api.clientRecordDownloadRequest("installer-windows", token);
      toast.success("Download request recorded", {
        description: `Starting MediHisaab ${record.version || r.version} download…`,
      });

      // Stream binary with authentication token attached
      const downloadPath = record.download_url || "/api/v1/client/downloads/installer-windows/file";
      const fullDownloadUrl = buildAuthenticatedDownloadUrl(downloadPath, token);
      const filename = record.filename || r.filename || "MediHisaab-Setup-1.0.3.exe";

      const link = document.createElement("a");
      link.href = fullDownloadUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err: any) {
      toast.error(err.message || "Failed to record download request. Downloading from direct mirror…");
      const fallbackUrl = r.directDownloadUrl || "https://github.com/saurabhmaurya6746/Medihisaab/releases/download/v1.0.3/MediHisaab-Setup-1.0.3.exe";
      window.location.href = fallbackUrl;
    } finally {
      setDownloading(false);
    }
  };

  return (
    <section className="container-page max-w-4xl py-14 md:py-20">
      <p className="eyebrow">Signed in as {session.email}</p>
      <h1 className="mt-3 text-4xl font-bold">MediHisaab for Windows</h1>

      <div className="mt-8 rounded-lg border bg-card">
        <dl className="grid divide-y sm:grid-cols-3 sm:divide-x sm:divide-y-0">
          <div className="p-5">
            <dt className="text-xs text-muted-foreground">Version</dt>
            <dd className="mt-1 font-mono">{r.version ?? NOT_CONFIGURED}</dd>
          </div>
          <div className="p-5">
            <dt className="text-xs text-muted-foreground">File size</dt>
            <dd className="mt-1 font-mono">{r.fileSize ?? NOT_CONFIGURED}</dd>
          </div>
          <div className="p-5">
            <dt className="text-xs text-muted-foreground">Release date</dt>
            <dd className="mt-1 font-mono">{r.releaseDate ?? NOT_CONFIGURED}</dd>
          </div>
        </dl>
        {r.sha256 && (
          <div className="border-t p-5">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <ShieldCheck className="size-3.5 text-primary" />
              <span>Cryptographic Checksum (SHA-256)</span>
            </div>
            <p className="mt-1 break-all font-mono text-sm">{r.sha256}</p>
          </div>
        )}
        <div className="border-t p-5">
          {hasInstaller ? (
            <Button size="lg" onClick={handleDownloadClick} disabled={downloading}>
              {downloading ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Download className="size-4" />
              )}
              Download Windows Installer
            </Button>
          ) : (
            <div className="flex items-start gap-4 rounded-md bg-warning-surface p-4 text-warning">
              <PackageX className="mt-0.5 size-5 shrink-0" />
              <div>
                <p className="font-semibold">Windows installer binary not found</p>
                <p className="mt-1 text-sm">
                  The Windows installer binary is currently unavailable on this deployment.
                  Please contact support or check back soon.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="mt-10 grid gap-10 md:grid-cols-2">
        <div>
          <h2 className="text-xl font-semibold">Installation steps</h2>
          <ol className="mt-4 list-decimal space-y-2 pl-5 text-muted-foreground">
            <li>Run the installer on your billing computer.</li>
            <li>Follow the prompts and finish installation.</li>
            <li>Open MediHisaab and sign in with this account to automatically activate your license.</li>
            <li>Create your separate local administrator login for daily store operations.</li>
            <li>Choose a backup location (external drive or network share) before you start billing.</li>
          </ol>
        </div>
        {r.requirements && r.requirements.length > 0 && (
          <div>
            <h2 className="text-xl font-semibold">System requirements</h2>
            <ul className="mt-4 list-disc space-y-2 pl-5 text-muted-foreground">
              {r.requirements.map((q) => (
                <li key={q}>{q}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
      <p className="mt-10 text-sm text-muted-foreground">
        Need help? Visit{" "}
        <Link to="/support" className="text-primary hover:underline">
          Support
        </Link>{" "}
        or return to your{" "}
        <Link to="/client" className="text-primary hover:underline">
          client dashboard
        </Link>
        .
      </p>
    </section>
  );
}

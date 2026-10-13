import { Link } from "react-router-dom";
import { Cloud, Monitor } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageIntro } from "@/components/site/PageIntro";
import { usePageTitle } from "@/hooks/use-page-title";

const steps = [
  [
    "Create your MediHisaab account",
    "Register your pharmacy online. This account is used for licensing and downloads.",
  ],
  ["Download the Windows installer", "Sign in and download the installer from your account."],
  [
    "Install and sign in",
    "Install the application and sign in once with your online account to activate it.",
  ],
  [
    "Set up the pharmacy and local administrator",
    "Enter store details and create a local administrator for the desktop app.",
  ],
  [
    "Add medicines, suppliers, stock and staff",
    "Build your item list, add opening stock and create staff logins.",
  ],
  [
    "Begin billing",
    "Start billing at the counter. Configure additional counters if your plan supports them.",
  ],
  ["Set up regular local backups", "Choose a backup location and back up your data regularly."],
];

export function HowItWorksPage() {
  usePageTitle("How It Works — MediHisaab");

  return (
    <>
      <PageIntro eyebrow="How it works" title="From sign-up to your first bill">
        A step-by-step view of the intended setup journey for a medical store.
      </PageIntro>
      <section className="container-page grid gap-16 py-20 lg:grid-cols-[1.4fr_1fr]">
        <ol className="relative border-l-2 border-border pl-8">
          {steps.map(([t, d], i) => (
            <li key={t} className="relative pb-10 last:pb-0">
              <span className="absolute -left-[3.05rem] flex size-8 items-center justify-center rounded-full border-2 border-primary bg-card font-mono text-sm font-semibold text-primary">
                {i + 1}
              </span>
              <h2 className="text-lg font-semibold">{t}</h2>
              <p className="mt-1 text-muted-foreground">{d}</p>
            </li>
          ))}
        </ol>
        <aside className="space-y-4 self-start lg:sticky lg:top-24">
          <h2 className="text-xl font-bold">Two kinds of credentials</h2>
          <div className="rounded-lg border bg-card p-5">
            <Cloud className="size-5 text-primary" />
            <h3 className="mt-3 font-semibold">Online account</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Owner's email and password. Used for licensing, renewals and downloads on this
              website.
            </p>
          </div>
          <div className="rounded-lg border bg-card p-5">
            <Monitor className="size-5 text-primary" />
            <h3 className="mt-3 font-semibold">Local staff logins</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Created inside the desktop app for the administrator and staff. They are intended to
              stay on your computer.
            </p>
          </div>
          <p className="rounded-lg bg-surface p-5 text-sm text-secondary-foreground">
            Offline use: daily billing is designed to work without internet after activation.
            Activation and periodic license checks may require a connection. Final behaviour depends
            on the released product.
          </p>
          <Button asChild className="w-full">
            <Link to="/account?mode=signup">Create your account</Link>
          </Button>
        </aside>
      </section>
    </>
  );
}

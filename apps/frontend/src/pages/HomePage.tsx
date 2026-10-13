import { Link } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  CalendarClock,
  Download,
  HardDrive,
  ReceiptText,
  Store,
  WifiOff,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DashboardMockup,
  ExpiryMockup,
  ReceiptMockup,
  ReportMockup,
} from "@/components/site/Mockups";
import { usePageTitle } from "@/hooks/use-page-title";

const day = [
  { time: "9:00", task: "Open the counter and check items expiring this month" },
  { time: "11:30", task: "Bill walk-in customers by medicine name, salt or batch" },
  { time: "15:00", task: "Enter a supplier purchase invoice and update stock" },
  { time: "21:00", task: "Review the day's sales and take a local backup" },
];

export function HomePage() {
  usePageTitle("MediHisaab — Your pharmacy. Your stock. Your daily hisaab.");

  return (
    <>
      <section className="border-b bg-card">
        <div className="container-page grid items-center gap-12 py-16 md:py-24 lg:grid-cols-[1fr_1.15fr]">
          <div>
            <p className="eyebrow">Pharmacy software for Windows</p>
            <h1 className="mt-4 text-4xl font-extrabold leading-[1.08] md:text-6xl">
              Your pharmacy. Your stock. <span className="text-primary">Your daily hisaab.</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg text-muted-foreground">
              MediHisaab helps you manage pharmacy billing, medicine stock, expiry dates and
              everyday store records from your Windows computer.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button asChild size="lg">
                <Link to="/product">
                  Explore the Product <ArrowRight className="size-4" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link to="/account?mode=signup">Start Free Trial</Link>
              </Button>
            </div>
            <Link
              to="/download"
              className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
            >
              <Download className="size-4" /> Download for Windows
            </Link>
          </div>
          <DashboardMockup />
        </div>
      </section>

      <section className="container-page grid gap-12 py-20 md:grid-cols-[0.9fr_1.1fr] md:py-28">
        <div>
          <p className="eyebrow">Everyday operations</p>
          <h2 className="mt-3 text-3xl font-bold md:text-4xl">
            Built around how a medical store actually runs its day.
          </h2>
          <p className="mt-4 text-muted-foreground">
            From the morning expiry check to the night's closing figures, MediHisaab is meant to
            keep counter work and record keeping in one place.
          </p>
        </div>
        <ol className="ledger-lines rounded-lg border bg-card">
          {day.map((d) => (
            <li key={d.time} className="flex gap-6 border-b px-6 py-5 last:border-0">
              <span className="w-12 shrink-0 font-mono text-sm font-semibold text-primary">
                {d.time}
              </span>
              <span>{d.task}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="bg-surface py-20 md:py-28">
        <div className="container-page grid items-center gap-12 md:grid-cols-2">
          <ReceiptMockup />
          <div>
            <ReceiptText className="size-6 text-primary" />
            <h2 className="mt-4 text-3xl font-bold">Billing and receipts at the counter</h2>
            <p className="mt-4 text-muted-foreground">
              Search a medicine by name or salt, pick the batch, and save the bill. Receipts can be
              printed for the customer and kept for your records.
            </p>
            <ul className="mt-6 space-y-2 text-sm">
              <li>· Batch-wise billing with MRP and discount</li>
              <li>· Print receipts on your store printer</li>
              <li>· Find past bills when a customer returns</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="container-page grid gap-6 py-20 md:py-28 lg:grid-cols-2">
        <div className="rounded-lg border bg-card p-8">
          <CalendarClock className="size-6 text-primary" />
          <h2 className="mt-4 text-2xl font-bold">Stock and expiry tracking</h2>
          <p className="mt-3 text-muted-foreground">
            See what is running low and which batches expire soon, so you can return or sell them in
            time.
          </p>
          <div className="mt-6">
            <ExpiryMockup />
          </div>
        </div>
        <div className="rounded-lg border bg-card p-8">
          <BarChart3 className="size-6 text-primary" />
          <h2 className="mt-4 text-2xl font-bold">Reports and business records</h2>
          <p className="mt-3 text-muted-foreground">
            Daily sales, purchases and supplier records, organised so your accounts are easier to
            check.
          </p>
          <div className="mt-6">
            <ReportMockup />
          </div>
        </div>
      </section>

      <section className="bg-ink text-ink-foreground">
        <div className="container-page grid gap-10 py-20 md:grid-cols-3 md:py-24">
          <div className="md:col-span-1">
            <h2 className="text-3xl font-bold">Runs on your computer</h2>
            <p className="mt-4 opacity-80">
              MediHisaab is designed as a Windows desktop application, with your store records kept
              on your own machine.
            </p>
          </div>
          <div className="flex gap-4">
            <HardDrive className="size-6 shrink-0" />
            <div>
              <h3 className="font-semibold">Local records</h3>
              <p className="mt-1 text-sm opacity-80">
                Pharmacy data is intended to be stored locally. Regular backups remain your
                responsibility.
              </p>
            </div>
          </div>
          <div className="flex gap-4">
            <WifiOff className="size-6 shrink-0" />
            <div>
              <h3 className="font-semibold">Offline billing, by design</h3>
              <p className="mt-1 text-sm opacity-80">
                Day-to-day billing is intended to work without internet. Account sign-in and license
                checks may need a connection.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="container-page py-20 md:py-28">
        <h2 className="text-3xl font-bold">Getting started takes three steps</h2>
        <ol className="mt-10 grid gap-8 md:grid-cols-3">
          {[
            ["Create an account", "Register your pharmacy online to start the trial."],
            ["Download and install", "Install MediHisaab on your Windows billing computer."],
            ["Set up and start billing", "Add medicines and stock, then start billing."],
          ].map(([t, d], i) => (
            <li key={t} className="border-t-2 border-primary pt-5">
              <span className="font-mono text-sm text-primary">0{i + 1}</span>
              <h3 className="mt-2 text-lg font-semibold">{t}</h3>
              <p className="mt-1 text-muted-foreground">{d}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="container-page">
        <div className="grid gap-px overflow-hidden rounded-lg border bg-border md:grid-cols-3">
          {[
            {
              to: "/product",
              icon: Store,
              t: "See the product",
              d: "Workflows for billing, stock and records.",
            },
            {
              to: "/plans",
              icon: CalendarClock,
              t: "Plans & trial",
              d: "How the trial and license work.",
            },
            {
              to: "/account",
              icon: ArrowRight,
              t: "Create your account",
              d: "Register your pharmacy to begin.",
            },
          ].map((c) => (
            <Link
              key={c.t}
              to={c.to}
              className="group bg-card p-8 transition-colors hover:bg-surface"
            >
              <c.icon className="size-5 text-primary" />
              <h3 className="mt-4 font-semibold group-hover:text-primary">{c.t} →</h3>
              <p className="mt-1 text-sm text-muted-foreground">{c.d}</p>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}

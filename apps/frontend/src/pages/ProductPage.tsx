import { Link } from "react-router-dom";
import {
  Archive,
  Boxes,
  CalendarClock,
  MonitorSmartphone,
  Printer,
  ReceiptText,
  Truck,
  Users,
  BarChart3,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageIntro } from "@/components/site/PageIntro";
import {
  DashboardMockup,
  ExpiryMockup,
  ReceiptMockup,
  ReportMockup,
} from "@/components/site/Mockups";
import { usePageTitle } from "@/hooks/use-page-title";

export function ProductPage() {
  usePageTitle("Product — MediHisaab pharmacy software");

  return (
    <>
      <PageIntro eyebrow="Product" title="Practical tools for the pharmacy counter and back office">
        The capabilities below describe what MediHisaab is designed to support. Details may change
        as the product develops.
      </PageIntro>

      <section className="container-page grid items-center gap-12 py-20 lg:grid-cols-[1fr_1.3fr]">
        <div>
          <ReceiptText className="size-6 text-primary" />
          <h2 className="mt-4 text-3xl font-bold">Pharmacy billing</h2>
          <p className="mt-4 text-muted-foreground">
            Fast search by medicine name or salt, batch selection, discounts and GST-ready bill
            fields — designed for busy counters with a keyboard-first flow.
          </p>
        </div>
        <DashboardMockup />
      </section>

      <section className="border-y bg-card">
        <div className="container-page grid gap-0 md:grid-cols-3">
          {[
            {
              icon: Boxes,
              t: "Medicine inventory",
              d: "Keep item masters with pack size, MRP, HSN and reorder level. Stock adjusts as you bill and purchase.",
            },
            {
              icon: Truck,
              t: "Suppliers & purchases",
              d: "Record supplier invoices, track purchase history and see what you owe to each distributor.",
            },
            {
              icon: Users,
              t: "Staff management",
              d: "Create local staff logins with separate roles, so counter staff see only what they need.",
            },
          ].map((f, i) => (
            <div
              key={f.t}
              className={`py-12 md:px-8 ${i > 0 ? "border-t md:border-l md:border-t-0" : "md:pl-0"}`}
            >
              <f.icon className="size-6 text-primary" />
              <h2 className="mt-4 text-xl font-semibold">{f.t}</h2>
              <p className="mt-2 text-muted-foreground">{f.d}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="container-page grid items-center gap-12 py-20 lg:grid-cols-2">
        <ExpiryMockup />
        <div>
          <CalendarClock className="size-6 text-primary" />
          <h2 className="mt-4 text-3xl font-bold">Batch and expiry tracking</h2>
          <p className="mt-4 text-muted-foreground">
            Every purchase is stored batch-wise with its expiry date. Near-expiry lists help you
            plan returns to suppliers before stock becomes a loss.
          </p>
        </div>
      </section>

      <section className="bg-surface py-20">
        <div className="container-page grid items-center gap-12 lg:grid-cols-2">
          <div>
            <BarChart3 className="size-6 text-primary" />
            <h2 className="mt-4 text-3xl font-bold">Sales and business reports</h2>
            <p className="mt-4 text-muted-foreground">
              Daily, monthly and item-wise sales, purchase registers and stock valuation — the
              figures you check at closing time and share with your accountant.
            </p>
          </div>
          <ReportMockup />
        </div>
      </section>

      <section className="container-page py-20">
        <div className="grid gap-10 lg:grid-cols-[1fr_2fr]">
          <div>
            <ReceiptMockup />
          </div>
          <dl className="grid gap-8 sm:grid-cols-2">
            <div>
              <dt className="flex items-center gap-2 font-semibold">
                <Printer className="size-5 text-primary" /> Receipt printing
              </dt>
              <dd className="mt-2 text-muted-foreground">
                Print bills on thermal or A4/A5 printers connected to your computer.
              </dd>
            </div>
            <div>
              <dt className="flex items-center gap-2 font-semibold">
                <Archive className="size-5 text-primary" /> Data backup
              </dt>
              <dd className="mt-2 text-muted-foreground">
                Create local backups to another drive or USB. Keeping backups safe is the store's
                responsibility.
              </dd>
            </div>
            <div>
              <dt className="flex items-center gap-2 font-semibold">
                <MonitorSmartphone className="size-5 text-primary" /> Multiple counters
              </dt>
              <dd className="mt-2 text-muted-foreground">
                Additional billing counters on the same store network are planned, subject to your
                plan and final product support.
              </dd>
            </div>
            <div>
              <dt className="flex items-center gap-2 font-semibold">
                <Users className="size-5 text-primary" /> Local credentials
              </dt>
              <dd className="mt-2 text-muted-foreground">
                Staff sign in to the desktop app with local usernames, separate from your online
                account.
              </dd>
            </div>
          </dl>
        </div>
        <div className="mt-16 flex flex-wrap gap-3">
          <Button asChild size="lg">
            <Link to="/account?mode=signup">Start Free Trial</Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link to="/how-it-works">How it works</Link>
          </Button>
        </div>
      </section>
    </>
  );
}

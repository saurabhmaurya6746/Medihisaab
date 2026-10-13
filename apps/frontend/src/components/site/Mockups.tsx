import { AlertTriangle, Package, Printer, ReceiptText, Search } from "lucide-react";
import { MockupLabel } from "./PageIntro";

function Frame({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <figure className="overflow-hidden rounded-lg border bg-card shadow-[0_1px_0_var(--color-border),0_24px_48px_-28px_color-mix(in_oklab,var(--color-primary-deep)_35%,transparent)]">
      <div className="flex items-center justify-between border-b bg-muted px-3 py-2">
        <div className="flex items-center gap-1.5" aria-hidden>
          <span className="size-2.5 rounded-full bg-border" />
          <span className="size-2.5 rounded-full bg-border" />
          <span className="size-2.5 rounded-full bg-border" />
          <span className="ml-2 text-xs text-muted-foreground">{title}</span>
        </div>
        <MockupLabel />
      </div>
      {children}
    </figure>
  );
}

const rows = [
  { name: "Paracetamol 650 Tab", batch: "PC2411", exp: "08/27", qty: 2, rate: "30.40" },
  { name: "Amoxicillin 500 Cap", batch: "AX0925", exp: "03/27", qty: 1, rate: "98.00" },
  { name: "ORS Sachet 21g", batch: "OR1102", exp: "11/26", qty: 4, rate: "84.00" },
  { name: "Cetirizine 10 Tab", batch: "CT3307", exp: "01/28", qty: 1, rate: "18.50" },
];

export function DashboardMockup() {
  return (
    <Frame title="MediHisaab — Billing">
      <div className="grid md:grid-cols-[minmax(0,1fr)_12rem]">
        <div className="p-4">
          <div className="flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm text-muted-foreground">
            <Search className="size-4" /> Search medicine, salt or batch…
          </div>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[22rem] text-left text-sm">
              <thead className="text-xs text-muted-foreground">
                <tr className="border-b">
                  <th className="py-2 font-medium">Item</th>
                  <th className="font-medium">Batch</th>
                  <th className="font-medium">Exp</th>
                  <th className="text-right font-medium">Qty</th>
                  <th className="text-right font-medium">Amount</th>
                </tr>
              </thead>
              <tbody className="font-mono text-[13px]">
                {rows.map((r) => (
                  <tr key={r.batch} className="border-b last:border-0">
                    <td className="py-2 font-sans">{r.name}</td>
                    <td>{r.batch}</td>
                    <td>{r.exp}</td>
                    <td className="text-right">{r.qty}</td>
                    <td className="text-right">₹{r.rate}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <aside className="space-y-3 border-t bg-surface p-4 md:border-l md:border-t-0 min-w-0">
          <div className="rounded-md bg-card p-3">
            <p className="text-xs text-muted-foreground">Bill total</p>
            <p className="font-mono text-2xl font-semibold text-primary-deep">₹230.90</p>
          </div>
          <div className="flex items-start gap-2 rounded-md bg-warning-surface p-3 text-xs text-warning">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" /> 12 batches expire within 60 days
          </div>
          <div className="flex items-start gap-2 rounded-md bg-card p-3 text-xs text-muted-foreground">
            <Package className="mt-0.5 size-4 shrink-0" /> 5 items below reorder level
          </div>
          <div className="flex gap-2">
            <span className="inline-flex flex-1 items-center justify-center gap-1 rounded-md bg-primary py-2 text-xs font-medium text-primary-foreground">
              <Printer className="size-3.5" /> Save & print
            </span>
          </div>
        </aside>
      </div>
      <figcaption className="sr-only">
        Illustrative concept of a billing screen with demo values.
      </figcaption>
    </Frame>
  );
}

export function ReceiptMockup() {
  return (
    <div className="mx-auto w-full max-w-xs rounded-md border bg-card p-5 font-mono text-xs shadow-sm">
      <div className="flex items-center justify-between font-sans">
        <ReceiptText className="size-4 text-primary" />
        <MockupLabel />
      </div>
      <p className="mt-3 text-center font-sans text-sm font-semibold">Your Medical Store</p>
      <p className="text-center text-muted-foreground">Bill #000124 · Demo</p>
      <div className="my-3 border-t border-dashed" />
      {rows.slice(0, 3).map((r) => (
        <div key={r.batch} className="flex justify-between py-0.5">
          <span>
            {r.name.split(" ")[0]} ×{r.qty}
          </span>
          <span>₹{r.rate}</span>
        </div>
      ))}
      <div className="my-3 border-t border-dashed" />
      <div className="flex justify-between font-semibold">
        <span>Total</span>
        <span>₹212.40</span>
      </div>
    </div>
  );
}

export function ExpiryMockup() {
  const items = [
    {
      name: "Azithromycin 500",
      batch: "AZ221",
      days: 18,
      tone: "bg-destructive-surface text-destructive",
    },
    { name: "Vitamin D3 60K", batch: "VD118", days: 41, tone: "bg-warning-surface text-warning" },
    { name: "Pantoprazole 40", batch: "PN903", days: 57, tone: "bg-warning-surface text-warning" },
    {
      name: "Metformin 500",
      batch: "MT450",
      days: 212,
      tone: "bg-secondary text-secondary-foreground",
    },
  ];
  return (
    <Frame title="Expiry watch">
      <ul className="divide-y">
        {items.map((i) => (
          <li key={i.batch} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
            <div>
              <p className="font-medium">{i.name}</p>
              <p className="font-mono text-xs text-muted-foreground">Batch {i.batch}</p>
            </div>
            <span className={`rounded px-2 py-1 text-xs font-medium ${i.tone}`}>{i.days} days</span>
          </li>
        ))}
      </ul>
    </Frame>
  );
}

export function ReportMockup() {
  const bars = [42, 58, 51, 67, 73, 61, 80];
  return (
    <Frame title="Daily sales">
      <div className="p-4">
        <div className="flex h-36 items-end gap-2" aria-hidden>
          {bars.map((b, i) => (
            <div key={i} className="flex-1 rounded-t bg-primary/80" style={{ height: `${b}%` }} />
          ))}
        </div>
        <div className="mt-2 flex justify-between text-[11px] text-muted-foreground">
          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
            <span key={d}>{d}</span>
          ))}
        </div>
      </div>
    </Frame>
  );
}

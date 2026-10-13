import { Link } from "react-router-dom";
import { Check } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { PageIntro } from "@/components/site/PageIntro";
import { pricingConfig } from "@/config/site";
import { api, type ClientPlan } from "@/lib/api";
import { usePageTitle } from "@/hooks/use-page-title";

function formatPrice(price: number | null, period: string | null) {
  if (price == null) return null;
  return `${new Intl.NumberFormat("en-IN", { style: "currency", currency: pricingConfig.currency, maximumFractionDigits: 0 }).format(price)}${period ? ` / ${period}` : ""}`;
}

export function PlansPage() {
  usePageTitle("Plans & Trial — MediHisaab");

  const [livePlans, setLivePlans] = useState<ClientPlan[]>([]);

  useEffect(() => {
    api.clientGetPlans().then(setLivePlans).catch(() => {});
  }, []);

  const displayPlans = livePlans.length > 0
    ? livePlans.map((lp) => ({
        id: lp.plan_code,
        name: lp.name,
        description: lp.description,
        price: lp.price / 100,
        period: lp.billing_period.toLowerCase(),
      }))
    : pricingConfig.plans;

  const trial = pricingConfig.trialDays
    ? `${pricingConfig.trialDays}-day free trial`
    : "Trial duration configured by the provider";

  return (
    <>
      <PageIntro eyebrow="Plans & trial" title="Try it in your store before you decide">
        Start with a free trial. When you're ready, request a license for your store from your
        account.
      </PageIntro>

      <section className="container-page py-16">
        <div className="rounded-lg border-2 border-primary bg-card p-8 md:flex md:items-center md:justify-between md:gap-8">
          <div>
            <p className="eyebrow">Free trial</p>
            <h2 className="mt-2 text-2xl font-bold">{trial}</h2>
            <p className="mt-2 max-w-xl text-muted-foreground">
              The trial starts when you create a pharmacy account. No payment details are requested
              on this website.
            </p>
          </div>
          <Button asChild size="lg" className="mt-6 md:mt-0">
            <Link to="/account?mode=signup">Create account</Link>
          </Button>
        </div>

        <div className="mt-8 grid gap-6 md:grid-cols-2">
          {displayPlans.map((p) => {
            const price = formatPrice(p.price, p.period);
            return (
              <article key={p.id} className="flex flex-col rounded-lg border bg-card p-8">
                <h3 className="text-xl font-semibold">{p.name}</h3>
                <p className="mt-2 text-muted-foreground">{p.description}</p>
                <p
                  className={`mt-6 ${price ? "text-3xl font-bold" : "text-sm text-muted-foreground"}`}
                >
                  {price ?? "Pricing is shared by the provider on request."}
                </p>
                <Button asChild variant="outline" className="mt-8 self-start">
                  <Link to="/support">Ask about this plan</Link>
                </Button>
              </article>
            );
          })}
        </div>
      </section>

      <section className="border-t bg-card">
        <div className="container-page grid gap-12 py-16 md:grid-cols-2">
          <div>
            <h2 className="text-2xl font-bold">License status, explained</h2>
            <dl className="mt-6 space-y-4">
              {[
                ["Active trial", "You can use the software while the trial is running."],
                ["Active license", "Your store has a valid license for the licensed period."],
                ["Expiring soon", "Your license ends shortly. A renewal request is recommended."],
                ["Renewal pending", "Your request has been received and is awaiting review."],
                ["Expired", "The license period has ended until a renewal is approved."],
              ].map(([t, d]) => (
                <div key={t} className="flex gap-3">
                  <Check className="mt-0.5 size-5 shrink-0 text-primary" />
                  <div>
                    <dt className="font-medium">{t}</dt>
                    <dd className="text-sm text-muted-foreground">{d}</dd>
                  </div>
                </div>
              ))}
            </dl>
          </div>
          <div>
            <h2 className="text-2xl font-bold">Renewal process</h2>
            <ol className="mt-6 space-y-4">
              {[
                "Sign in to your account dashboard.",
                "Open the renewal request form and choose a plan.",
                "Add a payment reference if you've already paid the provider.",
                "The provider reviews the request and updates your license.",
              ].map((s, i) => (
                <li key={s} className="flex gap-4">
                  <span className="font-mono text-sm font-semibold text-primary">0{i + 1}</span>
                  <span>{s}</span>
                </li>
              ))}
            </ol>
            <p className="mt-6 text-sm text-muted-foreground">
              Renewals are not charged automatically. Grace periods and plan limits are set by the
              provider.
            </p>
          </div>
        </div>
      </section>
    </>
  );
}

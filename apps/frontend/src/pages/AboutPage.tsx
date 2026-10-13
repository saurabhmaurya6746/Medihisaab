import { Link } from "react-router-dom";
import { PageIntro } from "@/components/site/PageIntro";
import { usePageTitle } from "@/hooks/use-page-title";

export function AboutPage() {
  usePageTitle("About — MediHisaab");

  return (
    <>
      <PageIntro eyebrow="About" title="Software for the work behind the counter" />
      <article className="container-page max-w-3xl py-16 text-lg leading-relaxed">
        <p className="text-2xl font-medium leading-snug">
          A medical store runs on hundreds of small, careful entries every day — bills, batches,
          expiry dates, supplier invoices and the closing hisaab.
        </p>
        <p className="mt-8 text-muted-foreground">
          MediHisaab is being built to keep those entries in one place on the store's own Windows
          computer. The aim is simple: make billing quicker at the counter, make stock and expiry
          easier to see, and make the day's figures easier to trust.
        </p>
        <h2 className="mt-12 text-2xl font-bold">What we focus on</h2>
        <dl className="mt-6 space-y-6">
          <div className="border-l-2 border-primary pl-5">
            <dt className="font-semibold">Practical usability</dt>
            <dd className="mt-1 text-base text-muted-foreground">
              Screens that make sense to pharmacy owners and counter staff, with plain language and
              keyboard-friendly flows.
            </dd>
          </div>
          <div className="border-l-2 border-primary pl-5">
            <dt className="font-semibold">Everyday pharmacy work</dt>
            <dd className="mt-1 text-base text-muted-foreground">
              Batch-wise stock, expiry tracking, purchase entry and daily reports — the tasks that
              repeat every day.
            </dd>
          </div>
          <div className="border-l-2 border-primary pl-5">
            <dt className="font-semibold">Your records, your machine</dt>
            <dd className="mt-1 text-base text-muted-foreground">
              A desktop application where store data is intended to stay local, with backups under
              your control.
            </dd>
          </div>
        </dl>
        <p className="mt-12 text-base text-muted-foreground">
          Want to see how it fits your store? Read{" "}
          <Link to="/how-it-works" className="text-primary hover:underline">
            how it works
          </Link>{" "}
          or{" "}
          <Link to="/account?mode=signup" className="text-primary hover:underline">
            start a trial
          </Link>
          .
        </p>
      </article>
    </>
  );
}

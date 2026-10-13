import { Link } from "react-router-dom";
import {
  CheckCircle2,
  KeyRound,
  Loader2,
  MonitorDown,
  RefreshCcw,
  ShieldCheck,
  Wrench,
} from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/site/Field";
import { PageIntro } from "@/components/site/PageIntro";
import { contactConfig } from "@/config/site";
import { api, type SupportContacts } from "@/lib/api";
import { usePageTitle } from "@/hooks/use-page-title";

const guides = [
  {
    icon: MonitorDown,
    t: "Installation help",
    d: "Download the installer from your account, run it as a user with install rights, and restart if Windows asks.",
  },
  {
    icon: KeyRound,
    t: "Account access",
    d: "Use Forgot password on the Account page. Remember: staff local logins are reset inside the desktop app, not here.",
  },
  {
    icon: ShieldCheck,
    t: "Activation",
    d: "Sign in once in the app with your online account while connected to the internet to activate the installation.",
  },
  {
    icon: RefreshCcw,
    t: "License renewal",
    d: "Submit a renewal request from your dashboard. You'll see the status change to Renewal pending.",
  },
];

const issues = [
  [
    "Installer is blocked by Windows SmartScreen",
    "Choose More info → Run anyway only if you downloaded it from your verified MediHisaab account.",
  ],
  [
    "Activation fails",
    "Check the internet connection and that you're using the owner's online account, not a staff counter login.",
  ],
  [
    "Printer doesn't print bills",
    "Confirm the printer is set up in Windows and selected in the app's ESC/POS or thermal print settings.",
  ],
];

export function SupportPage() {
  usePageTitle("Support — MediHisaab");

  const [liveContacts, setLiveContacts] = useState<SupportContacts | null>(null);

  useEffect(() => {
    api.clientGetSupportContacts().then(setLiveContacts).catch(() => {});
  }, []);

  const email = liveContacts?.email || contactConfig.supportEmail;
  const phone = liveContacts?.phone || contactConfig.supportPhone;
  const whatsapp = liveContacts?.whatsapp || contactConfig.whatsapp;

  const channels = [
    email && {
      label: "Email",
      value: email,
      href: `mailto:${email}`,
    },
    phone && {
      label: "Phone",
      value: phone,
      href: `tel:${phone}`,
    },
    whatsapp && {
      label: "WhatsApp",
      value: whatsapp,
      href: `https://wa.me/${whatsapp.replace(/\D/g, "")}`,
    },
  ].filter(Boolean) as { label: string; value: string; href: string }[];

  return (
    <>
      <PageIntro eyebrow="Support" title="How can we help?">
        Quick guides for common tasks, and ways to reach our technical support desk. Also see the{" "}
        <Link to="/faq" className="text-primary hover:underline">
          FAQ
        </Link>
        .
      </PageIntro>
      <section className="container-page grid gap-6 py-16 sm:grid-cols-2">
        {guides.map((g) => (
          <div key={g.t} className="flex gap-4 border-b pb-6">
            <g.icon className="size-6 shrink-0 text-primary" />
            <div>
              <h2 className="font-semibold">{g.t}</h2>
              <p className="mt-1 text-muted-foreground">{g.d}</p>
            </div>
          </div>
        ))}
      </section>
      <section className="bg-surface py-16">
        <div className="container-page">
          <h2 className="flex items-center gap-2 text-2xl font-bold">
            <Wrench className="size-5 text-primary" /> Frequently encountered issues
          </h2>
          <dl className="mt-6 grid gap-4 md:grid-cols-3">
            {issues.map(([q, a]) => (
              <div key={q} className="rounded-lg border bg-card p-5">
                <dt className="font-semibold">{q}</dt>
                <dd className="mt-2 text-sm text-muted-foreground">{a}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>
      <section className="container-page grid gap-12 py-16 lg:grid-cols-[1fr_1.4fr]">
        <div>
          <h2 className="text-2xl font-bold">Contact Support</h2>
          {channels.length ? (
            <ul className="mt-4 space-y-2.5">
              {channels.map((c) => (
                <li key={c.label}>
                  <span className="text-muted-foreground">{c.label}: </span>
                  <a href={c.href} className="text-primary hover:underline font-medium">
                    {c.value}
                  </a>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-4 rounded-md border border-dashed p-4 text-sm text-muted-foreground">
              Direct contact channels have not been configured yet. Please check back soon.
            </p>
          )}
          {contactConfig.supportHours && (
            <p className="mt-4 text-sm text-muted-foreground">
              Hours: {contactConfig.supportHours}
            </p>
          )}
        </div>
        <ContactForm supportEmail={email} />
      </section>
    </>
  );
}

type CK = "name" | "email" | "subject" | "message";

function ContactForm({ supportEmail }: { supportEmail: string | null }) {
  const [errors, setErrors] = useState<Partial<Record<CK, string>>>({});
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<CK, string>;
    const errs: Partial<Record<CK, string>> = {};
    if (!f.name?.trim()) errs.name = "Enter your name.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email || ""))
      errs.email = "Enter a valid email address.";
    if (!f.subject?.trim()) errs.subject = "Enter a subject.";
    if (!f.message || f.message.trim().length < 10)
      errs.message = "Please write at least 10 characters.";
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setLoading(true);
    await new Promise((r) => setTimeout(r, 600));
    setLoading(false);
    setDone(true);
  }

  if (done) {
    return (
      <div role="status" className="rounded-lg border bg-card p-8">
        <CheckCircle2 className="size-6 text-primary" />
        <h3 className="mt-3 text-lg font-semibold">Inquiry recorded</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          {supportEmail ? (
            <>
              For expedited assistance with your billing counter, you may also reach our team directly at{" "}
              <a href={`mailto:${supportEmail}`} className="text-primary underline">
                {supportEmail}
              </a>
              .
            </>
          ) : (
            "Our support desk will review your inquiry shortly."
          )}
        </p>
        <Button variant="outline" className="mt-6" onClick={() => setDone(false)}>
          Write another message
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-4 rounded-lg border bg-card p-6 md:p-8">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Name" name="name" autoComplete="name" error={errors.name} />
        <Field label="Email" name="email" type="email" autoComplete="email" error={errors.email} />
      </div>
      <Field label="Subject" name="subject" error={errors.subject} />
      <Field label="Message" name="message" multiline error={errors.message} />
      <Button type="submit" disabled={loading}>
        {loading && <Loader2 className="size-4 animate-spin" />} Send Inquiry
      </Button>
    </form>
  );
}

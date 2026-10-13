import { Link } from "react-router-dom";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { PageIntro } from "@/components/site/PageIntro";
import { usePageTitle } from "@/hooks/use-page-title";

const faqs = [
  [
    "How do I install MediHisaab?",
    "Sign in to your account, open the Download page and run the Windows installer on your billing computer once a release is published. Then sign in to activate.",
  ],
  [
    "How do I create an account?",
    "Use Create Account on the Account page and enter your pharmacy name, owner's name, email, phone and a password.",
  ],
  [
    "How does license activation work?",
    "After installing, you sign in once with your online account. The application is intended to link that installation to your account's license.",
  ],
  [
    "Is an internet connection required?",
    "A connection is expected for account sign-in, activation and periodic license checks. Exact requirements depend on the final release.",
  ],
  [
    "Can I continue billing offline?",
    "Daily billing is designed to work offline after activation. Please confirm this behaviour with the released version before relying on it.",
  ],
  [
    "What happens when the trial expires?",
    "The license status changes to expired. You can submit a renewal request from your dashboard. Access rules after expiry are set by the provider.",
  ],
  [
    "How do I request a renewal?",
    "Sign in, open your dashboard and use the renewal request form. Add a payment reference if you have one.",
  ],
  [
    "How do I back up pharmacy data?",
    "The desktop app is intended to include a local backup option. Save backups to a separate drive or USB and keep them safe.",
  ],
  [
    "Can I use multiple counters?",
    "Multiple counters are planned depending on your plan and final product support. Ask support for current availability.",
  ],
  [
    "Are staff credentials separate from account credentials?",
    "Yes. Your online account is for licensing and downloads; staff use separate local logins created inside the desktop app.",
  ],
  ["Where can I get support?", "Visit the Support page for guides and a contact form."],
];

export function FaqPage() {
  usePageTitle("FAQ — MediHisaab");

  return (
    <>
      <PageIntro eyebrow="FAQ" title="Frequently asked questions" />
      <section className="container-page max-w-3xl py-12">
        <Accordion type="single" collapsible className="rounded-lg border bg-card px-6">
          {faqs.map(([q, a], i) => (
            <AccordionItem key={q} value={`q${i}`}>
              <AccordionTrigger className="text-left text-base">{q}</AccordionTrigger>
              <AccordionContent className="text-muted-foreground">{a}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
        <p className="mt-8 text-sm text-muted-foreground">
          Still have a question?{" "}
          <Link to="/support" className="text-primary hover:underline">
            Contact support
          </Link>
          .
        </p>
      </section>
    </>
  );
}

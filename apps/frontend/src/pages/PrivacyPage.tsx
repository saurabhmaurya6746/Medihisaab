import { PageIntro } from "@/components/site/PageIntro";
import { usePageTitle } from "@/hooks/use-page-title";

const sections = [
  [
    "account",
    "Account information",
    "When you create an account, we intend to collect the pharmacy name, owner's name, email address and phone number to identify your account and contact you about it.",
  ],
  [
    "licensing",
    "Licensing information",
    "To activate and verify a license, the application may send license-related details such as an account identifier and installation details. Exact fields will be documented with the released product.",
  ],
  [
    "renewals",
    "Renewal requests",
    "Renewal requests may include the requested plan, an optional payment reference and notes you provide. These are used to process the renewal.",
  ],
  [
    "local",
    "Application data stored locally",
    "Pharmacy records such as bills, stock, suppliers and staff logins are intended to be stored on your computer by the desktop application.",
  ],
  [
    "backup",
    "Backup responsibilities",
    "The store is responsible for creating and safely keeping backups of local data. Lost local data may not be recoverable by the provider.",
  ],
  [
    "support",
    "Support communications",
    "If you contact support, the details you share (name, email and message) are used to respond to your request.",
  ],
] as const;

export function PrivacyPage() {
  usePageTitle("Privacy — MediHisaab");

  return (
    <>
      <PageIntro eyebrow="Privacy" title="Privacy information">
        <span className="mt-2 block rounded-md bg-warning-surface px-4 py-3 text-sm text-warning">
          Draft: this page must be verified against the final product implementation and actual data
          practices before publication.
        </span>
      </PageIntro>
      <div className="container-page grid gap-12 py-16 lg:grid-cols-[14rem_1fr]">
        <nav aria-label="On this page" className="hidden lg:block">
          <ul className="sticky top-24 space-y-2 text-sm">
            {sections.map(([id, t]) => (
              <li key={id}>
                <a href={`#${id}`} className="text-muted-foreground hover:text-foreground">
                  {t}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <div className="max-w-2xl space-y-10">
          {sections.map(([id, t, d]) => (
            <section key={id} id={id} className="scroll-mt-24">
              <h2 className="text-xl font-semibold">{t}</h2>
              <p className="mt-3 leading-relaxed text-muted-foreground">{d}</p>
            </section>
          ))}
        </div>
      </div>
    </>
  );
}

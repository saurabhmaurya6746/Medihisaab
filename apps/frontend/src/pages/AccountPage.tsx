import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/site/Field";
import { createAccount, safeNext, signIn, type Role } from "@/lib/auth";
import { usePageTitle } from "@/hooks/use-page-title";

const emailOk = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim());

export function AccountPage() {
  usePageTitle("Sign in or create an account — MediHisaab");

  const [searchParams] = useSearchParams();
  const rawMode = searchParams.get("mode");
  const mode = rawMode === "signup" ? "signup" : "signin";
  const next = searchParams.get("next") ?? undefined;
  const navigate = useNavigate();
  const target = safeNext(next);

  const go = (role: Role) => {
    if (target) {
      navigate(target);
      return;
    }
    if (role === "admin") {
      navigate("/admin");
    } else {
      navigate("/client");
    }
  };

  return (
    <section className="container-page grid gap-12 py-14 md:py-20 lg:grid-cols-[1fr_28rem]">
      <div className="hidden lg:block">
        <p className="eyebrow">MediHisaab account</p>
        <h1 className="mt-3 text-4xl font-bold">
          {mode === "signup" ? "Register your pharmacy" : "Welcome back"}
        </h1>
        <p className="mt-4 max-w-md text-muted-foreground">
          This online account is for licensing, renewals and downloads. Your counter staff will use
          separate local logins inside the desktop application.
        </p>
        {target === "/download" && (
          <p className="mt-6 rounded-md bg-surface p-4 text-sm text-secondary-foreground">
            Sign in to continue to the Windows installer download.
          </p>
        )}
      </div>
      <div className="rounded-lg border bg-card p-6 md:p-8">
        <div
          role="tablist"
          aria-label="Account mode"
          className="grid grid-cols-2 rounded-md bg-muted p-1"
        >
          {(["signin", "signup"] as const).map((m) => (
            <Link
              key={m}
              role="tab"
              aria-selected={mode === m}
              to={`/account?mode=${m}${next ? `&next=${encodeURIComponent(next)}` : ""}`}
              className={`rounded px-3 py-2 text-center text-sm font-medium ${mode === m ? "bg-card shadow-sm" : "text-muted-foreground"}`}
            >
              {m === "signin" ? "Sign In" : "Create Account"}
            </Link>
          ))}
        </div>
        <h1 className="mt-6 text-2xl font-bold lg:hidden">
          {mode === "signup" ? "Register your pharmacy" : "Welcome back"}
        </h1>
        {mode === "signup" ? <SignUp onDone={go} /> : <SignIn onDone={go} next={next} />}
      </div>
    </section>
  );
}

function SignIn({
  onDone,
  next,
}: {
  onDone: (role: Role) => void | Promise<void>;
  next?: string | undefined;
}) {
  const [errors, setErrors] = useState<Partial<Record<"email" | "password", string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const email = String(f.get("email") || "");
    const password = String(f.get("password") || "");
    const errs: Partial<Record<"email" | "password", string>> = {};
    if (!email) errs.email = "Enter your email address.";
    else if (!emailOk(email)) errs.email = "Enter a valid email address.";
    if (!password) errs.password = "Enter your password.";
    setErrors(errs);
    setFormError(null);
    if (Object.keys(errs).length) return;
    setLoading(true);
    try {
      const s = await signIn(email, password);
      toast.success("Signed in successfully");
      onDone(s.role);
    } catch (err) {
      setFormError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function forgot() {
    toast.info("Password Reset Assistance", {
      description:
        "Please contact vendor support directly with your registered pharmacy name and drug license details to reset your account credentials.",
    });
  }

  return (
    <form onSubmit={submit} noValidate className="mt-6 space-y-4">
      {formError && (
        <p
          role="alert"
          className="rounded-md bg-destructive-surface px-3 py-2 text-sm text-destructive"
        >
          {formError}
        </p>
      )}
      <Field
        label="Email address"
        name="email"
        type="email"
        autoComplete="email"
        error={errors.email}
      />
      <Field
        label="Password"
        name="password"
        type="password"
        autoComplete="current-password"
        error={errors.password}
      />
      <div className="flex justify-end">
        <button
          type="button"
          onClick={forgot}
          className="text-sm font-medium text-primary hover:underline"
        >
          Forgot password?
        </button>
      </div>
      <Button type="submit" className="w-full" disabled={loading}>
        {loading && <Loader2 className="size-4 animate-spin" />} Sign In
      </Button>
      <p className="text-center text-sm text-muted-foreground">
        New to MediHisaab?{" "}
        <Link
          to={`/account?mode=signup${next ? `&next=${encodeURIComponent(next)}` : ""}`}
          className="font-medium text-primary hover:underline"
        >
          Create Account
        </Link>
      </p>
    </form>
  );
}

type SignUpKey = "pharmacyName" | "ownerName" | "email" | "phone" | "password" | "confirm";

function SignUp({ onDone }: { onDone: (role: Role) => void | Promise<void> }) {
  const [errors, setErrors] = useState<Partial<Record<SignUpKey, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget)) as Record<SignUpKey, string>;
    const errs: Partial<Record<SignUpKey, string>> = {};
    if (!f.pharmacyName?.trim()) errs.pharmacyName = "Enter your pharmacy name.";
    if (!f.ownerName?.trim()) errs.ownerName = "Enter the owner's name.";
    if (!f.email) errs.email = "Enter your email address.";
    else if (!emailOk(f.email)) errs.email = "Enter a valid email address.";
    if (!f.phone?.trim()) errs.phone = "Enter a phone number.";
    else if (!/^[+\d][\d\s-]{7,15}$/.test(f.phone.trim()))
      errs.phone = "Enter a valid phone number (at least 7 digits).";
    if (!f.password) errs.password = "Create a password.";
    else if (f.password.length < 8) errs.password = "Password must be at least 8 characters.";
    if (f.confirm !== f.password) errs.confirm = "Passwords do not match.";
    setErrors(errs);
    setFormError(null);
    if (Object.keys(errs).length) return;
    setLoading(true);
    try {
      const s = await createAccount({
        email: f.email,
        password: f.password,
        pharmacyName: f.pharmacyName.trim(),
        ownerName: f.ownerName.trim(),
        phone: f.phone.trim(),
      });
      toast.success("Pharmacy account created!", {
        description: "Your evaluation trial is active and your license has been generated.",
      });
      onDone(s.role);
    } catch (err) {
      setFormError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="mt-6 space-y-4">
      {formError && (
        <p
          role="alert"
          className="rounded-md bg-destructive-surface px-3 py-2 text-sm text-destructive"
        >
          {formError}
        </p>
      )}
      <Field
        label="Pharmacy name"
        name="pharmacyName"
        autoComplete="organization"
        error={errors.pharmacyName}
      />
      <Field label="Owner's name" name="ownerName" autoComplete="name" error={errors.ownerName} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="Email address"
          name="email"
          type="email"
          autoComplete="email"
          error={errors.email}
        />
        <Field
          label="Phone number"
          name="phone"
          type="tel"
          autoComplete="tel"
          error={errors.phone}
        />
      </div>
      <Field
        label="Password"
        name="password"
        type="password"
        autoComplete="new-password"
        error={errors.password}
        hint="At least 8 characters."
      />
      <Field
        label="Confirm password"
        name="confirm"
        type="password"
        autoComplete="new-password"
        error={errors.confirm}
      />
      <Button type="submit" className="w-full" disabled={loading}>
        {loading && <Loader2 className="size-4 animate-spin" />} Create Pharmacy Account
      </Button>
    </form>
  );
}

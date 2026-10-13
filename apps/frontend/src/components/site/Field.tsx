import { Eye, EyeOff } from "lucide-react";
import { useState, type InputHTMLAttributes } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  name: string;
  error?: string | undefined;
  hint?: string | undefined;
  multiline?: boolean;
};

export function Field({ label, name, error, hint, multiline, type, ...rest }: Props) {
  const [show, setShow] = useState(false);
  const id = `f-${name}`;
  const describedBy = error ? `${id}-err` : hint ? `${id}-hint` : undefined;
  const isPassword = type === "password";
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <div className="relative">
        {multiline ? (
          <Textarea
            id={id}
            name={name}
            aria-invalid={!!error}
            aria-describedby={describedBy}
            rows={5}
            {...(rest as unknown as React.TextareaHTMLAttributes<HTMLTextAreaElement>)}
          />
        ) : (
          <Input
            id={id}
            name={name}
            type={isPassword && show ? "text" : type}
            aria-invalid={!!error}
            aria-describedby={describedBy}
            className={isPassword ? "pr-10" : undefined}
            {...rest}
          />
        )}
        {isPassword && (
          <button
            type="button"
            onClick={() => setShow((s) => !s)}
            className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-muted-foreground hover:text-foreground"
            aria-label={show ? "Hide password" : "Show password"}
          >
            {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        )}
      </div>
      {error ? (
        <p id={`${id}-err`} className="text-sm text-destructive">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export function DemoNotice({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-md border border-dashed bg-muted px-3 py-2 text-xs text-muted-foreground">
      {children}
    </p>
  );
}

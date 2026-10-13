import { Link } from "react-router-dom";
import { usePageTitle } from "@/hooks/use-page-title";

export function NotFoundPage() {
  usePageTitle("Page Not Found — MediHisaab");

  return (
    <div className="flex min-h-[60vh] items-center justify-center px-4">
      <div className="max-w-md text-center">
        <p className="eyebrow">404</p>
        <h1 className="mt-2 text-3xl font-bold">Page not found</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <Link
          to="/"
          className="mt-6 inline-flex rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary-deep"
        >
          Go home
        </Link>
      </div>
    </div>
  );
}

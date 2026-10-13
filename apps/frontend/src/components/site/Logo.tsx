import { useState } from "react";
import { Link } from "react-router-dom";
import logo from "@/assets/medihisaab-horizontal.png.asset.json";

export function Logo({ className = "h-8" }: { className?: string }) {
  const [imgError, setImgError] = useState(false);

  return (
    <Link to="/" aria-label="MediHisaab home" className="inline-flex shrink-0 items-center gap-2">
      {!imgError ? (
        <img
          src={logo.url}
          alt="MediHisaab"
          className={`${className} w-auto`}
          width={1480}
          height={240}
          onError={() => setImgError(true)}
        />
      ) : (
        <span className="flex items-center gap-2 text-xl font-bold tracking-tight text-primary">
          <img src="/favicon.png" alt="" className="size-7" />
          <span>
            Medi<span className="text-foreground">Hisaab</span>
          </span>
        </span>
      )}
    </Link>
  );
}

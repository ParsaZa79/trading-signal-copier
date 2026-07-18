import { Suspense } from "react";
import { CopyTradingClient } from "./copy-trading-client";

export default function CopyTradingPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[60vh] items-center justify-center text-sm text-text-muted">
          Opening copy trading…
        </div>
      }
    >
      <CopyTradingClient />
    </Suspense>
  );
}

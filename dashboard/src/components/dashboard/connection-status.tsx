"use client";

import { cn } from "@/lib/utils";
import { Wifi, WifiOff, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ConnectionStatusProps {
  isConnected: boolean;
  error: string | null;
  onReconnect: () => void;
}

export function ConnectionStatus({
  isConnected,
  error,
  onReconnect,
}: ConnectionStatusProps) {
  if (isConnected && !error) return null;

  return (
    <div
      className={cn(
        "flex items-center justify-between p-4 rounded-xl border mb-6",
        isConnected
          ? "bg-warning/10 border-warning/20"
          : "bg-danger/10 border-danger/20"
      )}
    >
      <div className="flex items-center gap-3">
        {isConnected ? (
          <Wifi className="w-5 h-5 text-warning" />
        ) : (
          <WifiOff className="w-5 h-5 text-danger" />
        )}
        <div>
          <p
            className={cn(
              "text-sm font-medium",
              isConnected ? "text-warning" : "text-danger"
            )}
          >
            {isConnected ? "Connection issue" : "Disconnected"}
          </p>
          <p className="text-xs text-text-muted">
            {error || "Unable to connect to trading server"}
          </p>
        </div>
      </div>
      <Button size="sm" variant="outline" onClick={onReconnect}>
        <RefreshCw className="w-4 h-4 mr-2" />
        Reconnect
      </Button>
    </div>
  );
}

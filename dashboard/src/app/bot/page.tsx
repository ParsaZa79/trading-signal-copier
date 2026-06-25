"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  getBotStatus,
  startBot,
  stopBot,
  getBotConfig,
  getTrackedPositions,
  clearTrackedPositions,
} from "@/lib/api";
import { API_URL } from "@/lib/constants";
import {
  Play,
  Square,
  RefreshCw,
  Trash2,
  Loader2,
  Clock,
  Zap,
  Server,
  Activity,
  AlertCircle,
  CheckCircle,
  Copy,
  Check,
} from "lucide-react";
import { PageContainer, AnimatedSection } from "@/components/motion";
import {
  PageHeader,
  PageLoading,
  SectionPanel,
  PanelHeader,
  PanelBody,
  TerminalPanel,
  EmptyState,
} from "@/components/layout";
import { useDashboard } from "@/components/layout/dashboard-layout";
import { MetricCard } from "@/components/dashboard/metric-card";
import { SymbolCell } from "@/components/dashboard/symbol-icon";
import { buildAuthenticatedWsUrl } from "@/lib/auth-storage";
import type { TrackedPosition } from "@/types";

const IS_MACOS = typeof window !== "undefined" && navigator.platform.includes("Mac");

type BotStatusType = "stopped" | "starting" | "running" | "stopping" | "error";

export default function BotControlPage() {
  const { session } = useDashboard();
  const [status, setStatus] = useState<BotStatusType>("stopped");
  const [pid, setPid] = useState<number | undefined>();
  const [startedAt, setStartedAt] = useState<string | undefined>();
  const [error, setError] = useState<string | undefined>();
  const [isLoading, setIsLoading] = useState(true);
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);

  // Options
  const [writeEnvOnStart, setWriteEnvOnStart] = useState(false);
  const [preventSleep, setPreventSleep] = useState(IS_MACOS);

  // Positions
  const [positions, setPositions] = useState<TrackedPosition[]>([]);
  const [positionsStats, setPositionsStats] = useState({ total: 0, open: 0, closed: 0 });

  // Log output
  const [logs, setLogs] = useState<Array<{ id: string; level: string; message: string; timestamp: string }>>([]);
  const logEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [copied, setCopied] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await getBotStatus();
      if (res.success) {
        setStatus(res.status);
        setPid(res.pid);
        setStartedAt(res.started_at);
        setError(res.error);
      }
    } catch (err) {
      console.error("Failed to fetch bot status:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchPositions = useCallback(async () => {
    try {
      const res = await getTrackedPositions();
      if (res.success) {
        setPositions(res.positions as TrackedPosition[]);
        setPositionsStats({ total: res.total, open: res.open, closed: res.closed });
      }
    } catch (err) {
      console.error("Failed to fetch positions:", err);
    }
  }, []);

  useEffect(() => {
    setIsLoading(true);
    fetchStatus();
    fetchPositions();

    // Poll status every 3 seconds
    const interval = setInterval(() => {
      fetchStatus();
      fetchPositions();
    }, 3000);

    return () => clearInterval(interval);
  }, [fetchStatus, fetchPositions, session.activeAccountId]);

  // WebSocket connection for log streaming
  useEffect(() => {
    if (!session.activeAccountId) {
      setWsConnected(false);
      return;
    }

    const wsUrl = buildAuthenticatedWsUrl(
      `${API_URL.replace(/^http/, "ws")}/ws/logs`,
      session.token,
      session.activeAccountId
    );
    let reconnectTimeout: NodeJS.Timeout;
    let ws: WebSocket | null = null;
    let isCleaningUp = false;

    const connect = () => {
      if (isCleaningUp) return;

      try {
        ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          if (isCleaningUp) {
            ws?.close();
            return;
          }
          console.log("Log WebSocket connected");
          setWsConnected(true);
        };

        ws.onmessage = (event) => {
          if (isCleaningUp) return;
          try {
            const data = JSON.parse(event.data);

            if (data.type === "history" && Array.isArray(data.logs)) {
              // Received buffered log history
              setLogs(data.logs);
            } else if (data.type === "log" && data.log) {
              // Single new log entry
              setLogs((prev) => [...prev, data.log]);
            }
          } catch (err) {
            console.error("Failed to parse log message:", err);
          }
        };

        ws.onclose = () => {
          if (isCleaningUp) return;
          console.log("Log WebSocket disconnected");
          setWsConnected(false);
          wsRef.current = null;

          // Reconnect after 3 seconds
          reconnectTimeout = setTimeout(connect, 3000);
        };

        ws.onerror = () => {
          // WebSocket errors are expected during cleanup or reconnection
          // The onclose handler will handle reconnection
          if (!isCleaningUp && ws) {
            ws.close();
          }
        };
      } catch (err) {
        console.error("Failed to create WebSocket:", err);
        // Retry connection after delay
        if (!isCleaningUp) {
          reconnectTimeout = setTimeout(connect, 3000);
        }
      }
    };

    connect();

    return () => {
      isCleaningUp = true;
      clearTimeout(reconnectTimeout);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [session.activeAccountId, session.token]);

  // Auto-scroll logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  const handleStart = async () => {
    setIsStarting(true);
    setError(undefined);

    try {
      let config: Record<string, string> | undefined;
      if (writeEnvOnStart) {
        const configRes = await getBotConfig();
        if (configRes.success) {
          config = configRes.config;
        }
      }

      const res = await startBot({
        preventSleep,
        writeEnv: writeEnvOnStart,
        config,
      });

      if (res.success) {
        setStatus("starting");
        addLog("info", res.pid ? `Bot starting (PID: ${res.pid})...` : "Bot starting...");
      } else {
        setError(res.error);
        addLog("error", `Failed to start: ${res.error}`);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      addLog("error", `Failed to start: ${message}`);
    } finally {
      setIsStarting(false);
      fetchStatus();
    }
  };

  const handleStop = async () => {
    setIsStopping(true);

    try {
      const res = await stopBot();

      if (res.success) {
        setStatus("stopping");
        addLog("info", "Bot stopping...");
      } else {
        setError(res.error);
        addLog("error", `Failed to stop: ${res.error}`);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setError(message);
      addLog("error", `Failed to stop: ${message}`);
    } finally {
      setIsStopping(false);
      fetchStatus();
    }
  };

  const handleClearPositions = async () => {
    if (!confirm("Are you sure you want to clear all tracked positions?")) return;

    try {
      await clearTrackedPositions();
      setPositions([]);
      setPositionsStats({ total: 0, open: 0, closed: 0 });
      addLog("info", "Cleared all tracked positions");
    } catch (err) {
      console.error("Failed to clear positions:", err);
    }
  };

  const addLog = (level: string, message: string) => {
    setLogs((prev) => [
      ...prev,
      {
        id: `${Date.now()}-${Math.random()}`,
        level,
        message,
        timestamp: new Date().toLocaleTimeString(),
      },
    ]);
  };

  const handleCopyLogs = async () => {
    const text = logs
      .map((log) => {
        const time = log.timestamp.includes("T")
          ? new Date(log.timestamp).toLocaleTimeString()
          : log.timestamp;
        return `[${time}] ${log.message}`;
      })
      .join("\n");
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getStatusColor = (s: BotStatusType) => {
    switch (s) {
      case "running":
        return "success";
      case "starting":
      case "stopping":
        return "warning";
      case "error":
        return "danger";
      default:
        return "default";
    }
  };

  const getStatusIcon = (s: BotStatusType) => {
    switch (s) {
      case "running":
        return <Activity className="w-5 h-5 text-success animate-pulse" />;
      case "starting":
      case "stopping":
        return <Loader2 className="w-5 h-5 text-warning animate-spin" />;
      case "error":
        return <AlertCircle className="w-5 h-5 text-danger" />;
      default:
        return <Square className="w-5 h-5 text-text-muted" />;
    }
  };

  if (isLoading) {
    return (
      <PageContainer>
        <PageLoading label="Loading bot status…" />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <AnimatedSection>
        <PageHeader
          meta="Automation"
          title="Bot control"
          description="Start, stop, and monitor the signal copier bot"
          actions={
            <Button variant="ghost" size="icon" onClick={fetchStatus}>
              <RefreshCw className="w-4 h-4" />
            </Button>
          }
        />
      </AnimatedSection>

      <AnimatedSection>
        <SectionPanel>
          <PanelHeader
            eyebrow="Signal copier"
            title={
              <span className="inline-flex items-center gap-2">
                Bot status
                <Badge variant={getStatusColor(status)} className="capitalize">
                  {status}
                </Badge>
                {pid && (
                  <span className="text-xs font-normal text-text-muted">
                    PID {pid}
                  </span>
                )}
              </span>
            }
            action={getStatusIcon(status)}
          />
          <PanelBody>
            {/* Error Display */}
            {error && (
              <div className="mb-6 p-4 rounded-xl bg-danger/10 border border-danger/30 text-danger text-sm">
                {error}
              </div>
            )}

            {/* Control Buttons */}
            <div className="flex items-center gap-4 mb-6">
              <Button
                variant="accent"
                size="lg"
                onClick={handleStart}
                disabled={isStarting || status === "running" || status === "starting"}
                className="min-w-[140px]"
              >
                {isStarting ? (
                  <Loader2 className="w-5 h-5 animate-spin mr-2" />
                ) : (
                  <Play className="w-5 h-5 mr-2" />
                )}
                Start Bot
              </Button>

              <Button
                variant="danger"
                size="lg"
                onClick={handleStop}
                disabled={isStopping || status === "stopped" || status === "stopping"}
                className="min-w-[140px]"
              >
                {isStopping ? (
                  <Loader2 className="w-5 h-5 animate-spin mr-2" />
                ) : (
                  <Square className="w-5 h-5 mr-2" />
                )}
                Stop Bot
              </Button>
            </div>

            {/* Options */}
            <div className="flex flex-wrap items-center gap-6 p-4 rounded-xl bg-bg-tertiary/50 border border-border-subtle">
              <Checkbox
                label="Write .env on start"
                checked={writeEnvOnStart}
                onChange={(e) => setWriteEnvOnStart(e.target.checked)}
              />

              <Checkbox
                label={IS_MACOS ? "Prevent sleep (caffeinate)" : "Prevent sleep (macOS only)"}
                checked={preventSleep}
                onChange={(e) => setPreventSleep(e.target.checked)}
                disabled={!IS_MACOS}
              />
            </div>

            {/* Status Info */}
            {status === "running" && startedAt && (
              <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
                <MetricCard
                  label="Started"
                  value={new Date(startedAt).toLocaleString()}
                  icon={<Clock className="w-5 h-5" />}
                />
                <MetricCard
                  label="Process ID"
                  value={String(pid || "-")}
                  icon={<Server className="w-5 h-5" />}
                  accent="info"
                />
                <MetricCard
                  label="Health"
                  value="Healthy"
                  icon={<CheckCircle className="w-5 h-5" />}
                  accent="success"
                />
              </div>
            )}
          </PanelBody>
        </SectionPanel>
      </AnimatedSection>

      <AnimatedSection>
        <SectionPanel>
          <PanelHeader
            eyebrow="Tracking"
            title={
              <span className="inline-flex items-center gap-2">
                Tracked positions
                <Badge variant="default">{positionsStats.total}</Badge>
              </span>
            }
            action={
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={fetchPositions}>
                  <RefreshCw className="w-4 h-4" />
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={handleClearPositions}
                  disabled={positions.length === 0}
                >
                  <Trash2 className="w-4 h-4 mr-1" />
                  Clear
                </Button>
              </div>
            }
          />
          <PanelBody flush>
            {positions.length === 0 ? (
              <EmptyState
                icon={<Activity className="w-5 h-5" />}
                title="No tracked positions"
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full data-table">
                  <thead>
                    <tr className="border-b border-border-subtle">
                      <th className="px-4 py-3 text-left">Msg ID</th>
                      <th className="px-4 py-3 text-left">Ticket</th>
                      <th className="px-4 py-3 text-left">Symbol</th>
                      <th className="px-4 py-3 text-left">Role</th>
                      <th className="px-4 py-3 text-left">Type</th>
                      <th className="px-4 py-3 text-right">Entry</th>
                      <th className="px-4 py-3 text-right">SL</th>
                      <th className="px-4 py-3 text-right">Lot</th>
                      <th className="px-4 py-3 text-left">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.slice(0, 10).map((pos, idx) => (
                      <tr key={`${pos.msg_id}-${pos.role}-${idx}`} className="border-b border-border-subtle">
                        <td className="px-4 py-3 text-text-secondary tabular-nums">{pos.msg_id}</td>
                        <td className="px-4 py-3 text-text-primary tabular-nums">{pos.mt5_ticket || "-"}</td>
                        <td className="px-4 py-3">
                          <SymbolCell symbol={pos.symbol} size="sm" />
                        </td>
                        <td className="px-4 py-3">
                          <Badge
                            variant={pos.role === "scalp" ? "default" : pos.role === "runner" ? "warning" : "default"}
                            className="capitalize"
                          >
                            {pos.role}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 uppercase text-text-secondary">{pos.order_type}</td>
                        <td className="px-4 py-3 text-right tabular-nums text-text-primary">
                          {pos.entry_price?.toFixed(5) || "-"}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-danger">
                          {pos.stop_loss?.toFixed(5) || "-"}
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-text-secondary">
                          {pos.lot_size?.toFixed(2) || "-"}
                        </td>
                        <td className="px-4 py-3">
                          <Badge
                            variant={pos.status === "open" ? "success" : pos.status === "closed" ? "default" : "warning"}
                            className="capitalize"
                          >
                            {pos.status}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {positions.length > 10 && (
                  <div className="p-3 text-center text-sm text-text-muted border-t border-border-subtle">
                    Showing 10 of {positions.length} positions
                  </div>
                )}
              </div>
            )}
          </PanelBody>
        </SectionPanel>
      </AnimatedSection>

      <AnimatedSection>
        <SectionPanel>
          <PanelHeader
            eyebrow="Terminal"
            title={
              <span className="inline-flex items-center gap-2">
                Output log
                {wsConnected && (
                  <Badge variant="success" className="text-xs">
                    Live
                  </Badge>
                )}
              </span>
            }
            action={
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleCopyLogs}
                  disabled={logs.length === 0}
                >
                  {copied ? <Check className="w-4 h-4 mr-1" /> : <Copy className="w-4 h-4 mr-1" />}
                  {copied ? "Copied" : "Copy"}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setLogs([]);
                    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                      wsRef.current.send("clear");
                    }
                  }}
                >
                  Clear
                </Button>
              </div>
            }
          />
          <TerminalPanel>
            {logs.length === 0 ? (
              <div className="text-text-muted text-center py-8">
                {wsConnected ? "Waiting for bot output…" : "Connecting to log stream…"}
              </div>
            ) : (
              logs.map((log) => {
                const time = log.timestamp.includes("T")
                  ? new Date(log.timestamp).toLocaleTimeString()
                  : log.timestamp;

                return (
                  <div
                    key={log.id}
                    className={`py-1 ${
                      log.level === "error"
                        ? "text-danger"
                        : log.level === "warning"
                          ? "text-warning"
                          : "text-text-secondary"
                    }`}
                  >
                    <span className="text-text-muted">[{time}]</span> {log.message}
                  </div>
                );
              })
            )}
            <div ref={logEndRef} />
          </TerminalPanel>
        </SectionPanel>
      </AnimatedSection>

      <AnimatedSection>
        <div className="flex items-center gap-3 p-4 rounded-xl bg-bg-secondary/50 border border-border-subtle">
          <Zap className="w-5 h-5 text-accent flex-shrink-0" />
          <p className="text-sm text-text-muted">
            <span className="font-medium text-text-secondary">Tip:</span> The bot
            reconnects automatically if the connection drops. Update settings on
            the Configuration page.
          </p>
        </div>
      </AnimatedSection>
    </PageContainer>
  );
}

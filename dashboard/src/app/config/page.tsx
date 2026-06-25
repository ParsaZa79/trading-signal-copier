"use client";

import { useState, useEffect, useCallback } from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  PageHeader,
  PageLoading,
  SectionPanel,
  PanelHeader,
  PanelBody,
} from "@/components/layout";
import { useDashboard } from "@/components/layout/dashboard-layout";
import {
  getBotConfig,
  saveBotConfig,
  connectMT5,
  getMT5BrokerServers,
  getPresets,
  getPreset,
  savePreset,
  deletePreset,
  getSystemPrompts,
  saveSystemPrompts,
  resetSystemPrompts,
} from "@/lib/api";
import {
  Server,
  TrendingUp,
  Settings2,
  Save,
  Trash2,
  Plus,
  ChevronDown,
  Loader2,
  Check,
  AlertCircle,
  Brain,
  RotateCcw,
} from "lucide-react";
import { PageContainer, AnimatedSection } from "@/components/motion";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  CUSTOM_BROKER_SERVER_VALUE,
  MT5_BROKER_SERVER_OPTIONS,
  brokerServerOptionsWithCustom,
  type BrokerServerOption,
} from "@/lib/broker-servers";

const IS_MACOS = typeof window !== "undefined" && navigator.platform.includes("Mac");

interface ConfigSection {
  title: string;
  icon: React.ReactNode;
  color: string;
  fields: Array<{
    key: string;
    label: string;
    type: "text" | "password" | "select";
    placeholder?: string;
    options?: Array<{ value: string; label: string }>;
    condition?: () => boolean;
  }>;
}

export default function ConfigPage() {
  const { session } = useDashboard();
  const [config, setConfig] = useState<Record<string, string>>({});
  const [configuredSecrets, setConfiguredSecrets] = useState<string[]>([]);
  const [presets, setPresets] = useState<Array<{ name: string; created_at: string; modified_at: string }>>([]);
  const [currentPreset, setCurrentPreset] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "success" | "error">("idle");
  const [mt5ConnectStatus, setMt5ConnectStatus] = useState<"idle" | "connecting" | "success" | "error">("idle");
  const [mt5ConnectMessage, setMt5ConnectMessage] = useState<string | null>(null);
  const [showPresetDialog, setShowPresetDialog] = useState(false);
  const [newPresetName, setNewPresetName] = useState("");
  const [presetDropdownOpen, setPresetDropdownOpen] = useState(false);
  const [brokerServers, setBrokerServers] = useState<BrokerServerOption[]>(
    MT5_BROKER_SERVER_OPTIONS
  );
  const [useCustomBrokerServer, setUseCustomBrokerServer] = useState(false);

  // System prompts state
  const [systemPrompt, setSystemPrompt] = useState("");
  const [correctionPrompt, setCorrectionPrompt] = useState("");
  const [isCustomSystemPrompt, setIsCustomSystemPrompt] = useState(false);
  const [isCustomCorrectionPrompt, setIsCustomCorrectionPrompt] = useState(false);
  const [promptsSaving, setPromptsSaving] = useState(false);
  const [promptsSaveStatus, setPromptsSaveStatus] = useState<"idle" | "success" | "error">("idle");

  const applyConfiguredSecrets = useCallback((secrets: string[]) => {
    setConfiguredSecrets(secrets);
    setConfig((prev) => {
      const next = { ...prev };
      secrets.forEach((key) => {
        next[key] = "";
      });
      return next;
    });
  }, []);

  const selectedBrokerServer = useCustomBrokerServer
    ? CUSTOM_BROKER_SERVER_VALUE
    : config.MT5_SERVER || "";

  const configSections: ConfigSection[] = [
    {
      title: "MetaTrader 5",
      icon: <Server className="w-5 h-5" />,
      color: "success",
      fields: [
        { key: "MT5_LOGIN", label: "Login", type: "text", placeholder: "Account number" },
        { key: "MT5_PASSWORD", label: "Password", type: "password", placeholder: "Your password" },
        {
          key: "MT5_SERVER",
          label: "Broker",
          type: "select",
          placeholder: "Select broker server",
          options: brokerServerOptionsWithCustom(config.MT5_SERVER, brokerServers),
        },
        ...(IS_MACOS
          ? [
              { key: "MT5_DOCKER_HOST", label: "Docker Host", type: "text" as const, placeholder: "localhost" },
              { key: "MT5_DOCKER_PORT", label: "Docker Port", type: "text" as const, placeholder: "18812" },
            ]
          : [{ key: "MT5_PATH", label: "MT5 Path (optional)", type: "text" as const, placeholder: "Auto-detected" }]),
      ],
    },
    {
      title: "Trading",
      icon: <TrendingUp className="w-5 h-5" />,
      color: "accent",
      fields: [
        { key: "DEFAULT_LOT_SIZE", label: "Default Lot Size", type: "text", placeholder: "0.01" },
        { key: "MAX_RISK_PERCENT", label: "Max Risk %", type: "text", placeholder: "2" },
        { key: "SCALP_LOT_SIZE", label: "Scalp Lot Size", type: "text", placeholder: "0.01" },
        { key: "RUNNER_LOT_SIZE", label: "Runner Lot Size", type: "text", placeholder: "0.01" },
        {
          key: "TRADING_STRATEGY",
          label: "Strategy",
          type: "select",
          options: [
            { value: "dual_tp", label: "Dual TP (Scalp + Runner)" },
            { value: "single", label: "Single Position" },
          ],
        },
        { key: "EDIT_WINDOW_SECONDS", label: "Edit Window (sec)", type: "text", placeholder: "120" },
      ],
    },
    {
      title: "Inference",
      icon: <Brain className="w-5 h-5" />,
      color: "warning",
      fields: [
        {
          key: "LLM_PROVIDER",
          label: "Provider",
          type: "select",
          options: [
            { value: "groq", label: "Groq" },
            { value: "cerebras", label: "Cerebras" },
          ],
        },
        { key: "GROQ_API_KEY", label: "Groq API Key", type: "password", placeholder: "gsk_..." },
        { key: "CEREBRAS_API_KEY", label: "Cerebras API Key", type: "password", placeholder: "csk-..." },
      ],
    },
    {
      title: "Optional",
      icon: <Settings2 className="w-5 h-5" />,
      color: "muted",
      fields: [{ key: "TEST_SYMBOL", label: "Test Symbol", type: "text", placeholder: "EURUSD" }],
    },
  ];

  const loadData = useCallback(async () => {
    try {
      const [configRes, presetsRes, promptsRes] = await Promise.all([
        getBotConfig(),
        getPresets(),
        getSystemPrompts(),
      ]);

      if (configRes.success) {
        setConfig(configRes.config);
        setUseCustomBrokerServer(false);
        applyConfiguredSecrets(configRes.configuredSecrets || []);
      }

      if (presetsRes.success) {
        setPresets(presetsRes.presets);
        if (presetsRes.lastPreset) {
          setCurrentPreset(presetsRes.lastPreset);
        }
      }

      if (promptsRes.success) {
        setSystemPrompt(promptsRes.system_prompt);
        setCorrectionPrompt(promptsRes.correction_system_prompt);
        setIsCustomSystemPrompt(promptsRes.is_custom_system_prompt);
        setIsCustomCorrectionPrompt(promptsRes.is_custom_correction_prompt);
      }

      getMT5BrokerServers()
        .then((brokerRes) => {
          if (brokerRes.success && brokerRes.brokers.length > 0) {
            setBrokerServers(brokerRes.brokers);
          }
        })
        .catch(() => undefined);
    } catch (error) {
      console.error("Failed to load config:", error);
    } finally {
      setIsLoading(false);
    }
  }, [applyConfiguredSecrets]);

  useEffect(() => {
    setIsLoading(true);
    setSaveStatus("idle");
    setMt5ConnectStatus("idle");
    setMt5ConnectMessage(null);
    loadData();
  }, [loadData, session.activeAccountId]);

  const handleFieldChange = (key: string, value: string) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
    setSaveStatus("idle");
    if (key.startsWith("MT5_")) {
      setMt5ConnectStatus("idle");
      setMt5ConnectMessage(null);
    }
  };

  const handleBrokerServerChange = (value: string) => {
    if (value === CUSTOM_BROKER_SERVER_VALUE) {
      setUseCustomBrokerServer(true);
      handleFieldChange("MT5_SERVER", "");
      return;
    }

    setUseCustomBrokerServer(false);
    handleFieldChange("MT5_SERVER", value);
  };

  const handleConnectMt5 = async () => {
    const login = config.MT5_LOGIN?.trim();
    const password = config.MT5_PASSWORD?.trim();
    const server = config.MT5_SERVER?.trim();
    const hasStoredPassword = configuredSecrets.includes("MT5_PASSWORD");

    if (!login || (!password && !hasStoredPassword) || !server || Number.isNaN(Number(login)) || Number(login) <= 0) {
      setMt5ConnectStatus("error");
      setMt5ConnectMessage("Enter a valid MT5 login, password, and server.");
      return;
    }

    setMt5ConnectStatus("connecting");
    setMt5ConnectMessage(null);

    try {
      const saved = await saveBotConfig(config);
      if (saved.configuredSecrets) {
        applyConfiguredSecrets(saved.configuredSecrets);
      }
      const result = await connectMT5(config);
      if (!result.success || !result.connected) {
        setMt5ConnectStatus("error");
        setMt5ConnectMessage(result.error || result.health?.error || "MT5 connection failed.");
        return;
      }

      setMt5ConnectStatus("success");
      setUseCustomBrokerServer(false);
      getMT5BrokerServers()
        .then((brokerRes) => {
          if (brokerRes.success && brokerRes.brokers.length > 0) {
            setBrokerServers(brokerRes.brokers);
          }
        })
        .catch(() => undefined);
      const balance = result.health?.account_balance;
      setMt5ConnectMessage(
        typeof balance === "number"
          ? `Connected. Account balance: ${balance.toLocaleString(undefined, {
              maximumFractionDigits: 2,
            })}`
          : "Connected to MT5."
      );
    } catch (error) {
      setMt5ConnectStatus("error");
      setMt5ConnectMessage(error instanceof Error ? error.message : "MT5 connection failed.");
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveStatus("idle");

    try {
      const saved = await saveBotConfig(config);
      if (saved.configuredSecrets) {
        applyConfiguredSecrets(saved.configuredSecrets);
      }

      if (currentPreset) {
        await savePreset(currentPreset, config);
      }

      setSaveStatus("success");
      setTimeout(() => setSaveStatus("idle"), 2000);
    } catch (error) {
      console.error("Failed to save:", error);
      setSaveStatus("error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleLoadPreset = async (name: string) => {
    try {
      const res = await getPreset(name);
      if (res.success) {
        setConfig(res.preset.values);
        setUseCustomBrokerServer(false);
        applyConfiguredSecrets(res.preset.configuredSecrets || []);
        setCurrentPreset(name);
      }
    } catch (error) {
      console.error("Failed to load preset:", error);
    }
    setPresetDropdownOpen(false);
  };

  const handleSaveAsPreset = async () => {
    if (!newPresetName.trim()) return;

    try {
      await savePreset(newPresetName.trim(), config);
      setCurrentPreset(newPresetName.trim());
      setNewPresetName("");
      setShowPresetDialog(false);

      // Refresh presets list
      const presetsRes = await getPresets();
      if (presetsRes.success) {
        setPresets(presetsRes.presets);
      }
    } catch (error) {
      console.error("Failed to save preset:", error);
    }
  };

  const handleDeletePreset = async () => {
    if (!currentPreset) return;

    try {
      await deletePreset(currentPreset);
      setCurrentPreset(null);

      // Refresh presets list
      const presetsRes = await getPresets();
      if (presetsRes.success) {
        setPresets(presetsRes.presets);
      }
    } catch (error) {
      console.error("Failed to delete preset:", error);
    }
  };

  const handleSavePrompts = async () => {
    setPromptsSaving(true);
    setPromptsSaveStatus("idle");
    try {
      await saveSystemPrompts({
        system_prompt: systemPrompt,
        correction_system_prompt: correctionPrompt,
      });
      setPromptsSaveStatus("success");
      setIsCustomSystemPrompt(true);
      setIsCustomCorrectionPrompt(true);
      setTimeout(() => setPromptsSaveStatus("idle"), 2000);
    } catch (error) {
      console.error("Failed to save prompts:", error);
      setPromptsSaveStatus("error");
    } finally {
      setPromptsSaving(false);
    }
  };

  const handleResetPrompts = async () => {
    try {
      await resetSystemPrompts();
      const promptsRes = await getSystemPrompts();
      if (promptsRes.success) {
        setSystemPrompt(promptsRes.system_prompt);
        setCorrectionPrompt(promptsRes.correction_system_prompt);
        setIsCustomSystemPrompt(false);
        setIsCustomCorrectionPrompt(false);
        setPromptsSaveStatus("idle");
      }
    } catch (error) {
      console.error("Failed to reset prompts:", error);
    }
  };

  const colorStyles: Record<string, { bg: string; border: string; text: string }> = {
    info: { bg: "bg-info/10", border: "border-info/30", text: "text-info" },
    success: { bg: "bg-success/10", border: "border-success/30", text: "text-success" },
    accent: { bg: "bg-accent/10", border: "border-accent/30", text: "text-accent" },
    warning: { bg: "bg-warning/10", border: "border-warning/30", text: "text-warning" },
    muted: { bg: "bg-bg-tertiary", border: "border-border-subtle", text: "text-text-muted" },
  };

  const isSecretConfigured = (key: string) => configuredSecrets.includes(key);

  if (isLoading) {
    return (
      <PageContainer>
        <PageLoading label="Loading configuration…" />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <AnimatedSection>
        <PageHeader
          meta="Setup"
          title="Configuration"
          description="Bot settings and runtime presets"
          actions={
            <>
            {/* Preset Selector */}
            <div className="relative">
              <button
                onClick={() => setPresetDropdownOpen(!presetDropdownOpen)}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-bg-tertiary border border-border-subtle hover:border-accent/30 transition-colors"
              >
                <span className="text-sm text-text-secondary">
                  {currentPreset || "No preset"}
                </span>
                <ChevronDown className="w-4 h-4 text-text-muted" />
              </button>

              {presetDropdownOpen && (
                <>
                  <div
                    className="fixed inset-0 z-10"
                    onClick={() => setPresetDropdownOpen(false)}
                  />
                  <div className="absolute right-0 top-full mt-2 w-56 p-2 rounded-xl bg-bg-elevated border border-border-subtle shadow-lg z-20">
                    {presets.length === 0 ? (
                      <p className="px-3 py-2 text-sm text-text-muted">No presets saved</p>
                    ) : (
                      presets.map((preset) => (
                        <button
                          key={preset.name}
                          onClick={() => handleLoadPreset(preset.name)}
                          className={`w-full px-3 py-2 text-left text-sm rounded-lg transition-colors ${
                            currentPreset === preset.name
                              ? "bg-accent/20 text-accent"
                              : "text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
                          }`}
                        >
                          {preset.name}
                        </button>
                      ))
                    )}
                    <div className="border-t border-border-subtle mt-2 pt-2">
                      <button
                        onClick={() => {
                          setPresetDropdownOpen(false);
                          setShowPresetDialog(true);
                        }}
                        className="w-full px-3 py-2 text-left text-sm text-accent hover:bg-accent/10 rounded-lg transition-colors flex items-center gap-2"
                      >
                        <Plus className="w-4 h-4" />
                        Save as new preset
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>

            {currentPreset && (
              <Button variant="ghost" size="icon" onClick={handleDeletePreset}>
                <Trash2 className="w-4 h-4 text-danger" />
              </Button>
            )}

            {/* Save Button */}
            <Button variant="accent" onClick={handleSave} disabled={isSaving}>
              {isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : saveStatus === "success" ? (
                <Check className="w-4 h-4 text-success" />
              ) : saveStatus === "error" ? (
                <AlertCircle className="w-4 h-4 text-danger" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              <span className="ml-2">Save</span>
            </Button>
            </>
          }
        />
      </AnimatedSection>

      {/* Current Preset Badge */}
      {currentPreset && (
        <AnimatedSection>
          <Badge variant="default" className="bg-accent/20 text-accent border-accent/30">
            Active Preset: {currentPreset}
          </Badge>
        </AnimatedSection>
      )}

      {/* Config Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {configSections.map((section, idx) => {
          const colors = colorStyles[section.color];

          return (
            <AnimatedSection key={section.title} className={`stagger-${idx + 1}`}>
              <SectionPanel>
                <PanelHeader
                  eyebrow={section.title}
                  title={section.title}
                  action={
                    <span className={colors.text}>{section.icon}</span>
                  }
                />
                <PanelBody>
                  <div className="space-y-4">
                    {section.fields.map((field) => {
                      if (field.condition && !field.condition()) return null;

                      if (field.type === "select") {
                        return (
                          <div key={field.key} className="space-y-4">
                            <Select
                              label={field.label}
                              value={
                                field.key === "MT5_SERVER"
                                  ? selectedBrokerServer
                                  : config[field.key] || ""
                              }
                              onChange={(e) =>
                                field.key === "MT5_SERVER"
                                  ? handleBrokerServerChange(e.target.value)
                                  : handleFieldChange(field.key, e.target.value)
                              }
                              options={field.options || []}
                              placeholder={field.placeholder}
                            />
                            {field.key === "MT5_SERVER" && useCustomBrokerServer && (
                              <Input
                                label="Server name"
                                value={config.MT5_SERVER || ""}
                                onChange={(e) => handleFieldChange("MT5_SERVER", e.target.value)}
                                placeholder="Exact MT5 server"
                              />
                            )}
                          </div>
                        );
                      }

                      return (
                        <Input
                          key={field.key}
                          label={field.label}
                          type={field.type}
                          value={config[field.key] || ""}
                          onChange={(e) => handleFieldChange(field.key, e.target.value)}
                          placeholder={
                            field.type === "password" && isSecretConfigured(field.key)
                              ? "Configured"
                              : field.placeholder
                          }
                        />
                      );
                    })}
                    {section.title === "MetaTrader 5" && (
                      <div className="pt-4 border-t border-border-subtle space-y-3">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-text-primary">
                              Runtime connection
                            </p>
                            <p className="text-xs text-text-muted mt-1">
                              Saves these credentials and reconnects the running API process.
                            </p>
                          </div>
                          <Button
                            variant="secondary"
                            onClick={handleConnectMt5}
                            disabled={mt5ConnectStatus === "connecting"}
                          >
                            {mt5ConnectStatus === "connecting" ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : mt5ConnectStatus === "success" ? (
                              <Check className="w-4 h-4 text-success" />
                            ) : mt5ConnectStatus === "error" ? (
                              <AlertCircle className="w-4 h-4 text-danger" />
                            ) : (
                              <Server className="w-4 h-4" />
                            )}
                            <span>Save & Connect</span>
                          </Button>
                        </div>
                        {mt5ConnectMessage && (
                          <div
                            className={`rounded-xl border px-4 py-3 text-xs ${
                              mt5ConnectStatus === "success"
                                ? "border-success/20 bg-success/10 text-success"
                                : "border-danger/20 bg-danger/10 text-danger"
                            }`}
                          >
                            {mt5ConnectMessage}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </PanelBody>
              </SectionPanel>
            </AnimatedSection>
          );
        })}
      </div>

      {/* System Prompts Section */}
      <AnimatedSection>
        <SectionPanel>
          <PanelHeader
            eyebrow="LLM"
            title="System prompts"
            description="Controls how the AI parses trading signals. Changes apply on next bot restart."
            action={
              <div className="flex items-center gap-2 flex-wrap justify-end">
                {(isCustomSystemPrompt || isCustomCorrectionPrompt) && (
                  <Badge variant="warning">Customized</Badge>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleResetPrompts}
                  disabled={!isCustomSystemPrompt && !isCustomCorrectionPrompt}
                >
                  <RotateCcw className="w-4 h-4" />
                  <span className="ml-1">Reset</span>
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleSavePrompts}
                  disabled={promptsSaving}
                >
                  {promptsSaving ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : promptsSaveStatus === "success" ? (
                    <Check className="w-4 h-4 text-success" />
                  ) : promptsSaveStatus === "error" ? (
                    <AlertCircle className="w-4 h-4 text-danger" />
                  ) : (
                    <Save className="w-4 h-4" />
                  )}
                  <span className="ml-1">Save prompts</span>
                </Button>
              </div>
            }
          />
          <PanelBody className="space-y-6">
            <Textarea
              label="Signal Parsing Prompt"
              value={systemPrompt}
              onChange={(e) => {
                setSystemPrompt(e.target.value);
                setPromptsSaveStatus("idle");
              }}
              rows={20}
              placeholder="Enter the system prompt for signal parsing..."
            />
            <Textarea
              label="Correction Parsing Prompt"
              value={correctionPrompt}
              onChange={(e) => {
                setCorrectionPrompt(e.target.value);
                setPromptsSaveStatus("idle");
              }}
              rows={12}
              placeholder="Enter the system prompt for correction parsing..."
            />
            <div className="flex items-start gap-2 p-3 rounded-xl bg-warning/5 border border-warning/20">
              <AlertCircle className="w-4 h-4 text-warning mt-0.5 shrink-0" />
              <p className="text-xs text-text-muted">
                The correction prompt uses template placeholders like{" "}
                <code className="text-text-secondary">{"{original_entry}"}</code>,{" "}
                <code className="text-text-secondary">{"{original_sl}"}</code>,{" "}
                <code className="text-text-secondary">{"{original_tps}"}</code>,{" "}
                <code className="text-text-secondary">{"{symbol}"}</code>, and{" "}
                <code className="text-text-secondary">{"{order_type}"}</code>.
                Make sure to preserve these when editing.
              </p>
            </div>
          </PanelBody>
        </SectionPanel>
      </AnimatedSection>

      {/* Save As Preset Dialog */}
      <Dialog open={showPresetDialog} onOpenChange={setShowPresetDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Save as Preset</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <Input
              label="Preset Name"
              value={newPresetName}
              onChange={(e) => setNewPresetName(e.target.value)}
              placeholder="My Trading Setup"
              autoFocus
            />
            <div className="flex justify-end gap-3">
              <Button variant="ghost" onClick={() => setShowPresetDialog(false)}>
                Cancel
              </Button>
              <Button variant="accent" onClick={handleSaveAsPreset} disabled={!newPresetName.trim()}>
                Save Preset
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </PageContainer>
  );
}

export interface BrokerServerOption {
  value: string;
  label: string;
  source?: "seed" | "learned" | "current" | "custom";
}

export const CUSTOM_BROKER_SERVER_VALUE = "__custom_mt5_broker_server__";

export const MT5_BROKER_SERVER_OPTIONS: BrokerServerOption[] = [
  { value: "AMarkets-Real", label: "AMarkets - Real (AMarkets-Real)" },
  { value: "AMarkets-Demo", label: "AMarkets - Demo (AMarkets-Demo)" },
  { value: "AdmiralMarkets-Live", label: "Admirals - Live (AdmiralMarkets-Live)" },
  { value: "AdmiralMarkets-Demo", label: "Admirals - Demo (AdmiralMarkets-Demo)" },
  { value: "Axiory-Live", label: "Axiory - Live (Axiory-Live)" },
  { value: "Axiory-Demo", label: "Axiory - Demo (Axiory-Demo)" },
  { value: "BlackBullMarkets-Live", label: "BlackBull Markets - Live (BlackBullMarkets-Live)" },
  { value: "BlackBullMarkets-Demo", label: "BlackBull Markets - Demo (BlackBullMarkets-Demo)" },
  { value: "BlueberryMarkets-Live", label: "Blueberry Markets - Live (BlueberryMarkets-Live)" },
  { value: "BlueberryMarkets-Demo", label: "Blueberry Markets - Demo (BlueberryMarkets-Demo)" },
  { value: "Eightcap-Real", label: "Eightcap - Real (Eightcap-Real)" },
  { value: "Eightcap-Demo", label: "Eightcap - Demo (Eightcap-Demo)" },
  { value: "Exness-MT5Real", label: "Exness - Real (Exness-MT5Real)" },
  { value: "Exness-MT5Real2", label: "Exness - Real 2 (Exness-MT5Real2)" },
  { value: "Exness-MT5Real3", label: "Exness - Real 3 (Exness-MT5Real3)" },
  { value: "Exness-MT5Trial", label: "Exness - Demo (Exness-MT5Trial)" },
  { value: "FBS-Real", label: "FBS - Real (FBS-Real)" },
  { value: "FBS-Demo", label: "FBS - Demo (FBS-Demo)" },
  { value: "FPMarkets-Live", label: "FP Markets - Live (FPMarkets-Live)" },
  { value: "FPMarkets-Demo", label: "FP Markets - Demo (FPMarkets-Demo)" },
  { value: "FusionMarkets-Live", label: "Fusion Markets - Live (FusionMarkets-Live)" },
  { value: "FusionMarkets-Demo", label: "Fusion Markets - Demo (FusionMarkets-Demo)" },
  { value: "FxPro-MT5", label: "FxPro - MT5 (FxPro-MT5)" },
  { value: "FxPro.com-Real", label: "FxPro - Real (FxPro.com-Real)" },
  { value: "FxPro.com-Demo", label: "FxPro - Demo (FxPro.com-Demo)" },
  { value: "HFM-Live", label: "HFM - Live (HFM-Live)" },
  { value: "HFM-Demo", label: "HFM - Demo (HFM-Demo)" },
  { value: "ICMarketsSC-MT5", label: "IC Markets - MT5 (ICMarketsSC-MT5)" },
  { value: "ICMarketsSC-MT5-2", label: "IC Markets - MT5 2 (ICMarketsSC-MT5-2)" },
  { value: "ICMarketsSC-Demo", label: "IC Markets - Demo (ICMarketsSC-Demo)" },
  { value: "IronFX-Live", label: "IronFX - Live (IronFX-Live)" },
  { value: "IronFX-Demo", label: "IronFX - Demo (IronFX-Demo)" },
  { value: "JustMarkets-Live", label: "JustMarkets - Live (JustMarkets-Live)" },
  { value: "JustMarkets-Demo", label: "JustMarkets - Demo (JustMarkets-Demo)" },
  { value: "LiteFinance-ECN", label: "LiteFinance - ECN (LiteFinance-ECN)" },
  { value: "LiteFinance-Demo", label: "LiteFinance - Demo (LiteFinance-Demo)" },
  { value: "MetaQuotes-Demo", label: "MetaQuotes - Demo (MetaQuotes-Demo)" },
  { value: "OANDA-v20 Live-1", label: "OANDA - Live (OANDA-v20 Live-1)" },
  { value: "OANDA-v20 Practice-1", label: "OANDA - Practice (OANDA-v20 Practice-1)" },
  { value: "OctaFX-Real", label: "Octa - Real (OctaFX-Real)" },
  { value: "OctaFX-Demo", label: "Octa - Demo (OctaFX-Demo)" },
  { value: "Pepperstone-MT5-Live01", label: "Pepperstone - Live 01 (Pepperstone-MT5-Live01)" },
  { value: "Pepperstone-MT5-Live02", label: "Pepperstone - Live 02 (Pepperstone-MT5-Live02)" },
  { value: "Pepperstone-Demo", label: "Pepperstone - Demo (Pepperstone-Demo)" },
  { value: "RoboForex-ECN", label: "RoboForex - ECN (RoboForex-ECN)" },
  { value: "RoboForex-Pro", label: "RoboForex - Pro (RoboForex-Pro)" },
  { value: "RoboForex-Demo", label: "RoboForex - Demo (RoboForex-Demo)" },
  { value: "Tickmill-Live", label: "Tickmill - Live (Tickmill-Live)" },
  { value: "Tickmill-Demo", label: "Tickmill - Demo (Tickmill-Demo)" },
  { value: "VantageInternational-Live", label: "Vantage - Live (VantageInternational-Live)" },
  { value: "VantageInternational-Demo", label: "Vantage - Demo (VantageInternational-Demo)" },
  { value: "XMGlobal-MT5", label: "XM - MT5 (XMGlobal-MT5)" },
  { value: "XMGlobal-Demo", label: "XM - Demo (XMGlobal-Demo)" },
];

export function brokerServerOptionsWithCurrent(
  currentServer?: string,
  brokerServers: BrokerServerOption[] = MT5_BROKER_SERVER_OPTIONS
): BrokerServerOption[] {
  const server = currentServer?.trim();
  if (!server || brokerServers.some((option) => option.value === server)) {
    return brokerServers;
  }

  return [{ value: server, label: `Current - ${server}`, source: "current" }, ...brokerServers];
}

export function brokerServerOptionsWithCustom(
  currentServer?: string,
  brokerServers: BrokerServerOption[] = MT5_BROKER_SERVER_OPTIONS
): BrokerServerOption[] {
  return [
    ...brokerServerOptionsWithCurrent(currentServer, brokerServers),
    {
      value: CUSTOM_BROKER_SERVER_VALUE,
      label: "Broker not listed - enter server manually",
      source: "custom",
    },
  ];
}

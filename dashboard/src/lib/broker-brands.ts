import type { BrokerServerOption } from "./broker-servers";

export interface BrokerBrand {
  id: string;
  name: string;
  logo: string;
  website: string;
  serverPrefixes: string[];
}

export interface BrokerBrandGroup extends BrokerBrand {
  servers: BrokerServerOption[];
}

export const BROKER_BRANDS: BrokerBrand[] = [
  { id: "amarkets", name: "AMarkets", logo: "/brokers/amarkets.png", website: "https://www.amarkets.com", serverPrefixes: ["AMarkets-"] },
  { id: "admirals", name: "Admirals", logo: "/brokers/admirals.png", website: "https://admiralmarkets.com", serverPrefixes: ["AdmiralMarkets-"] },
  { id: "exness", name: "Exness", logo: "/brokers/exness.png", website: "https://www.exness.com", serverPrefixes: ["Exness-"] },
  { id: "ic-markets", name: "IC Markets", logo: "/brokers/ic-markets.png", website: "https://www.icmarkets.com", serverPrefixes: ["ICMarketsSC-"] },
  { id: "pepperstone", name: "Pepperstone", logo: "/brokers/pepperstone.png", website: "https://pepperstone.com", serverPrefixes: ["Pepperstone-"] },
  { id: "oanda", name: "OANDA", logo: "/brokers/oanda.png", website: "https://www.oanda.com", serverPrefixes: ["OANDA-"] },
  { id: "eightcap", name: "Eightcap", logo: "/brokers/eightcap.png", website: "https://www.eightcap.com", serverPrefixes: ["Eightcap-"] },
  { id: "fp-markets", name: "FP Markets", logo: "/brokers/fp-markets.png", website: "https://www.fpmarkets.com", serverPrefixes: ["FPMarkets-"] },
  { id: "axiory", name: "Axiory", logo: "/brokers/axiory.png", website: "https://www.axiory.com", serverPrefixes: ["Axiory-"] },
  { id: "blackbull-markets", name: "BlackBull Markets", logo: "/brokers/blackbull-markets.png", website: "https://blackbull.com", serverPrefixes: ["BlackBullMarkets-"] },
  { id: "blueberry-markets", name: "Blueberry Markets", logo: "/brokers/blueberry-markets.png", website: "https://blueberrymarkets.com", serverPrefixes: ["BlueberryMarkets-"] },
  { id: "fbs", name: "FBS", logo: "/brokers/fbs.png", website: "https://fbs.com", serverPrefixes: ["FBS-"] },
  { id: "fusion-markets", name: "Fusion Markets", logo: "/brokers/fusion-markets.png", website: "https://fusionmarkets.com", serverPrefixes: ["FusionMarkets-"] },
  { id: "fxpro", name: "FxPro", logo: "/brokers/fxpro.png", website: "https://www.fxpro.com", serverPrefixes: ["FxPro"] },
  { id: "hfm", name: "HFM", logo: "/brokers/hfm.png", website: "https://www.hfm.com", serverPrefixes: ["HFM-"] },
  { id: "ironfx", name: "IronFX", logo: "/brokers/ironfx.png", website: "https://www.ironfx.com", serverPrefixes: ["IronFX-"] },
  { id: "justmarkets", name: "JustMarkets", logo: "/brokers/justmarkets.png", website: "https://justmarkets.com", serverPrefixes: ["JustMarkets-"] },
  { id: "litefinance", name: "LiteFinance", logo: "/brokers/litefinance.png", website: "https://www.litefinance.org", serverPrefixes: ["LiteFinance-"] },
  { id: "metaquotes", name: "MetaQuotes", logo: "/brokers/metaquotes.png", website: "https://www.metaquotes.net", serverPrefixes: ["MetaQuotes-"] },
  { id: "octa", name: "Octa", logo: "/brokers/octa.png", website: "https://www.octafx.com", serverPrefixes: ["OctaFX-"] },
  { id: "roboforex", name: "RoboForex", logo: "/brokers/roboforex.png", website: "https://roboforex.com", serverPrefixes: ["RoboForex-"] },
  { id: "tickmill", name: "Tickmill", logo: "/brokers/tickmill.png", website: "https://www.tickmill.com", serverPrefixes: ["Tickmill-"] },
  { id: "vantage", name: "Vantage", logo: "/brokers/vantage.png", website: "https://www.vantagemarkets.com", serverPrefixes: ["VantageInternational-"] },
  { id: "xm", name: "XM", logo: "/brokers/xm.png", website: "https://www.xm.com", serverPrefixes: ["XMGlobal-"] },
];

export function brokerBrandForServer(server?: string): BrokerBrand | undefined {
  if (!server) return undefined;
  return BROKER_BRANDS.find((brand) =>
    brand.serverPrefixes.some((prefix) => server.startsWith(prefix))
  );
}

export function groupBrokerServers(options: BrokerServerOption[]): BrokerBrandGroup[] {
  return BROKER_BRANDS.map((brand) => ({
    ...brand,
    servers: options.filter((option) =>
      brand.serverPrefixes.some((prefix) => option.value.startsWith(prefix))
    ),
  })).filter((brand) => brand.servers.length > 0);
}

export function brokerServerKind(server: string): "live" | "demo" {
  return /demo|trial|practice/i.test(server) ? "demo" : "live";
}

const FOREX_CURRENCIES = new Set([
  "USD",
  "EUR",
  "GBP",
  "JPY",
  "AUD",
  "NZD",
  "CAD",
  "CHF",
  "DKK",
  "HKD",
  "HUF",
  "MXN",
  "NOK",
  "PLN",
  "SEK",
  "SGD",
  "TRY",
  "ZAR",
]);

const CRYPTO_COINS = new Set([
  "BTC",
  "ETH",
  "SOL",
  "ADA",
  "DOT",
  "XRP",
  "LTC",
  "BNB",
  "DOGE",
  "USDT",
  "USDC",
  "AVAX",
  "LINK",
  "MATIC",
  "XLM",
  "TRX",
  "BCH",
  "ATOM",
  "NEAR",
  "APT",
  "ARB",
  "OP",
  "FIL",
  "ICP",
  "UNI",
  "SHIB",
]);

const FINANCIAL_FLAG_KEYS = new Set([
  "xauusd",
  "usdsilver",
  "platinum",
  "spot",
  "audcad",
  "audchf",
  "audjpy",
  "audnzd",
  "audusd",
  "cadchf",
  "cadjpy",
  "chfjpy",
  "euraud",
  "eurcad",
  "eurchf",
  "eurdkk",
  "eurgbp",
  "eurhuf",
  "eurjpy",
  "eurnok",
  "eurnzd",
  "eurpln",
  "eurtry",
  "eurusd",
  "gbpaud",
  "gbpcad",
  "gbpchf",
  "gbpjpy",
  "gbpnzd",
  "gbpusd",
  "nzdcad",
  "nzdchf",
  "nzdjpy",
  "nzdusd",
  "sgdjpy",
  "usdcad",
  "usdchf",
  "usddkk",
  "usdhkd",
  "usdhuf",
  "usdjpy",
  "usdmxn",
  "usdpln",
  "usdsek",
  "usdsgd",
  "usdtry",
  "usdzar",
  "btcusd",
  "ethusd",
  "xrpusd",
  "ltcusd",
  "bchusd",
  "adausd",
  "dotusd",
  "xlmusd",
]);

const INDEX_LOGO_RULES: Array<{ pattern: RegExp; path: string }> = [
  { pattern: /US30|DJ30|DOW|WALLSTREET/i, path: "source/CBOT" },
  { pattern: /US500|SP500|SPX|S&P/i, path: "source/CME" },
  { pattern: /NAS|USTEC|NDX|US100|NAS100|NASDAQ/i, path: "source/NASDAQ" },
  { pattern: /DAX|DE40|GER40|GERMANY/i, path: "source/XETR" },
  { pattern: /UK100|FTSE|UKX/i, path: "source/LSE" },
  { pattern: /JP225|NI225|NIKKEI|JPN225/i, path: "source/TSE" },
];

const CURRENCY_TO_FLAG: Record<string, string> = {
  USD: "us",
  EUR: "eu",
  GBP: "gb",
  JPY: "jp",
  AUD: "au",
  NZD: "nz",
  CAD: "ca",
  CHF: "ch",
  CNH: "cn",
  CNY: "cn",
  HKD: "hk",
  SGD: "sg",
  NOK: "no",
  SEK: "se",
  MXN: "mx",
  ZAR: "za",
  TRY: "tr",
  PLN: "pl",
  DKK: "dk",
  HUF: "hu",
};

export type SymbolIconKind =
  | "financial-flag"
  | "tradingview"
  | "circle-flag"
  | "fallback";

export interface ResolvedSymbolIcon {
  kind: SymbolIconKind;
  key?: string;
  tradingViewPath?: string;
  flagCode?: string;
}

export function normalizeSymbol(symbol: string): string {
  return symbol
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, "")
    .replace(/(CASH|ECN|PRO|MINI|MICRO|STD|RAW|ZERO|SPOT)$/i, "");
}

function resolveForexPair(normalized: string): string | null {
  if (normalized.length < 6) return null;

  const pair = normalized.slice(0, 6);
  const base = pair.slice(0, 3);
  const quote = pair.slice(3, 6);

  if (!FOREX_CURRENCIES.has(base) || !FOREX_CURRENCIES.has(quote)) {
    return null;
  }

  const key = pair.toLowerCase();
  return FINANCIAL_FLAG_KEYS.has(key) ? key : null;
}

function resolveCommodity(normalized: string): string | null {
  if (/XAU|GOLD/.test(normalized)) return "xauusd";
  if (/XAG|SILVER/.test(normalized)) return "usdsilver";
  if (/XPT|PLATINUM/.test(normalized)) return "platinum";
  return null;
}

function resolveCrypto(normalized: string): string | null {
  for (const coin of CRYPTO_COINS) {
    if (normalized === coin || normalized.startsWith(coin)) {
      return coin.toLowerCase();
    }
  }

  const pairMatch = normalized.match(/^([A-Z]{3,5})(USD|USDT)$/);
  if (pairMatch) {
    const key = `${pairMatch[1]}${pairMatch[2]}`.toLowerCase();
    if (FINANCIAL_FLAG_KEYS.has(key)) return key;
  }

  return null;
}

function resolveIndex(normalized: string): string | null {
  for (const rule of INDEX_LOGO_RULES) {
    if (rule.pattern.test(normalized)) {
      return rule.path;
    }
  }
  return null;
}

function resolveSingleCurrency(normalized: string): string | null {
  if (normalized.length !== 3) return null;
  return CURRENCY_TO_FLAG[normalized] ?? null;
}

export function resolveSymbolIcon(symbol: string): ResolvedSymbolIcon {
  const normalized = normalizeSymbol(symbol);

  const indexPath = resolveIndex(normalized);
  if (indexPath) {
    return { kind: "tradingview", tradingViewPath: indexPath };
  }

  const commodityKey = resolveCommodity(normalized);
  if (commodityKey) {
    return { kind: "financial-flag", key: commodityKey };
  }

  const forexKey = resolveForexPair(normalized);
  if (forexKey) {
    return { kind: "financial-flag", key: forexKey };
  }

  const cryptoKey = resolveCrypto(normalized);
  if (cryptoKey) {
    return { kind: "financial-flag", key: cryptoKey };
  }

  const flagCode = resolveSingleCurrency(normalized);
  if (flagCode) {
    return { kind: "circle-flag", flagCode };
  }

  return { kind: "fallback" };
}

export const TRADING_VIEW_LOGO_BASE =
  "https://s3-symbol-logo.tradingview.com";

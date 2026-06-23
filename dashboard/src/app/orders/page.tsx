"use client";

import { useDashboard } from "@/components/layout/dashboard-layout";
import { OrderForm } from "@/components/orders/order-form";
import { PageHeader, SectionPanel, PanelHeader, PanelBody, EmptyState } from "@/components/layout";
import { formatNumber } from "@/lib/utils";
import { getSymbolPrice, getSymbols, type SymbolListItem } from "@/lib/api";
import { useEffect, useState, useRef, useCallback } from "react";
import { TrendingUp, TrendingDown, Activity } from "lucide-react";
import { SymbolCell } from "@/components/dashboard/symbol-icon";
import { PageContainer, AnimatedSection } from "@/components/motion";

interface PriceData {
  symbol: string;
  bid: number;
  ask: number;
  spread: number;
}

export default function OrdersPage() {
  const { reconnect, session } = useDashboard();
  const [symbols, setSymbols] = useState<SymbolListItem[]>([]);
  const [prices, setPrices] = useState<Record<string, PriceData>>({});
  const [isLoadingSymbols, setIsLoadingSymbols] = useState(true);
  const [isLoadingPrices, setIsLoadingPrices] = useState(true);
  const symbolsRef = useRef<SymbolListItem[]>([]);

  useEffect(() => {
    setIsLoadingSymbols(true);
    setSymbols([]);
    setPrices({});
    symbolsRef.current = [];
    const fetchSymbols = async () => {
      try {
        const fetchedSymbols = await getSymbols();
        setSymbols(fetchedSymbols);
        symbolsRef.current = fetchedSymbols;
      } catch (error) {
        console.error("Failed to fetch symbols:", error);
      } finally {
        setIsLoadingSymbols(false);
      }
    };
    fetchSymbols();
  }, [session.activeAccountId]);

  const fetchPrices = useCallback(async () => {
    const currentSymbols = symbolsRef.current;
    if (currentSymbols.length === 0) return;

    try {
      const results = await Promise.all(
        currentSymbols.map(async (s) => {
          try {
            const price = await getSymbolPrice(s.value);
            return { symbol: s.value, data: price };
          } catch {
            return null;
          }
        })
      );

      const priceMap: Record<string, PriceData> = {};
      results.forEach((result) => {
        if (result?.data) priceMap[result.symbol] = result.data;
      });
      setPrices(priceMap);
    } catch (error) {
      console.error("Failed to fetch prices:", error);
    } finally {
      setIsLoadingPrices(false);
    }
  }, []);

  useEffect(() => {
    if (symbols.length === 0) return;
    fetchPrices();
    const interval = setInterval(fetchPrices, 2000);
    return () => clearInterval(interval);
  }, [symbols, fetchPrices]);

  return (
    <PageContainer className="max-w-[1400px]">
      <AnimatedSection>
        <PageHeader
          meta="Execution"
          title="New order"
          description="Place a market or pending order"
        />
      </AnimatedSection>

      <AnimatedSection className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <OrderForm onSuccess={reconnect} accountId={session.activeAccountId} />

        <SectionPanel>
          <PanelHeader
            eyebrow="Markets"
            title="Live prices"
            action={
              <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-bg-tertiary border border-border-subtle text-[10px] text-text-muted">
                <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
                Streaming
              </span>
            }
          />
          <PanelBody flush>
            {isLoadingSymbols || isLoadingPrices ? (
              <EmptyState
                compact
                icon={<Activity className="w-5 h-5 animate-pulse" />}
                title={
                  isLoadingSymbols ? "Loading symbols…" : "Loading prices…"
                }
              />
            ) : symbols.length === 0 ? (
              <EmptyState title="No symbols available" />
            ) : (
              <div className="overflow-x-auto max-h-[640px] overflow-y-auto">
                <table className="w-full data-table">
                  <thead className="sticky top-0 bg-bg-secondary z-10">
                    <tr className="border-b border-border-subtle bg-bg-tertiary/30">
                      <th className="px-6 py-3 text-left">Symbol</th>
                      <th className="px-6 py-3 text-right">Bid</th>
                      <th className="px-6 py-3 text-right">Ask</th>
                      <th className="px-6 py-3 text-right">Spread</th>
                    </tr>
                  </thead>
                  <tbody>
                    {symbols.map((symbol) => {
                      const price = prices[symbol.value];
                      return (
                        <tr
                          key={symbol.value}
                          className="border-b border-border-subtle last:border-0 hover:bg-bg-tertiary/30"
                        >
                          <td className="px-6 py-4">
                            <SymbolCell
                              symbol={symbol.value}
                              label={symbol.label}
                              size="sm"
                            />
                          </td>
                          <td className="px-6 py-4 text-right">
                            <span className="inline-flex items-center justify-end gap-1 text-sm text-danger tabular-nums font-mono">
                              <TrendingDown className="w-3 h-3" />
                              {price ? formatNumber(price.bid, 5) : "-"}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-right">
                            <span className="inline-flex items-center justify-end gap-1 text-sm text-success tabular-nums font-mono">
                              <TrendingUp className="w-3 h-3" />
                              {price ? formatNumber(price.ask, 5) : "-"}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-right text-sm text-text-secondary tabular-nums">
                            {price ? formatNumber(price.spread, 1) : "-"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </PanelBody>
        </SectionPanel>
      </AnimatedSection>
    </PageContainer>
  );
}

import { describe, expect, it } from "vitest";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { MT5_BROKER_SERVER_OPTIONS } from "./broker-servers";
import {
  BROKER_BRANDS,
  brokerBrandForServer,
  brokerServerKind,
  groupBrokerServers,
} from "./broker-brands";

describe("broker brands", () => {
  it("maps every seeded server to a visible broker brand", () => {
    for (const option of MT5_BROKER_SERVER_OPTIONS) {
      expect(brokerBrandForServer(option.value), option.value).toBeDefined();
    }
  });

  it("keeps one searchable group per supported brand", () => {
    const groups = groupBrokerServers(MT5_BROKER_SERVER_OPTIONS);
    expect(groups).toHaveLength(BROKER_BRANDS.length);
    expect(groups.find((group) => group.id === "exness")?.servers).toHaveLength(4);
  });

  it("ships a local image asset for every broker", () => {
    for (const brand of BROKER_BRANDS) {
      expect(existsSync(join(process.cwd(), "public", brand.logo)), brand.name).toBe(true);
    }
  });

  it("recognizes demo and practice servers", () => {
    expect(brokerServerKind("Pepperstone-Demo")).toBe("demo");
    expect(brokerServerKind("OANDA-v20 Practice-1")).toBe("demo");
    expect(brokerServerKind("AMarkets-Real")).toBe("live");
  });
});

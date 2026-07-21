import { describe, expect, it } from "vitest";

import { getPresetDates } from "./time-range-filter";

describe("getPresetDates", () => {
  it("returns the current calendar year through tomorrow", () => {
    const now = new Date(2026, 6, 21, 12);

    expect(getPresetDates("this_year", now)).toEqual({
      from: "2026-01-01",
      to: "2026-07-22",
    });
  });

  it("keeps preset dates in the user's local calendar", () => {
    const now = new Date(2026, 0, 1, 12);

    expect(getPresetDates("today", now)).toEqual({
      from: "2026-01-01",
      to: "2026-01-02",
    });
  });
});

import { describe, expect, it } from "vitest";

import {
  allocateEqual,
  formatTHB,
  fromApiAmount,
  parseAmount,
  sumSatang,
  toApiAmount,
} from "./money";

function satang(input: string): number {
  const result = parseAmount(input);
  if (!result.ok) throw new Error(result.error);
  return result.satang;
}

describe("parseAmount", () => {
  it.each([
    ["1000", 100000],
    ["1000.00", 100000],
    ["1,000.5", 100050],
    ["0.30", 30],
    ["0.1", 10],
    ["007.10", 710],
    ["1000.", 100000],
    ["9999999999.99", 999999999999],
  ])("parses %s", (input, expected) => {
    expect(satang(input)).toBe(expected);
  });

  it.each([
    ["", "Enter an amount"],
    ["10.005", "at most 2 decimal places"],
    ["0", "greater than zero"],
    ["0.00", "greater than zero"],
    ["-5", "digits only"],
    ["1e3", "digits only"],
    ["abc", "digits only"],
    ["10000000000.00", "too large"],
  ])("rejects %j", (input, message) => {
    const result = parseAmount(input);
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toContain(message);
  });
});

describe("formatTHB", () => {
  it("uses thousands separators and two decimals", () => {
    expect(formatTHB(100000)).toBe("1,000.00");
    expect(formatTHB(123456789)).toBe("1,234,567.89");
    expect(formatTHB(5)).toBe("0.05");
    expect(formatTHB(-33333)).toBe("-333.33");
    expect(formatTHB(0)).toBe("0.00");
  });

  it("shows 0.1 + 0.2 as 0.30, free of floating-point error", () => {
    expect(0.1 + 0.2).not.toBe(0.3); // the problem being avoided
    expect(formatTHB(sumSatang([satang("0.1"), satang("0.2")]))).toBe("0.30");
  });
});

describe("allocateEqual", () => {
  it("matches the backend: 100.00 / 3 = 33.34, 33.33, 33.33", () => {
    expect(allocateEqual(satang("100.00"), 3).map(formatTHB)).toEqual(["33.34", "33.33", "33.33"]);
  });

  it("gives leftover satang to the first members listed and always sums to the total", () => {
    expect(allocateEqual(5, 3)).toEqual([2, 2, 1]);
    expect(allocateEqual(2, 3)).toEqual([1, 1, 0]);
    for (const total of [1, 99, 100000, 999999999999]) {
      for (const count of [1, 2, 3, 7]) {
        expect(sumSatang(allocateEqual(total, count))).toBe(total);
      }
    }
  });

  it("returns nothing for zero members", () => {
    expect(allocateEqual(100, 0)).toEqual([]);
  });
});

describe("API amount conversion", () => {
  it("round-trips the API string format", () => {
    expect(toApiAmount(100000)).toBe("1000.00");
    expect(toApiAmount(5)).toBe("0.05");
    expect(fromApiAmount("-333.33")).toBe(-33333);
    expect(fromApiAmount("666.66")).toBe(66666);
  });
});

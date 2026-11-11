/**
 * Money helpers. Amounts are held as integer satang (1 THB = 100 satang) and only ever added,
 * subtracted or divided with integer results, so no floating-point rounding can creep in:
 * "0.1" + "0.2" is 10 + 20 = 30 satang, displayed as "0.30".
 *
 * The largest amount the API accepts is 9,999,999,999.99 THB = 999,999,999,999 satang, well
 * inside Number.MAX_SAFE_INTEGER (about 9.007e15), so plain numbers are exact here.
 */

export type Satang = number;

export const MAX_SATANG: Satang = 999_999_999_999;

export type ParseResult = { ok: true; satang: Satang } | { ok: false; error: string };

const AMOUNT_RE = /^(\d+)(?:\.(\d*))?$/;

/** Parse user input such as "1000", "1,000.5" or "0.30" into satang. */
export function parseAmount(input: string): ParseResult {
  const cleaned = input.trim().replace(/,/g, "");
  if (cleaned === "") return { ok: false, error: "Enter an amount" };
  const match = AMOUNT_RE.exec(cleaned);
  if (!match) return { ok: false, error: "Use digits only, for example 1,000.00" };
  const [, whole, fraction = ""] = match;
  if (fraction.length > 2) return { ok: false, error: "Use at most 2 decimal places" };
  const wholeDigits = whole.replace(/^0+(?=\d)/, "");
  if (wholeDigits.length > 10) return { ok: false, error: "Amount is too large" };
  const satang = Number(wholeDigits) * 100 + Number(fraction.padEnd(2, "0"));
  if (satang > MAX_SATANG) return { ok: false, error: "Amount is too large" };
  if (satang <= 0) return { ok: false, error: "Amount must be greater than zero" };
  return { ok: true, satang };
}

/** Parse an amount string coming back from the API ("-333.33", "0.00"). */
export function fromApiAmount(value: string): Satang {
  const match = /^(-?)(\d+)\.(\d{2})$/.exec(value);
  if (!match) throw new Error(`Unexpected amount from API: ${value}`);
  const [, sign, whole, fraction] = match;
  const satang = Number(whole) * 100 + Number(fraction);
  return sign === "-" ? -satang : satang;
}

/** Render satang as the "1000.00" string the API expects. */
export function toApiAmount(satang: Satang): string {
  return `${Math.trunc(satang / 100)}.${String(satang % 100).padStart(2, "0")}`;
}

/** Thai-style display with thousands separators: 100000 -> "1,000.00", -33333 -> "-333.33". */
export function formatTHB(satang: Satang): string {
  assertInteger(satang);
  const sign = satang < 0 ? "-" : "";
  const abs = Math.abs(satang);
  const whole = String(Math.trunc(abs / 100)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${sign}${whole}.${String(abs % 100).padStart(2, "0")}`;
}

/**
 * Same rule as the backend: split into `count` shares that differ by at most one satang and
 * give the leftover satang, one each, to the first members in the order listed.
 * 10000 / 3 -> [3334, 3333, 3333].
 */
export function allocateEqual(total: Satang, count: number): Satang[] {
  assertInteger(total);
  if (count <= 0) return [];
  const base = Math.floor(total / count);
  const remainder = total - base * count;
  return Array.from({ length: count }, (_, i) => base + (i < remainder ? 1 : 0));
}

export function sumSatang(values: Satang[]): Satang {
  return values.reduce((acc, v) => acc + v, 0);
}

function assertInteger(value: number): void {
  if (!Number.isSafeInteger(value)) throw new Error(`Not an integer satang amount: ${value}`);
}

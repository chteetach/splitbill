"use client";

import { useMemo, useRef, useState } from "react";

import { allocateEqual, formatTHB, parseAmount, sumSatang, toApiAmount } from "@/lib/money";
import type { NewExpense } from "@/lib/types";

type SplitType = "equal" | "exact";

type Props = {
  members: string[];
  currentUser: string;
  onSubmit: (expense: NewExpense, idempotencyKey: string) => Promise<boolean>;
};

const inputClass =
  "w-full rounded border border-gray-300 px-2 py-1.5 focus:border-blue-500 focus:outline-none";

export function ExpenseForm({ members, currentUser, onSubmit }: Props) {
  const [description, setDescription] = useState("");
  const [amountInput, setAmountInput] = useState("");
  const [paidBy, setPaidBy] = useState(members.includes(currentUser) ? currentUser : members[0]);
  const [splitType, setSplitType] = useState<SplitType>("equal");
  const [included, setIncluded] = useState<string[]>(members);
  const [exactInputs, setExactInputs] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  // One key per distinct submission: a retry of the same form (e.g. after a network error)
  // reuses it so the server can deduplicate; any edit to the form starts a new one.
  const idempotencyKey = useRef<string | null>(null);
  const edit = <T,>(setter: (value: T) => void) => (value: T) => {
    idempotencyKey.current = null;
    setter(value);
  };

  const amount = parseAmount(amountInput);
  const total = amount.ok ? amount.satang : 0;

  const preview = useMemo(() => {
    if (splitType === "equal") {
      const selected = members.filter((m) => included.includes(m));
      const shares = allocateEqual(total, selected.length);
      return {
        rows: selected.map((m, i) => ({ member: m, satang: shares[i], error: null as string | null })),
        unallocated: 0,
        valid: amount.ok && selected.length > 0,
      };
    }
    const rows = members.map((m) => {
      const raw = exactInputs[m] ?? "";
      if (raw.trim() === "") return { member: m, satang: 0, error: null };
      const parsed = parseAmount(raw);
      return parsed.ok
        ? { member: m, satang: parsed.satang, error: null }
        : { member: m, satang: 0, error: parsed.error };
    });
    const allocated = sumSatang(rows.map((r) => r.satang));
    const hasErrors = rows.some((r) => r.error);
    return {
      rows,
      unallocated: total - allocated,
      valid: amount.ok && !hasErrors && allocated === total && allocated > 0,
    };
  }, [splitType, members, included, exactInputs, total, amount.ok]);

  const canSubmit = description.trim() !== "" && preview.valid && !submitting;

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;
    const expense: NewExpense = {
      description: description.trim(),
      paid_by: paidBy,
      amount: toApiAmount(total),
      split:
        splitType === "equal"
          ? { type: "equal", members: preview.rows.map((r) => r.member) }
          : {
              type: "exact",
              shares: Object.fromEntries(
                preview.rows.filter((r) => r.satang > 0).map((r) => [r.member, toApiAmount(r.satang)]),
              ),
            },
    };
    idempotencyKey.current ??= crypto.randomUUID();
    setSubmitting(true);
    const ok = await onSubmit(expense, idempotencyKey.current);
    setSubmitting(false);
    if (ok) {
      idempotencyKey.current = null;
      setDescription("");
      setAmountInput("");
      setExactInputs({});
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block sm:col-span-2">
          <span className="text-sm text-gray-600">Description</span>
          <input
            className={inputClass}
            value={description}
            maxLength={200}
            placeholder="Dinner at the night market"
            onChange={(e) => edit(setDescription)(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="text-sm text-gray-600">Amount (THB)</span>
          <input
            className={inputClass}
            inputMode="decimal"
            value={amountInput}
            placeholder="1,000.00"
            onChange={(e) => edit(setAmountInput)(e.target.value)}
          />
          {amountInput && !amount.ok && <span className="text-sm text-red-600">{amount.error}</span>}
        </label>
        <label className="block">
          <span className="text-sm text-gray-600">Paid by</span>
          <select className={inputClass} value={paidBy} onChange={(e) => edit(setPaidBy)(e.target.value)}>
            {members.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
      </div>

      <fieldset>
        <legend className="text-sm text-gray-600">Split</legend>
        <div className="mt-1 flex gap-4">
          {(["equal", "exact"] as const).map((type) => (
            <label key={type} className="flex items-center gap-1.5">
              <input
                type="radio"
                name="split-type"
                checked={splitType === type}
                onChange={() => edit(setSplitType)(type)}
              />
              {type === "equal" ? "Equally among selected" : "Exact amounts"}
            </label>
          ))}
        </div>
      </fieldset>

      <div className="rounded border border-gray-200">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-gray-600">
            <tr>
              <th className="px-3 py-2">Member</th>
              <th className="px-3 py-2 text-right">Share (THB)</th>
            </tr>
          </thead>
          <tbody>
            {members.map((member) => {
              const row = preview.rows.find((r) => r.member === member);
              return (
                <tr key={member} className="border-t border-gray-100">
                  <td className="px-3 py-2">
                    {splitType === "equal" ? (
                      <label className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={included.includes(member)}
                          onChange={(e) =>
                            edit(setIncluded)(
                              e.target.checked
                                ? [...included, member]
                                : included.filter((m) => m !== member),
                            )
                          }
                        />
                        {member}
                      </label>
                    ) : (
                      member
                    )}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {splitType === "equal" ? (
                      row ? formatTHB(row.satang) : <span className="text-gray-400">not included</span>
                    ) : (
                      <>
                        <input
                          className={`${inputClass} max-w-36 text-right`}
                          inputMode="decimal"
                          aria-label={`Share for ${member}`}
                          placeholder="0.00"
                          value={exactInputs[member] ?? ""}
                          onChange={(e) =>
                            edit(setExactInputs)({ ...exactInputs, [member]: e.target.value })
                          }
                        />
                        {row?.error && <div className="text-red-600">{row.error}</div>}
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
          {splitType === "exact" && (
            <tfoot>
              <tr className="border-t border-gray-200">
                <td className="px-3 py-2 font-medium">Unallocated</td>
                <td
                  className={`px-3 py-2 text-right font-medium tabular-nums ${
                    preview.unallocated === 0 ? "text-green-700" : "text-red-600"
                  }`}
                >
                  {formatTHB(preview.unallocated)}
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
      {splitType === "exact" && amount.ok && preview.unallocated !== 0 && (
        <p className="text-sm text-red-600">
          {preview.unallocated > 0
            ? `Assign another ${formatTHB(preview.unallocated)} THB before saving.`
            : `The shares are ${formatTHB(-preview.unallocated)} THB more than the total.`}
        </p>
      )}
      {splitType === "equal" && included.length === 0 && (
        <p className="text-sm text-red-600">Select at least one member.</p>
      )}

      <button
        type="submit"
        disabled={!canSubmit}
        className="rounded bg-blue-600 px-4 py-2 font-medium text-white disabled:cursor-not-allowed disabled:bg-gray-300"
      >
        {submitting ? "Saving..." : "Add expense"}
      </button>
    </form>
  );
}

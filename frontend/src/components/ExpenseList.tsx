import { formatTHB, fromApiAmount } from "@/lib/money";
import type { Expense } from "@/lib/types";

type Props = {
  expenses: Expense[];
  currentUser: string;
  onDelete: (expense: Expense) => void;
};

const dateFormat = new Intl.DateTimeFormat("th-TH", { dateStyle: "medium", timeStyle: "short" });

export function ExpenseList({ expenses, currentUser, onDelete }: Props) {
  if (expenses.length === 0) return <p className="text-sm text-gray-500">No expenses yet.</p>;
  return (
    <ul className="divide-y divide-gray-100">
      {expenses.map((expense) => (
        <li key={expense.id} className="py-3">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="font-medium">{expense.description}</p>
              <p className="text-sm text-gray-500">
                Paid by {expense.paid_by} · {dateFormat.format(new Date(expense.created_at))} ·{" "}
                {expense.split_type === "equal" ? "split equally" : "exact split"}
              </p>
            </div>
            <div className="text-right">
              <p className="font-medium tabular-nums">{formatTHB(fromApiAmount(expense.amount))} THB</p>
              {expense.paid_by === currentUser && (
                <button
                  type="button"
                  onClick={() => onDelete(expense)}
                  className="text-sm text-red-600 hover:underline"
                >
                  Delete
                </button>
              )}
            </div>
          </div>
          <p className="mt-1 text-sm text-gray-600">
            {expense.shares
              .map((s) => `${s.user} ${formatTHB(fromApiAmount(s.amount))}`)
              .join(" · ")}
          </p>
        </li>
      ))}
    </ul>
  );
}

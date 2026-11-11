import { formatTHB, fromApiAmount } from "@/lib/money";
import type { Balance, Settlement } from "@/lib/types";

type Props = { balances: Balance[]; settlements: Settlement[]; currentUser: string };

export function BalancesPanel({ balances, settlements, currentUser }: Props) {
  return (
    <div className="space-y-4">
      <ul className="divide-y divide-gray-100">
        {balances.map(({ user, balance }) => {
          const satang = fromApiAmount(balance);
          const you = user === currentUser ? " (you)" : "";
          return (
            <li key={user} className="flex items-center justify-between py-2">
              <span>
                {user}
                <span className="text-gray-500">{you}</span>
              </span>
              {satang > 0 ? (
                <span className="text-green-700">
                  is owed <strong className="tabular-nums">{formatTHB(satang)}</strong> THB
                </span>
              ) : satang < 0 ? (
                <span className="text-red-600">
                  owes <strong className="tabular-nums">{formatTHB(-satang)}</strong> THB
                </span>
              ) : (
                <span className="text-gray-500">settled up</span>
              )}
            </li>
          );
        })}
      </ul>

      <div>
        <h3 className="text-sm font-medium text-gray-600">To settle up</h3>
        {settlements.length === 0 ? (
          <p className="text-sm text-gray-500">Everyone is even.</p>
        ) : (
          <ul className="mt-1 space-y-1 text-sm">
            {settlements.map((s) => (
              <li key={`${s.from_user}-${s.to_user}`}>
                <strong>{s.from_user}</strong> pays <strong>{s.to_user}</strong>{" "}
                <span className="tabular-nums">{formatTHB(fromApiAmount(s.amount))}</span> THB
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

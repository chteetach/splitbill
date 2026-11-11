"use client";

import { useCallback, useEffect, useState } from "react";

import { BalancesPanel } from "@/components/BalancesPanel";
import { ExpenseForm } from "@/components/ExpenseForm";
import { ExpenseList } from "@/components/ExpenseList";
import { api, friendlyMessage } from "@/lib/api";
import type { Balance, Expense, Group, GroupSummary, NewExpense, Settlement } from "@/lib/types";

type GroupData = {
  group: Group;
  expenses: Expense[];
  balances: Balance[];
  settlements: Settlement[];
};

export default function Home() {
  const [users, setUsers] = useState<string[]>([]);
  const [currentUser, setCurrentUser] = useState("");
  const [groups, setGroups] = useState<GroupSummary[]>([]);
  const [groupId, setGroupId] = useState<number | null>(null);
  const [data, setData] = useState<GroupData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    api
      .listUsers()
      .then((list) => {
        setUsers(list.map((u) => u.username));
        setCurrentUser((u) => u || list[0]?.username || "");
      })
      .catch((e) => setError(friendlyMessage(e)));
  }, []);

  // Reset the group selection in the same update as the user change. Doing it in an effect
  // would leave one render where the new user is paired with the previous user's group.
  function selectUser(user: string) {
    setCurrentUser(user);
    setGroups([]);
    setGroupId(null);
    setData(null);
    setError(null);
    setNotice(null);
  }

  // Only the selected user's groups are listed.
  useEffect(() => {
    if (!currentUser) return;
    let stale = false;
    api
      .listGroups(currentUser)
      .then((list) => {
        if (stale) return;
        setGroups(list);
        setGroupId(list[0]?.id ?? null);
      })
      .catch((e) => !stale && setError(friendlyMessage(e)));
    return () => {
      stale = true;
    };
  }, [currentUser]);

  const fetchGroup = useCallback(async (user: string, id: number): Promise<GroupData> => {
    const [group, expenses, balances, settle] = await Promise.all([
      api.getGroup(user, id),
      api.listExpenses(user, id),
      api.getBalances(user, id),
      api.getSettleUp(user, id),
    ]);
    return { group, expenses, balances: balances.balances, settlements: settle.payments };
  }, []);

  useEffect(() => {
    if (!currentUser || groupId === null) return;
    // Ignore responses for a selection the user has already moved away from.
    let stale = false;
    fetchGroup(currentUser, groupId)
      .then((d) => !stale && setData(d))
      .catch((e) => !stale && setError(friendlyMessage(e)));
    return () => {
      stale = true;
    };
  }, [currentUser, groupId, fetchGroup]);

  async function reload() {
    if (groupId === null) return;
    setData(await fetchGroup(currentUser, groupId));
  }

  async function handleCreate(expense: NewExpense, idempotencyKey: string): Promise<boolean> {
    if (groupId === null) return false;
    setError(null);
    setNotice(null);
    try {
      await api.createExpense(currentUser, groupId, expense, idempotencyKey);
      setNotice(`Added "${expense.description}".`);
      await reload().catch((e) => setError(friendlyMessage(e)));
      return true;
    } catch (e) {
      setError(friendlyMessage(e));
      return false;
    }
  }

  async function handleDelete(expense: Expense) {
    if (groupId === null) return;
    if (!window.confirm(`Delete "${expense.description}"?`)) return;
    setError(null);
    setNotice(null);
    try {
      await api.deleteExpense(currentUser, groupId, expense.id);
      setNotice(`Deleted "${expense.description}".`);
    } catch (e) {
      setError(friendlyMessage(e));
    }
    await reload().catch((e) => setError(friendlyMessage(e)));
  }

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-4 sm:p-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-2xl font-semibold">SplitBill</h1>
        <div className="flex flex-wrap gap-3">
          <label className="text-sm">
            <span className="block text-gray-600">Signed in as</span>
            <select
              className="rounded border border-gray-300 px-2 py-1.5"
              value={currentUser}
              onChange={(e) => selectUser(e.target.value)}
            >
              {users.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="block text-gray-600">Group</span>
            <select
              className="rounded border border-gray-300 px-2 py-1.5"
              value={groupId ?? ""}
              onChange={(e) => {
                setData(null);
                setError(null);
                setNotice(null);
                setGroupId(Number(e.target.value));
              }}
              disabled={groups.length === 0}
            >
              {groups.length === 0 && <option value="">No groups</option>}
              {groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      {error && (
        <div role="alert" className="rounded border border-red-200 bg-red-50 px-4 py-3 text-red-700">
          {error}
        </div>
      )}
      {notice && !error && (
        <div role="status" className="rounded border border-green-200 bg-green-50 px-4 py-3 text-green-800">
          {notice}
        </div>
      )}

      {data && (
        <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
          <section className="space-y-6">
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <h2 className="mb-3 text-lg font-medium">Add an expense to {data.group.name}</h2>
              <ExpenseForm
                key={`${data.group.id}-${currentUser}`}
                members={data.group.members}
                currentUser={currentUser}
                onSubmit={handleCreate}
              />
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <h2 className="mb-2 text-lg font-medium">Expenses</h2>
              <ExpenseList expenses={data.expenses} currentUser={currentUser} onDelete={handleDelete} />
            </div>
          </section>
          <section className="h-fit rounded-lg border border-gray-200 bg-white p-4">
            <h2 className="mb-2 text-lg font-medium">Balances</h2>
            <BalancesPanel
              balances={data.balances}
              settlements={data.settlements}
              currentUser={currentUser}
            />
          </section>
        </div>
      )}
    </main>
  );
}

// Shapes returned by the SplitBill API. Amounts are strings such as "1000.00".

export type GroupSummary = { id: number; name: string };

export type Group = GroupSummary & { members: string[] };

export type Share = { user: string; amount: string };

export type Expense = {
  id: number;
  group_id: number;
  description: string;
  paid_by: string;
  amount: string;
  split_type: "equal" | "exact";
  shares: Share[];
  created_by: string;
  created_at: string;
};

export type Balance = { user: string; balance: string };

export type Settlement = { from_user: string; to_user: string; amount: string };

export type NewExpense = {
  description: string;
  paid_by: string;
  amount: string;
  split:
    | { type: "equal"; members: string[] }
    | { type: "exact"; shares: Record<string, string> };
};

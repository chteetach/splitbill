import type { Balance, Expense, Group, GroupSummary, NewExpense, Settlement } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details?: unknown,
  ) {
    super(message);
  }
}

type RequestOptions = {
  user?: string;
  method?: "GET" | "POST" | "DELETE";
  body?: unknown;
  idempotencyKey?: string;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.user) headers["X-User"] = options.user;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError(0, "network_error", "Could not reach the server");
  }

  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const error = data?.error;
    throw new ApiError(
      res.status,
      error?.code ?? "http_error",
      error?.message ?? `Request failed (${res.status})`,
      error?.details,
    );
  }
  return data as T;
}

export const api = {
  listUsers: () => request<{ username: string }[]>("/users"),
  listGroups: (user: string) => request<GroupSummary[]>("/groups", { user }),
  getGroup: (user: string, groupId: number) => request<Group>(`/groups/${groupId}`, { user }),
  listExpenses: (user: string, groupId: number) =>
    request<Expense[]>(`/groups/${groupId}/expenses`, { user }),
  getBalances: (user: string, groupId: number) =>
    request<{ group_id: number; balances: Balance[] }>(`/groups/${groupId}/balances`, { user }),
  getSettleUp: (user: string, groupId: number) =>
    request<{ group_id: number; payments: Settlement[] }>(`/groups/${groupId}/settle-up`, {
      user,
    }),
  createExpense: (user: string, groupId: number, expense: NewExpense, idempotencyKey: string) =>
    request<Expense>(`/groups/${groupId}/expenses`, {
      user,
      method: "POST",
      body: expense,
      idempotencyKey,
    }),
  deleteExpense: (user: string, groupId: number, expenseId: number) =>
    request<void>(`/groups/${groupId}/expenses/${expenseId}`, { user, method: "DELETE" }),
};

/** Turn any error from the API layer into a sentence a user can act on. */
export function friendlyMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return "Something went wrong. Please try again.";
  const users = (error.details as { users?: string[] } | undefined)?.users;
  switch (error.code) {
    case "network_error":
      return "Could not reach the server. Check that the API is running and try again.";
    case "shares_mismatch":
      return "The shares do not add up to the total.";
    case "not_group_member":
      return users?.length
        ? `Not a member of this group: ${users.join(", ")}.`
        : "Not a member of this group.";
    case "group_not_found":
      return "Not a member of this group, or the group does not exist.";
    case "not_payer":
      return "Only the person who paid can delete this expense.";
    case "expense_not_found":
      return "That expense no longer exists. The list has been refreshed.";
    case "duplicate_members":
      return "Each member can only be included once.";
    case "idempotency_key_reused":
      return "This expense was already submitted with different details. Please submit again.";
    case "unknown_user":
    case "unauthenticated":
      return "Please choose a valid user.";
    case "validation_error":
      return `Please check the form: ${error.message}`;
    case "internal_error":
      return "The server hit an unexpected problem. Please try again.";
    default:
      return error.message;
  }
}

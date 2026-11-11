import { describe, expect, it } from "vitest";

import { ApiError, friendlyMessage } from "./api";

describe("friendlyMessage", () => {
  it("explains shares that do not add up", () => {
    const err = new ApiError(422, "shares_mismatch", "The shares add up to 999.99 but ...");
    expect(friendlyMessage(err)).toBe("The shares do not add up to the total.");
  });

  it("names the users who are not group members", () => {
    const err = new ApiError(422, "not_group_member", "...", { users: ["dan"] });
    expect(friendlyMessage(err)).toBe("Not a member of this group: dan.");
  });

  it("handles a server that cannot be reached", () => {
    expect(friendlyMessage(new ApiError(0, "network_error", ""))).toMatch(/Could not reach/);
  });

  it("falls back to a generic message for unknown errors", () => {
    expect(friendlyMessage(new TypeError("boom"))).toBe("Something went wrong. Please try again.");
  });
});

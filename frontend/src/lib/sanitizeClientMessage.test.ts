import { describe, expect, it } from "vitest";
import { sanitizeClientMessage } from "./sanitizeClientMessage";

describe("sanitizeClientMessage", () => {
  it("strips leading undefined prefix", () => {
    expect(sanitizeClientMessage("undefinedHi there")).toBe("Hi there");
  });

  it("trims whitespace", () => {
    expect(sanitizeClientMessage("  hello  ")).toBe("hello");
  });
});

import { describe, expect, it } from "vitest";
import { messageHasActionableRfpDetails, shouldStartAutonomousPipeline } from "./rfpFlow";

describe("shouldStartAutonomousPipeline", () => {
  it("does not start on greeting plus vague book a room", () => {
    const msg = "Hi, how are you doing today? I want to book a room.";
    expect(messageHasActionableRfpDetails(msg)).toBe(false);
    expect(shouldStartAutonomousPipeline(msg)).toBe(false);
  });

  it("starts when dates and counts are present", () => {
    const msg = "We have 10 people arriving June 17 for two nights.";
    expect(shouldStartAutonomousPipeline(msg)).toBe(true);
  });
});

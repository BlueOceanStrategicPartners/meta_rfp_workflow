import { describe, expect, it } from "vitest";
import {
  cardsHaveIdentifiedFields,
  messageHasActionableRfpDetails,
  messageIsSocialGreeting,
  shouldEnsureRfpSession,
  shouldRunDebateExtraction,
  shouldStartAutonomousPipeline,
} from "./rfpFlow";

describe("shouldStartAutonomousPipeline", () => {
  it("does not start on greeting plus vague book a room", () => {
    const msg = "Hi, how are you doing today? I want to book a room.";
    expect(messageHasActionableRfpDetails(msg)).toBe(false);
    expect(shouldStartAutonomousPipeline(msg)).toBe(false);
  });

  it("starts when dates and counts are present", () => {
    const msg = "We have 10 people arriving June 17 for two nights.";
    expect(shouldRunDebateExtraction(msg)).toBe(false);
    expect(messageHasActionableRfpDetails(msg)).toBe(true);
  });

  it("does not start debate on multi-part planning questions", () => {
    const msg =
      "We need a room next week, actually not one room. We need several rooms. We have 100 participants. So how about your rooms? What kind of rooms you have?";
    expect(shouldRunDebateExtraction(msg)).toBe(false);
  });

  it("starts debate on long pasted RFP text", () => {
    const msg =
      `${"Corporate summit room block and catering. ".repeat(12)}We need breakout space and a full RFP package.`;
    expect(shouldRunDebateExtraction(msg)).toBe(true);
  });
});

describe("messageIsSocialGreeting", () => {
  it("detects hi how are you", () => {
    expect(messageIsSocialGreeting("Hi, how are you doing? Thank you very much.")).toBe(true);
    expect(shouldEnsureRfpSession("Hi, how are you doing? Thank you very much.")).toBe(false);
  });
});

describe("cardsHaveIdentifiedFields", () => {
  it("ignores placeholder organization shell", () => {
    expect(
      cardsHaveIdentifiedFields({
        event_overview: { company_name: "Your organization" },
        room_block: {},
        meeting_space: {},
      }),
    ).toBe(false);
  });

  it("shows when headcount is set", () => {
    expect(
      cardsHaveIdentifiedFields({
        event_overview: { company_name: "Your organization" },
        meeting_space: { headcount: 100 },
      }),
    ).toBe(true);
  });
});

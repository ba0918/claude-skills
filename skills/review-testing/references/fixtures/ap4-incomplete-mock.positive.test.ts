// AP4 POSITIVE — should be detected (CONFIRMED).
// Downstream reads response.metadata.requestId, but the mock omits metadata.
import { handle } from "../handler";

test("processes response", () => {
  const mockResponse = {
    status: "success",
    data: { userId: "123", name: "Alice" },
    // BAD: metadata missing -> handler that reads response.metadata.requestId breaks in integration.
  };
  expect(handle(mockResponse)).toBe("ok"); // passes here, fails against the real API shape.
});

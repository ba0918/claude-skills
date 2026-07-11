// AP4 NEGATIVE — must NOT be detected.
// Mock reproduces the complete real response schema, including metadata consumed downstream.
import { handle } from "../handler";

test("processes response", () => {
  const mockResponse = {
    status: "success",
    data: { userId: "123", name: "Alice" },
    metadata: { requestId: "req-789", timestamp: 1234567890 }, // full schema.
  };
  expect(handle(mockResponse)).toBe("ok");
});

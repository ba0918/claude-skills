// AP3 NEGATIVE — must NOT be detected.
// Only the genuinely slow/external service is mocked; the config write side effect still runs.
import { addItem } from "../registry";

test("detects duplicate", async () => {
  vi.mock("SlowExternalService"); // mock only the slow external call.
  await addItem(config);          // real config file write still happens.
  await expect(addItem(config)).rejects.toThrow(/duplicate/); // dedup works: side effect intact.
});

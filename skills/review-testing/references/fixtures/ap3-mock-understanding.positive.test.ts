// AP3 POSITIVE — should be detected (CONFIRMED).
// The test depends on a side effect (duplicate detection via the catalog write) that the mock erased.
import { addItem } from "../registry";

test("detects duplicate", async () => {
  // BAD: mocking ToolCatalog removes discoverAndCacheTools' side effect that dedup relies on.
  vi.mock("ToolCatalog", () => ({ discoverAndCacheTools: vi.fn().mockResolvedValue(undefined) }));
  await addItem(config);
  await expect(addItem(config)).rejects.toThrow(/duplicate/); // never throws: side effect gone.
});

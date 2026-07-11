// AP1 NEGATIVE — must NOT be detected (FALSE_POSITIVE if flagged)
// Asserts on the real component's accessible role, not on a mock artifact.
import { render, screen } from "@testing-library/react";
import { Page } from "../Page";

test("renders sidebar", () => {
  render(<Page />);
  // GOOD: verifies real rendered behavior via role.
  expect(screen.getByRole("navigation")).toBeInTheDocument();
});

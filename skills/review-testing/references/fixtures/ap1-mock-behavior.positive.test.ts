// AP1 POSITIVE — should be detected (CONFIRMED)
// The assertion only proves the mock rendered; it verifies nothing about real behavior.
import { render, screen } from "@testing-library/react";
import { Page } from "../Page";

test("renders sidebar", () => {
  render(<Page />);
  // BAD: asserts on a *-mock test id — tests the mock, not the component.
  expect(screen.getByTestId("sidebar-mock")).toBeInTheDocument();
});

import { render, screen } from "@testing-library/react";
import { DialogueBox } from "./DialogueBox";

test("renders children inside a status region", () => {
  render(<DialogueBox>41h to arrival</DialogueBox>);
  expect(screen.getByText("41h to arrival")).toBeInTheDocument();
});

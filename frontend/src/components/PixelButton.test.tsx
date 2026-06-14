import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PixelButton } from "./PixelButton";

test("renders label and fires onClick", async () => {
  const onClick = vi.fn();
  render(<PixelButton onClick={onClick}>SEND</PixelButton>);
  await userEvent.click(screen.getByRole("button", { name: "SEND" }));
  expect(onClick).toHaveBeenCalledOnce();
});

test("respects disabled", async () => {
  const onClick = vi.fn();
  render(<PixelButton onClick={onClick} disabled>SEND</PixelButton>);
  await userEvent.click(screen.getByRole("button", { name: "SEND" }));
  expect(onClick).not.toHaveBeenCalled();
});

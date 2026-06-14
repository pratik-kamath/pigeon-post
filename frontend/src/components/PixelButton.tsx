import type { ButtonHTMLAttributes } from "react";

export function PixelButton(props: ButtonHTMLAttributes<HTMLButtonElement>) {
  const { className = "", ...rest } = props;
  return <button className={`pk-button ${className}`} {...rest} />;
}

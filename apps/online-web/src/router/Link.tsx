import React from "react";
import { useRouter } from "./RouterContext";

export interface LinkProps extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
  to: string;
  activeClassName?: string;
  exact?: boolean;
}

export const Link: React.FC<LinkProps> = ({
  to,
  children,
  className = "",
  activeClassName = "",
  exact = false,
  onClick,
  ...rest
}) => {
  const { pathname, navigate } = useRouter();

  const isExternal =
    to.startsWith("http://") ||
    to.startsWith("https://") ||
    to.startsWith("mailto:") ||
    to.startsWith("tel:");

  const targetPath = to.split("?")[0].split("#")[0];
  const isActive = exact
    ? pathname === targetPath
    : targetPath === "/"
    ? pathname === "/"
    : pathname.startsWith(targetPath);

  const finalClassName = [className, isActive && activeClassName].filter(Boolean).join(" ");

  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (onClick) {
      onClick(e);
    }

    if (
      !e.defaultPrevented &&
      !isExternal &&
      e.button === 0 &&
      !e.metaKey &&
      !e.altKey &&
      !e.ctrlKey &&
      !e.shiftKey &&
      rest.target !== "_blank"
    ) {
      e.preventDefault();
      navigate(to);
    }
  };

  return (
    <a href={to} className={finalClassName} onClick={handleClick} {...rest}>
      {children}
    </a>
  );
};

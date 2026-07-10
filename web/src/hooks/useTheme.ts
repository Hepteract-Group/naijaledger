import { useEffect, useState } from "react";
import type { Theme } from "../theme";
import { applyTheme, resolveInitialTheme, toggleTheme } from "../theme";

export function useTheme(): { theme: Theme; onToggle: () => void } {
  const [theme, setTheme] = useState<Theme>(() => resolveInitialTheme());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  return {
    theme,
    onToggle: () => {
      setTheme((current) => toggleTheme(current));
    },
  };
}

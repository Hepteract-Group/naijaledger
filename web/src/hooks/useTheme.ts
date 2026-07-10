import { useEffect, useState } from "react";
import type { Theme } from "../theme";
import { applyTheme, resolveInitialTheme, toggleTheme } from "../theme";

export function useTheme(): { theme: Theme; onToggle: () => void } {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof document === "undefined") {
      return "light";
    }
    const initial = resolveInitialTheme();
    applyTheme(initial);
    return initial;
  });

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

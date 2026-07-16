import { useEffect, useState } from "react";

function getInitialTheme() {
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("ews-theme", theme);
  }, [theme]);

  const isLight = theme === "light";

  return (
    <button
      onClick={() => setTheme(isLight ? "dark" : "light")}
      title={isLight ? "Switch to dark theme" : "Switch to light theme"}
      style={{
        width: 30, height: 30, borderRadius: "50%",
        background: "var(--panel-2)", border: "1px solid var(--line-strong)",
        color: "var(--chalk-dim)", fontSize: 14,
        display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0,
      }}
    >
      {isLight ? "☾" : "☀"}
    </button>
  );
}

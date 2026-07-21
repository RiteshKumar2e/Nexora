"use client";

import { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";
import { useTheme } from "next-themes";

let counter = 0;

export default function Mermaid({ chart }: { chart: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    let cancelled = false;
    const id = `mermaid-${counter++}`;
    
    // Configure theme-aware diagram coloring
    const themeMode = resolvedTheme === "dark" ? "dark" : "default";
    mermaid.initialize({
      startOnLoad: false,
      theme: themeMode,
      securityLevel: "loose",
      themeVariables: {
        fontFamily: "var(--font-sans)",
        fontSize: "14px",
      }
    });

    mermaid
      .render(id, chart)
      .then(({ svg }) => {
        if (!cancelled && ref.current) {
          ref.current.innerHTML = svg;
          setError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(String(e?.message ?? e));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [chart, resolvedTheme]);

  if (error) {
    return <pre className="mermaid-error">Diagram error: {error}</pre>;
  }
  return <div className="mermaid-diagram" ref={ref} />;
}

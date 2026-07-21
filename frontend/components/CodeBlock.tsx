"use client";

import { useState, type ReactNode } from "react";
import { Check, Copy } from "lucide-react";

/** A fenced code block with a language label and a copy button. The already
 *  syntax-highlighted `<code>` element is passed through as `children`; `code`
 *  is the raw text used for copying. */
export default function CodeBlock({
  lang,
  code,
  children,
}: {
  lang?: string;
  code: string;
  children: ReactNode;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard may be unavailable (insecure context) — ignore */
    }
  }

  return (
    <div className="code-block">
      <div className="code-head">
        <span className="code-lang">{lang || "text"}</span>
        <button className="code-copy" onClick={copy} aria-label="Copy code">
          {copied ? <Check size={13} /> : <Copy size={13} />}
          <span>{copied ? "Copied" : "Copy"}</span>
        </button>
      </div>
      <pre>{children}</pre>
    </div>
  );
}

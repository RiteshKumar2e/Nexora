"use client";

import { memo, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeHighlight from "rehype-highlight";
import Mermaid from "./Mermaid";
import CodeBlock from "./CodeBlock";

/** Recursively pull plain text out of React children (for mermaid source). */
function textOf(node: ReactNode): string {
  if (node == null || node === false) return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  // React element with children
  const el = node as { props?: { children?: ReactNode } };
  if (el.props?.children) return textOf(el.props.children);
  return "";
}

/**
 * Normalize LaTeX delimiters so remark-math (which only understands `$…$` and
 * `$$…$$`) renders what models actually emit: `\(…\)` and `\[…\]`. Code spans
 * and fenced code blocks are left untouched so real code isn't mangled.
 */
function normalizeMath(input: string): string {
  const segments = input.split(/(```[\s\S]*?```|`[^`]*`)/g);
  return segments
    .map((seg, i) => {
      if (i % 2 === 1) return seg; // captured code segment — leave as-is
      return seg
        .replace(/\\\[|\\\]/g, () => "$$") // \[ \] -> $$  (display math)
        .replace(/\\\(|\\\)/g, () => "$"); // \( \) -> $   (inline math)
    })
    .join("");
}

/** Inline code vs block code. In react-markdown v9 there is no `inline` prop;
 *  block code carries a `language-*` class, inline code does not. Block code is
 *  rendered by the `pre` override below, so here we only special-case inline. */
function Code({ className, children }: any) {
  if (!className) {
    return <code className="inline-code">{children}</code>;
  }
  return <code className={className}>{children}</code>;
}

/** The `<pre>` wrapper: route mermaid to the diagram renderer, everything else
 *  to CodeBlock (language label + copy button around the highlighted code). */
function Pre({ children }: any) {
  const codeEl = Array.isArray(children) ? children[0] : children;
  const className: string = codeEl?.props?.className || "";
  const lang = /language-(\w+)/.exec(className)?.[1];
  const raw = textOf(codeEl?.props?.children);
  if (lang === "mermaid") {
    return <Mermaid chart={raw.trim()} />;
  }
  return (
    <CodeBlock lang={lang} code={raw}>
      {children}
    </CodeBlock>
  );
}

function MarkdownBase({ content }: { content: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex, [rehypeHighlight, { detect: true, ignoreMissing: true }]]}
        components={{ code: Code, pre: Pre }}
      >
        {normalizeMath(content)}
      </ReactMarkdown>
    </div>
  );
}

// Re-render only when text changes — important during token streaming.
export default memo(MarkdownBase, (a, b) => a.content === b.content);

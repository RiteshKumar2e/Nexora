"use client";

import { useRef, type KeyboardEvent } from "react";

export default function Composer({
  value,
  onChange,
  onSend,
  onStop,
  busy,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onStop: () => void;
  busy: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!busy && value.trim()) onSend();
    }
  }

  function autoresize() {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 220) + "px";
  }

  return (
    <div className="composer">
      <div className="composer-inner glass">
        <textarea
          ref={ref}
          className="composer-input"
          placeholder="Message Nexora…  (Enter to send, Shift+Enter for newline)"
          rows={1}
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            autoresize();
          }}
          onKeyDown={handleKey}
        />
        {busy ? (
          <button className="send-btn stop" onClick={onStop} title="Stop">
            ■
          </button>
        ) : (
          <button
            className="send-btn"
            onClick={onSend}
            disabled={!value.trim()}
            title="Send"
          >
            ↑
          </button>
        )}
      </div>
      <p className="composer-hint">
        Nexora can make mistakes. Consider checking important information.
      </p>
    </div>
  );
}

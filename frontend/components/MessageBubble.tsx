"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import type { Message } from "@/lib/types";
import Markdown from "./Markdown";

export default function MessageBubble({
  message,
  streaming,
}: {
  message: Message;
  streaming?: boolean;
}) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable — ignore */
    }
  }

  return (
    <div className={`msg-row ${isUser ? "msg-user" : "msg-assistant"}`}>
      <div className="msg-avatar" aria-hidden>
        {isUser ? "You" : "N"}
      </div>
      <div className="msg-col">
        <div className="msg-body">
          {isUser ? (
            <p className="msg-plain">{message.content}</p>
          ) : (
            <Markdown content={message.content} />
          )}
          {streaming && <span className="cursor-blink" />}
        </div>

        {!isUser && !streaming && message.content && (
          <div className="msg-actions">
            <button className="msg-action" onClick={copy} title="Copy">
              {copied ? <Check size={15} /> : <Copy size={15} />}
              <span>{copied ? "Copied" : "Copy"}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

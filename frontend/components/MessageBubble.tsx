"use client";

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
  return (
    <div className={`msg-row ${isUser ? "msg-user" : "msg-assistant"}`}>
      <div className="msg-avatar" aria-hidden>
        {isUser ? "You" : "N"}
      </div>
      <div className="msg-body">
        {isUser ? (
          <p className="msg-plain">{message.content}</p>
        ) : (
          <Markdown content={message.content || (streaming ? "" : "")} />
        )}
        {streaming && <span className="cursor-blink" />}
      </div>
    </div>
  );
}

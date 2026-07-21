"use client";

import { useState } from "react";
import { Check, Copy, ThumbsUp, ThumbsDown, RefreshCw, Edit2, Clock } from "lucide-react";
import type { Message } from "@/lib/types";
import Markdown from "./Markdown";

export default function MessageBubble({
  message,
  index,
  streaming,
  onRegenerate,
  onEdit,
  onFeedback,
}: {
  message: Message;
  index: number;
  streaming?: boolean;
  onRegenerate?: () => void;
  onEdit?: (newContent: string) => void;
  onFeedback?: (rating: "up" | "down", correction?: string) => void;
}) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<"up" | "down" | null>(null);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(message.content);
  const [showCorrection, setShowCorrection] = useState(false);
  const [correction, setCorrection] = useState("");

  function rateUp() {
    const next = feedback === "up" ? null : "up";
    setFeedback(next);
    setShowCorrection(false);
    if (next === "up") onFeedback?.("up");
  }

  function rateDown() {
    setFeedback("down");
    setShowCorrection(true);
    onFeedback?.("down");
  }

  function submitCorrection() {
    if (correction.trim()) {
      onFeedback?.("down", correction.trim());
      setShowCorrection(false);
      setCorrection("");
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }

  function handleSaveEdit() {
    if (editText.trim() && editText.trim() !== message.content && onEdit) {
      onEdit(editText.trim());
      setEditing(false);
    }
  }

  const timestampStr = message.created_at
    ? new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <div className={`msg-row ${isUser ? "msg-user" : "msg-assistant"}`}>
      <div className="msg-avatar" aria-hidden>
        {isUser ? "You" : "N"}
      </div>
      <div className="msg-col">
        <div className="msg-header">
          <span className="msg-role">{isUser ? "You" : "Nexora AI"}</span>
          <span className="msg-time">{timestampStr}</span>
          {!isUser && (
            <span className="msg-model-badge">
              {message.model || "nexora-native"}
            </span>
          )}
        </div>

        <div className="msg-body">
          {isUser ? (
            editing ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", width: "100%" }}>
                <textarea
                  className="form-input"
                  style={{ minHeight: "80px", width: "100%", resize: "vertical" }}
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                />
                <div style={{ display: "flex", gap: "8px" }}>
                  <button className="btn btn-primary" style={{ padding: "4px 12px" }} onClick={handleSaveEdit}>
                    Save & Submit
                  </button>
                  <button className="btn btn-ghost" style={{ padding: "4px 12px" }} onClick={() => setEditing(false)}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <p className="msg-plain">{message.content}</p>
            )
          ) : (
            <Markdown content={message.content} />
          )}
          {streaming && <span className="cursor-blink" />}
        </div>

        {!streaming && message.content && (
          <div className="msg-actions">
            <button className="msg-action" onClick={copy} title="Copy response">
              {copied ? <Check size={14} /> : <Copy size={14} />}
              <span>{copied ? "Copied" : "Copy"}</span>
            </button>

            {isUser && onEdit && !editing && (
              <button className="msg-action" onClick={() => setEditing(true)} title="Edit prompt">
                <Edit2 size={14} />
                <span>Edit</span>
              </button>
            )}

            {!isUser && (
              <>
                <button
                  className="msg-action"
                  onClick={rateUp}
                  style={feedback === "up" ? { color: "var(--success)" } : {}}
                  title="Helpful — save as a good example"
                >
                  <ThumbsUp size={14} />
                </button>
                <button
                  className="msg-action"
                  onClick={rateDown}
                  style={feedback === "down" ? { color: "var(--danger)" } : {}}
                  title="Unhelpful — optionally suggest a better answer"
                >
                  <ThumbsDown size={14} />
                </button>
                {onRegenerate && (
                  <button className="msg-action" onClick={onRegenerate} title="Regenerate response">
                    <RefreshCw size={14} />
                    <span>Regenerate</span>
                  </button>
                )}
              </>
            )}
          </div>
        )}

        {!isUser && showCorrection && (
          <div className="correction-box">
            <textarea
              className="correction-input"
              placeholder="Optional: write a better answer. It's saved as the preferred target for training."
              value={correction}
              onChange={(e) => setCorrection(e.target.value)}
            />
            <div className="correction-actions">
              <button className="msg-action" onClick={submitCorrection} disabled={!correction.trim()}>
                Submit correction
              </button>
              <button className="msg-action" onClick={() => setShowCorrection(false)}>
                Dismiss
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

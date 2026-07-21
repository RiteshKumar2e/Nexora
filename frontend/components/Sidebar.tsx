"use client";

import type { Conversation } from "@/lib/types";

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
}: {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}) {
  return (
    <aside className="sidebar glass">
      <div className="sidebar-header">
        <div className="brand">
          <span className="brand-mark">◈</span>
          <span className="brand-name">Nexora</span>
        </div>
        <button className="new-chat" onClick={onNew}>
          + New chat
        </button>
      </div>

      <nav className="convo-list">
        {conversations.length === 0 && (
          <p className="convo-empty">No conversations yet.</p>
        )}
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`convo-item ${c.id === activeId ? "active" : ""}`}
            onClick={() => onSelect(c.id)}
          >
            <span className="convo-title">
              {c.pinned ? "📌 " : ""}
              {c.title}
            </span>
            <button
              className="convo-del"
              title="Delete"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(c.id);
              }}
            >
              ×
            </button>
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        <span className="dot" /> Local model · self-hosted
      </div>
    </aside>
  );
}

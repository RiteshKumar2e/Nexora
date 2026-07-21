"use client";

import { useMemo, useState } from "react";
import {
  MessageSquare,
  PanelLeftClose,
  Pin,
  PinOff,
  Search,
  Sparkles,
  SquarePen,
  Trash2,
} from "lucide-react";
import type { Conversation } from "@/lib/types";

function ConvoRow({
  c,
  active,
  onSelect,
  onDelete,
  onPin,
}: {
  c: Conversation;
  active: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onPin: (id: string, pinned: boolean) => void;
}) {
  return (
    <div
      className={`convo-item ${active ? "active" : ""}`}
      onClick={() => onSelect(c.id)}
      title={c.title}
    >
      <MessageSquare size={15} className="convo-icon" />
      <span className="convo-title">{c.title}</span>
      <div className="convo-actions">
        <button
          className="convo-act"
          title={c.pinned ? "Unpin" : "Pin"}
          onClick={(e) => {
            e.stopPropagation();
            onPin(c.id, !c.pinned);
          }}
        >
          {c.pinned ? <PinOff size={14} /> : <Pin size={14} />}
        </button>
        <button
          className="convo-act danger"
          title="Delete"
          onClick={(e) => {
            e.stopPropagation();
            onDelete(c.id);
          }}
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
}

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onPin,
  onCollapse,
}: {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onPin: (id: string, pinned: boolean) => void;
  onCollapse: () => void;
}) {
  const [searching, setSearching] = useState(false);
  const [query, setQuery] = useState("");

  const { pinned, recents } = useMemo(() => {
    const q = query.trim().toLowerCase();
    const match = (c: Conversation) => !q || c.title.toLowerCase().includes(q);
    const filtered = conversations.filter(match);
    return {
      pinned: filtered.filter((c) => c.pinned),
      recents: filtered.filter((c) => !c.pinned),
    };
  }, [conversations, query]);

  const nothing = pinned.length === 0 && recents.length === 0;

  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <div className="brand">
          <span className="brand-mark">
            <Sparkles size={18} />
          </span>
          <span className="brand-name">Nexora</span>
        </div>
        <button className="icon-btn sm" title="Collapse sidebar" onClick={onCollapse}>
          <PanelLeftClose size={18} />
        </button>
      </div>

      <div className="sidebar-nav">
        <button className="nav-row" onClick={onNew}>
          <SquarePen size={17} />
          <span>New chat</span>
        </button>
        <button
          className={`nav-row ${searching ? "active" : ""}`}
          onClick={() => setSearching((s) => !s)}
        >
          <Search size={17} />
          <span>Search chats</span>
        </button>
        {searching && (
          <input
            className="nav-search"
            autoFocus
            placeholder="Search conversations…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        )}
      </div>

      <nav className="convo-list">
        {nothing && (
          <p className="convo-empty">
            {query ? "No matches." : "No conversations yet."}
          </p>
        )}

        {pinned.length > 0 && (
          <>
            <div className="convo-group">Pinned</div>
            {pinned.map((c) => (
              <ConvoRow
                key={c.id}
                c={c}
                active={c.id === activeId}
                onSelect={onSelect}
                onDelete={onDelete}
                onPin={onPin}
              />
            ))}
          </>
        )}

        {recents.length > 0 && (
          <>
            <div className="convo-group">Recents</div>
            {recents.map((c) => (
              <ConvoRow
                key={c.id}
                c={c}
                active={c.id === activeId}
                onSelect={onSelect}
                onDelete={onDelete}
                onPin={onPin}
              />
            ))}
          </>
        )}
      </nav>

      <div className="sidebar-footer">
        <span className="dot" /> Connected
      </div>
    </aside>
  );
}

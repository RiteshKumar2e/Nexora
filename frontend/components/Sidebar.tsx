"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import {
  Bot,
  Clock,
  Folder,
  Library,
  MessageSquare,
  MoreHorizontal,
  PanelLeftClose,
  Pin,
  PinOff,
  Puzzle,
  Search,
  Sparkles,
  SquarePen,
  Store,
  Trash2,
  Edit2,
  Check,
  X,
  GraduationCap
} from "lucide-react";
import type { Conversation } from "@/lib/types";

// Left sidebar navigation
const SECONDARY = [
  { label: "Projects", Icon: Folder },
  { label: "Library", Icon: Library },
  { label: "Plugins", Icon: Puzzle },
  { label: "Training", Icon: GraduationCap },
];

function ConvoRow({
  c,
  active,
  onSelect,
  onDelete,
  onPin,
  onRename,
}: {
  c: Conversation;
  active: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onPin: (id: string, pinned: boolean) => void;
  onRename: (id: string, title: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(c.title);
  const [confirmDelete, setConfirmDelete] = useState(false);

  function handleSave(e: React.MouseEvent) {
    e.stopPropagation();
    if (title.trim() && title !== c.title) {
      onRename(c.id, title.trim());
    }
    setEditing(false);
  }

  function handleCancel(e: React.MouseEvent) {
    e.stopPropagation();
    setTitle(c.title);
    setEditing(false);
  }

  function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    if (confirmDelete) {
      onDelete(c.id);
    } else {
      setConfirmDelete(true);
      setTimeout(() => setConfirmDelete(false), 3000); // Reset after 3 seconds
    }
  }

  return (
    <div
      className={`convo-item ${active ? "active" : ""}`}
      onClick={() => !editing && onSelect(c.id)}
      title={c.title}
    >
      <MessageSquare size={15} className="convo-icon" />
      {editing ? (
        <div className="flex items-center gap-1 w-full" onClick={(e) => e.stopPropagation()}>
          <input
            className="nav-search"
            style={{ margin: 0, padding: "2px 4px", fontSize: "13px", width: "100%" }}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                if (title.trim() && title !== c.title) onRename(c.id, title.trim());
                setEditing(false);
              } else if (e.key === "Escape") {
                setTitle(c.title);
                setEditing(false);
              }
            }}
          />
          <button className="convo-act" onClick={handleSave}><Check size={13} /></button>
          <button className="convo-act" onClick={handleCancel}><X size={13} /></button>
        </div>
      ) : (
        <>
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
              {c.pinned ? <PinOff size={13} /> : <Pin size={13} />}
            </button>
            <button
              className="convo-act"
              title="Rename"
              onClick={(e) => {
                e.stopPropagation();
                setEditing(true);
              }}
            >
              <Edit2 size={13} />
            </button>
            <button
              className={`convo-act danger ${confirmDelete ? "active" : ""}`}
              title={confirmDelete ? "Click again to confirm" : "Delete"}
              onClick={handleDelete}
              style={confirmDelete ? { color: "var(--danger)", backgroundColor: "var(--danger-soft)" } : {}}
            >
              <Trash2 size={13} />
            </button>
          </div>
        </>
      )}
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
  onRename,
  onCollapse,
  user,
  onAuthClick,
  onSignOut,
}: {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onPin: (id: string, pinned: boolean) => void;
  onRename: (id: string, title: string) => void;
  onCollapse: () => void;
  user: any;
  onAuthClick: () => void;
  onSignOut: () => void;
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
  const navigateTo = (label: string) => toast(`${label} — loading workspace`);

  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <div className="brand">
          <span className="brand-mark">
            <Sparkles size={18} />
          </span>
          <span className="brand-name">Nexora AI</span>
        </div>
        <div className="sidebar-top-actions">
          <button
            className={`icon-btn sm ${searching ? "on" : ""}`}
            title="Search chats"
            onClick={() => setSearching((s) => !s)}
          >
            <Search size={17} />
          </button>
          <button className="icon-btn sm" title="Collapse sidebar" onClick={onCollapse}>
            <PanelLeftClose size={18} />
          </button>
        </div>
      </div>

      <div className="sidebar-nav">
        <button className="nav-row primary" onClick={onNew}>
          <SquarePen size={17} />
          <span>New chat</span>
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
        {SECONDARY.map(({ label, Icon }) => (
          <button key={label} className="nav-row" onClick={() => navigateTo(label)}>
            <Icon size={17} />
            <span>{label}</span>
          </button>
        ))}
      </div>

      <div className="nav-divider" />

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
                onRename={onRename}
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
                onRename={onRename}
              />
            ))}
          </>
        )}
      </nav>

      {user ? (
        <div className="sidebar-profile" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", overflow: "hidden" }}>
            <span className="profile-avatar">{user.username[0].toUpperCase()}</span>
            <span className="profile-meta" style={{ overflow: "hidden" }}>
              <span className="profile-name" style={{ textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap" }}>
                {user.display_name || user.username}
              </span>
              <span className="profile-plan" onClick={onSignOut} style={{ cursor: "pointer", textDecoration: "underline", color: "var(--danger)" }}>
                Sign Out
              </span>
            </span>
          </div>
        </div>
      ) : (
        <button className="sidebar-profile" onClick={onAuthClick}>
          <span className="profile-avatar">?</span>
          <span className="profile-meta">
            <span className="profile-name">Sign In / Register</span>
            <span className="profile-plan">Sync conversations</span>
          </span>
          <Store size={17} className="profile-store" />
        </button>
      )}
    </aside>
  );
}

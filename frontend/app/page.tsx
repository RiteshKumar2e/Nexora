"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import MessageBubble from "@/components/MessageBubble";
import Composer from "@/components/Composer";
import ContextPanel from "@/components/ContextPanel";
import CommandPalette from "@/components/CommandPalette";
import AuthModal from "@/components/AuthModal";
import { api, streamChat } from "@/lib/api";
import type { Conversation, Message } from "@/lib/types";
import { Sparkles } from "lucide-react";

const SUGGESTIONS = [
  { icon: "💡", label: "Explain a concept", text: "Explain how neural networks learn through backpropagation" },
  { icon: "🐛", label: "Debug code", text: "Help me debug this Python function that isn't returning the right result" },
  { icon: "📄", label: "Analyze content", text: "Summarize the key principles of object-oriented programming" },
  { icon: "🔬", label: "Research topic", text: "Compare supervised and unsupervised learning with examples" },
];

export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [contextOpen, setContextOpen] = useState(false);
  const [showPalette, setShowPalette] = useState(false);
  
  // Auth state
  const [user, setUser] = useState<any | null>(null);
  const [showAuthModal, setShowAuthModal] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await api.listConversations());
    } catch {
      /* backend may still be starting */
    }
  }, []);

  // Check auth status on load
  useEffect(() => {
    async function checkAuth() {
      const token = localStorage.getItem("nexora_token");
      if (token) {
        try {
          const res = await fetch("http://localhost:8000/api/auth/me", {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (res.ok) {
            const data = await res.json();
            setUser(data);
          } else {
            localStorage.removeItem("nexora_token");
            setUser(null);
          }
        } catch {
          setUser(null);
        }
      }
    }
    checkAuth().then(() => {
      refreshConversations();
    });
  }, [refreshConversations]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  // Global keyboard shortcuts
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setShowPalette((p) => !p);
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "n") {
        e.preventDefault();
        newChat();
      }
      if (e.key === "Escape") {
        setShowPalette(false);
        if (busy) stop();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [busy]);

  async function selectConversation(id: string) {
    if (busy) return;
    setActiveId(id);
    const detail = await api.getConversation(id);
    setMessages(detail.messages);
  }

  function newChat() {
    if (busy) return;
    setActiveId(null);
    setMessages([]);
  }

  async function deleteConversation(id: string) {
    await api.deleteConversation(id);
    if (id === activeId) newChat();
    refreshConversations();
  }

  async function pinConversation(id: string, pinned: boolean) {
    setConversations((cs) =>
      cs.map((c) => (c.id === id ? { ...c, pinned } : c))
    );
    try {
      await api.setPinned(id, pinned);
    } catch {
      toast.error("Couldn't update pin");
    }
    refreshConversations();
  }

  async function renameConversation(id: string, title: string) {
    try {
      await api.renameConversation(id, title);
      refreshConversations();
    } catch {
      toast.error("Couldn't rename conversation");
    }
  }

  function send(text?: string) {
    const msg = (text ?? input).trim();
    if (!msg || busy) return;

    setInput("");
    setBusy(true);

    setMessages((m) => [
      ...m,
      { role: "user", content: msg },
      { role: "assistant", content: "" },
    ]);

    const appendToAssistant = (delta: string) =>
      setMessages((m) => {
        const copy = [...m];
        const last = copy[copy.length - 1];
        copy[copy.length - 1] = { ...last, content: last.content + delta };
        return copy;
      });

    abortRef.current = streamChat(
      { message: msg, conversation_id: activeId ?? undefined },
      {
        onMeta: (e) => {
          if (e.is_new) {
            setActiveId(e.conversation_id);
            refreshConversations();
          }
        },
        onToken: appendToAssistant,
        onDone: () => {
          setBusy(false);
          abortRef.current = null;
          refreshConversations();
        },
        onError: (msg) => {
          toast.error(msg);
          setMessages((m) => {
            const copy = [...m];
            const last = copy[copy.length - 1];
            if (last?.role === "assistant" && !last.content) copy.pop();
            return copy;
          });
          setBusy(false);
          abortRef.current = null;
        },
      }
    );
  }

  function stop() {
    abortRef.current?.abort();
    abortRef.current = null;
    setBusy(false);
  }

  function regenerate() {
    if (busy || messages.length < 2) return;
    const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUserMsg) return;

    setMessages((m) => {
      const copy = [...m];
      if (copy[copy.length - 1]?.role === "assistant") copy.pop();
      return copy;
    });

    setTimeout(() => send(lastUserMsg.content), 50);
  }

  function editAndResend(index: number, newContent: string) {
    if (busy) return;
    setMessages((m) => m.slice(0, index));
    setTimeout(() => send(newContent), 50);
  }

  function handleAuthSuccess(token: string, user: any) {
    localStorage.setItem("nexora_token", token);
    setUser(user);
    refreshConversations();
  }

  function handleSignOut() {
    localStorage.removeItem("nexora_token");
    setUser(null);
    newChat();
    setConversations([]);
    toast.info("Logged out successfully");
  }

  const empty = messages.length === 0;
  const activeTitle = conversations.find((c) => c.id === activeId)?.title;

  const shellClass = [
    "app-shell",
    !sidebarOpen && "sidebar-collapsed",
    contextOpen && "context-open",
  ].filter(Boolean).join(" ");

  return (
    <>
      <div className={shellClass}>
        {sidebarOpen && (
          <Sidebar
            conversations={conversations}
            activeId={activeId}
            onSelect={selectConversation}
            onNew={newChat}
            onDelete={deleteConversation}
            onPin={pinConversation}
            onRename={renameConversation}
            onCollapse={() => setSidebarOpen(false)}
            user={user}
            onAuthClick={() => setShowAuthModal(true)}
            onSignOut={handleSignOut}
          />
        )}

        <main className="chat-main">
          <Header
            title={activeTitle}
            sidebarOpen={sidebarOpen}
            onOpenSidebar={() => setSidebarOpen(true)}
            onNewChat={newChat}
            onToggleContext={() => setContextOpen((c) => !c)}
            contextOpen={contextOpen}
          />
          <div className="chat-scroll" ref={scrollRef}>
            {empty ? (
              <div className="welcome">
                <div className="welcome-logo">
                  <Sparkles size={28} />
                </div>
                <h1>How can I help you today?</h1>
                <p>
                  Ask anything — explanations, code, math, diagrams, and more.
                  Powered by a model trained from scratch.
                </p>
                <div className="suggestions">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s.text}
                      className="suggestion"
                      onClick={() => send(s.text)}
                    >
                      <div className="suggestion-icon">
                        <span>{s.icon}</span> {s.label}
                      </div>
                      {s.text}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="messages">
                {messages.map((m, i) => (
                  <MessageBubble
                    key={m.id ?? i}
                    message={m}
                    index={i}
                    streaming={
                      busy && i === messages.length - 1 && m.role === "assistant"
                    }
                    onRegenerate={
                      !busy && m.role === "assistant" && i === messages.length - 1
                        ? regenerate
                        : undefined
                    }
                    onEdit={
                      m.role === "user" ? (text) => editAndResend(i, text) : undefined
                    }
                  />
                ))}
              </div>
            )}
          </div>

          <Composer
            value={input}
            onChange={setInput}
            onSend={() => send()}
            onStop={stop}
            busy={busy}
          />
        </main>

        {contextOpen && <ContextPanel onClose={() => setContextOpen(false)} />}
      </div>

      {showPalette && (
        <CommandPalette
          onClose={() => setShowPalette(false)}
          onNewChat={newChat}
          onToggleTheme={() => {}}
        />
      )}

      {showAuthModal && (
        <AuthModal
          onClose={() => setShowAuthModal(false)}
          onSuccess={handleAuthSuccess}
        />
      )}
    </>
  );
}

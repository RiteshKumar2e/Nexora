"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Sidebar from "@/components/Sidebar";
import MessageBubble from "@/components/MessageBubble";
import Composer from "@/components/Composer";
import { api, streamChat } from "@/lib/api";
import type { Conversation, Message } from "@/lib/types";

export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await api.listConversations());
    } catch {
      /* backend may still be starting */
    }
  }, []);

  useEffect(() => {
    refreshConversations();
  }, [refreshConversations]);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages]);

  async function selectConversation(id: string) {
    if (busy) return;
    setActiveId(id);
    setError(null);
    const detail = await api.getConversation(id);
    setMessages(detail.messages);
  }

  function newChat() {
    if (busy) return;
    setActiveId(null);
    setMessages([]);
    setError(null);
  }

  async function deleteConversation(id: string) {
    await api.deleteConversation(id);
    if (id === activeId) newChat();
    refreshConversations();
  }

  function send() {
    const text = input.trim();
    if (!text || busy) return;

    setError(null);
    setInput("");
    setBusy(true);

    setMessages((m) => [
      ...m,
      { role: "user", content: text },
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
      { message: text, conversation_id: activeId ?? undefined },
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
          setError(msg);
          setBusy(false);
          abortRef.current = null;
        },
      },
    );
  }

  function stop() {
    abortRef.current?.abort();
    abortRef.current = null;
    setBusy(false);
  }

  const empty = messages.length === 0;

  return (
    <div className="app-shell">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={selectConversation}
        onNew={newChat}
        onDelete={deleteConversation}
      />

      <main className="chat-main">
        <div className="chat-scroll" ref={scrollRef}>
          {empty ? (
            <div className="welcome">
              <div className="welcome-glow" />
              <h1>How can I help you today?</h1>
              <p>
                Ask anything — explanations, code, math, diagrams, and more.
              </p>
              <div className="suggestions">
                {[
                  "Explain async/await with a code example",
                  "Draw a Mermaid flowchart for a login flow",
                  "Prove the sum 1+2+…+n = n(n+1)/2",
                ].map((s) => (
                  <button
                    key={s}
                    className="suggestion glass"
                    onClick={() => setInput(s)}
                  >
                    {s}
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
                  streaming={
                    busy && i === messages.length - 1 && m.role === "assistant"
                  }
                />
              ))}
            </div>
          )}

          {error && <div className="error-banner">⚠ {error}</div>}
        </div>

        <Composer
          value={input}
          onChange={setInput}
          onSend={send}
          onStop={stop}
          busy={busy}
        />
      </main>
    </div>
  );
}

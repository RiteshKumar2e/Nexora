"use client";

import { useEffect, useState } from "react";
import { PanelLeft, Sparkles, SquarePen, PanelRight, ChevronDown, Check, Wifi, AlertTriangle } from "lucide-react";
import ThemeToggle from "./ThemeToggle";
import { api } from "@/lib/api";

export default function Header({
  title,
  sidebarOpen,
  onOpenSidebar,
  onNewChat,
  onToggleContext,
  contextOpen,
}: {
  title?: string;
  sidebarOpen: boolean;
  onOpenSidebar: () => void;
  onNewChat: () => void;
  onToggleContext: () => void;
  contextOpen: boolean;
}) {
  const [model, setModel] = useState("nexora-native");
  const [provider, setProvider] = useState("Native");
  const [status, setStatus] = useState<"ok" | "degraded" | "offline">("ok");
  const [modelsList, setModelsList] = useState<string[]>(["nexora-native"]);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  useEffect(() => {
    async function checkStatus() {
      try {
        const health = await fetch("http://localhost:8000/api/health/ready").then((r) => r.json());
        if (health.status === "ok") {
          setStatus("ok");
        } else {
          setStatus("degraded");
        }
        if (health.llm) {
          setProvider(health.llm.backend === "nano" ? "Native" : "External");
          setModel(health.llm.model || "nexora-native");
        }
      } catch {
        setStatus("offline");
      }
    }
    checkStatus();
    const interval = setInterval(checkStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  const selectModel = (m: string) => {
    setModel(m);
    setDropdownOpen(false);
    // Future work: tell the API which model to use.
  };

  return (
    <header className="topbar">
      <div className="topbar-left">
        {!sidebarOpen && (
          <>
            <button className="icon-btn" title="Open sidebar" onClick={onOpenSidebar}>
              <PanelLeft size={18} />
            </button>
            <button className="icon-btn" title="New chat" onClick={onNewChat}>
              <SquarePen size={18} />
            </button>
          </>
        )}
        <div className="topbar-title">
          <Sparkles size={16} className="topbar-spark" />
          <span>{title || "New chat"}</span>
        </div>

        {/* Model Selector Dropdown */}
        <div style={{ position: "relative", marginLeft: "12px" }}>
          <button
            className="model-badge native"
            onClick={() => setDropdownOpen(!dropdownOpen)}
            style={{ cursor: "pointer", border: "none" }}
          >
            <span>{model}</span>
            <span style={{ fontSize: "10px", padding: "1px 4px", borderRadius: "4px", background: "rgba(0,0,0,0.1)" }}>
              {provider}
            </span>
            <ChevronDown size={12} />
          </button>

          {dropdownOpen && (
            <div
              className="glass"
              style={{
                position: "absolute",
                top: "100%",
                left: 0,
                marginTop: "4px",
                borderRadius: "var(--radius-md)",
                padding: "4px",
                width: "200px",
                boxShadow: "var(--shadow-md)",
                zIndex: 100,
                display: "flex",
                flexDirection: "column",
                gap: "2px",
                backgroundColor: "var(--surface)",
              }}
            >
              {modelsList.map((m) => (
                <button
                  key={m}
                  onClick={() => selectModel(m)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "8px 12px",
                    border: "none",
                    borderRadius: "var(--radius-sm)",
                    background: m === model ? "var(--primary-soft)" : "transparent",
                    color: m === model ? "var(--primary)" : "var(--text-primary)",
                    cursor: "pointer",
                    textAlign: "left",
                    fontSize: "13px",
                    width: "100%",
                  }}
                >
                  <span>{m}</span>
                  {m === model && <Check size={14} />}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="topbar-actions">
        {/* Connection status indicator */}
        <div
          style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "var(--text-muted)", marginRight: "8px" }}
          title={`Status: ${status}`}
        >
          {status === "ok" && <Wifi size={14} className="text-success" style={{ color: "var(--success)" }} />}
          {status === "degraded" && <AlertTriangle size={14} style={{ color: "var(--warning)" }} />}
          {status === "offline" && <AlertTriangle size={14} style={{ color: "var(--danger)" }} />}
          <span>{status === "ok" ? "Online" : status === "degraded" ? "Degraded" : "Offline"}</span>
        </div>

        <ThemeToggle />
        
        {/* Context panel toggle */}
        <button
          className={`icon-btn ${contextOpen ? "on" : ""}`}
          title="Toggle Context Panel (Artifacts / Files / RAG)"
          onClick={onToggleContext}
          style={contextOpen ? { color: "var(--primary)", backgroundColor: "var(--primary-soft)" } : {}}
        >
          <PanelRight size={18} />
        </button>
      </div>
    </header>
  );
}

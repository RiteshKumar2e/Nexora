"use client";

import { useRef, type KeyboardEvent, useState } from "react";
import { ArrowUp, Square, Paperclip, AlertCircle, FileText, Check } from "lucide-react";
import { toast } from "sonner";

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
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [attachedFiles, setAttachedFiles] = useState<string[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!busy && (value.trim() || attachedFiles.length > 0)) {
        onSend();
        setAttachedFiles([]);
      }
    }
  }

  function autoresize() {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }

  function handleAttachClick() {
    fileInputRef.current?.click();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      const names = files.map((f) => f.name);
      setAttachedFiles((prev) => [...prev, ...names]);
      toast.success(`Attached: ${names.join(", ")}`);
    }
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    setIsDragOver(true);
  }

  function handleDragLeave() {
    setIsDragOver(false);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setIsDragOver(false);
    const files = Array.from(e.dataTransfer.files || []);
    if (files.length > 0) {
      const names = files.map((f) => f.name);
      setAttachedFiles((prev) => [...prev, ...names]);
      toast.success(`Attached dropped file(s): ${names.join(", ")}`);
    }
  }

  return (
    <div className="composer" onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}>
      <div className={`composer-inner glass ${isDragOver ? "drag-over" : ""}`} style={isDragOver ? { borderColor: "var(--primary)", backgroundColor: "var(--primary-soft)" } : {}}>
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          multiple
          style={{ display: "none" }}
        />
        
        <button
          className="icon-btn sm"
          title="Upload document/file"
          onClick={handleAttachClick}
          style={{ alignSelf: "flex-end", marginBottom: "4px" }}
        >
          <Paperclip size={17} />
        </button>

        <div style={{ display: "flex", flexDirection: "column", flex: 1 }}>
          {attachedFiles.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "8px", marginTop: "4px" }}>
              {attachedFiles.map((name, idx) => (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                    padding: "2px 8px",
                    borderRadius: "var(--radius-sm)",
                    background: "var(--surface-secondary)",
                    fontSize: "12px",
                    color: "var(--text-secondary)",
                    border: "1px solid var(--border)",
                  }}
                >
                  <FileText size={12} />
                  <span>{name}</span>
                  <button
                    onClick={() => setAttachedFiles((prev) => prev.filter((_, i) => i !== idx))}
                    style={{ border: "none", background: "none", cursor: "pointer", color: "var(--text-muted)", marginLeft: "4px" }}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}

          <textarea
            ref={ref}
            className="composer-input"
            placeholder="Ask Nexora anything... (Shift+Enter for newline)"
            rows={1}
            value={value}
            onChange={(e) => {
              onChange(e.target.value);
              autoresize();
            }}
            onKeyDown={handleKey}
          />
        </div>

        <div className="composer-tools">
          <span style={{ fontSize: "11px", color: "var(--text-muted)", marginRight: "4px", fontFamily: "var(--font-mono)" }}>
            {value.length} ch
          </span>

          {busy ? (
            <button className="send-btn stop" onClick={onStop} title="Stop generation">
              <Square size={14} fill="currentColor" />
            </button>
          ) : (
            <button
              className="send-btn"
              onClick={() => {
                onSend();
                setAttachedFiles([]);
              }}
              disabled={!value.trim() && attachedFiles.length === 0}
              title="Send message"
            >
              <ArrowUp size={18} />
            </button>
          )}
        </div>
      </div>
      <p className="composer-hint">
        Nexora may produce inaccurate information. Run Native Mode locally without privacy leak.
      </p>
    </div>
  );
}

"use client";

import { useRef, type KeyboardEvent, useState, useEffect } from "react";
import {
  ArrowUp, Square, Plus, FileText, Mic, Paperclip, Globe, Image as ImageIcon,
} from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

const TEXT_EXT = new Set([
  "txt", "md", "markdown", "csv", "tsv", "json", "yaml", "yml", "xml", "html",
  "htm", "css", "js", "jsx", "ts", "tsx", "py", "java", "c", "cpp", "cs", "go",
  "rs", "rb", "php", "sh", "sql", "log", "ini", "toml", "env", "text",
]);
const MAX_CHARS = 8000;

function isTextFile(f: File): boolean {
  const ext = f.name.split(".").pop()?.toLowerCase() || "";
  return TEXT_EXT.has(ext) || f.type.startsWith("text/");
}

export default function Composer({
  value,
  onChange,
  onSend,
  onStop,
  busy,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: (attachmentText?: string) => void;
  onStop: () => void;
  busy: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [listening, setListening] = useState(false);
  const [preparing, setPreparing] = useState(false);

  useEffect(() => () => recognitionRef.current?.stop?.(), []);

  function addFiles(list: FileList | null) {
    const picked = Array.from(list || []);
    if (picked.length) {
      setFiles((prev) => [...prev, ...picked]);
      toast.success(`Attached: ${picked.map((f) => f.name).join(", ")}`);
    }
  }

  async function buildAttachmentText(): Promise<string> {
    if (files.length === 0) return "";
    const parts: string[] = [];
    for (const f of files) {
      if (isTextFile(f)) {
        // Plain text: read directly in the browser (fast, no upload).
        try {
          parts.push(`\n\n[Attached file: ${f.name}]\n${(await f.text()).slice(0, MAX_CHARS)}`);
        } catch {
          parts.push(`\n\n[Attached file: ${f.name} — could not read]`);
        }
      } else {
        // PDF/DOCX/XLSX/etc.: upload so the backend extracts the text.
        try {
          const res = await api.uploadFile(f);
          const text = (res.parsed_text || "").slice(0, MAX_CHARS);
          parts.push(
            text.trim()
              ? `\n\n[Attached file: ${f.name}]\n${text}`
              : `\n\n[Attached file: ${f.name} — no extractable text (maybe a scanned image).]`,
          );
        } catch {
          parts.push(`\n\n[Attached file: ${f.name} — upload/parse failed]`);
        }
      }
    }
    return parts.join("");
  }

  async function doSend() {
    if (busy || preparing || (!value.trim() && files.length === 0)) return;
    const hasBinary = files.some((f) => !isTextFile(f));
    if (hasBinary) setPreparing(true);
    const attachment = await buildAttachmentText();
    setPreparing(false);
    onSend(attachment || undefined);
    setFiles([]);
    if (ref.current) ref.current.style.height = "auto";
  }

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      doSend();
    }
  }

  function autoresize() {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }

  // --- Voice command (Web Speech API: speech -> text) ---
  function toggleVoice() {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) {
      toast.error("Voice input isn't supported in this browser — try Chrome or Edge.");
      return;
    }
    if (listening) {
      recognitionRef.current?.stop();
      return;
    }
    const rec = new SR();
    rec.lang = "en-US";
    rec.interimResults = true;
    rec.continuous = false;
    const base = value.trim();
    rec.onresult = (e: any) => {
      let transcript = "";
      for (let i = 0; i < e.results.length; i++) transcript += e.results[i][0].transcript;
      onChange((base ? base + " " : "") + transcript);
      autoresize();
    };
    rec.onerror = (e: any) => {
      setListening(false);
      if (e.error !== "aborted") toast.error("Voice input error — please try again.");
    };
    rec.onend = () => {
      setListening(false);
      recognitionRef.current = null;
    };
    recognitionRef.current = rec;
    setListening(true);
    rec.start();
    toast("Listening… speak now");
  }

  const menuItems = [
    { icon: Paperclip, label: "Add photos & files", hint: "Upload from computer", onClick: () => fileInputRef.current?.click() },
    { icon: Globe, label: "Web search", hint: "Find real-time info", onClick: () => toast("Web search — coming soon") },
    { icon: ImageIcon, label: "Create image", hint: "Visualize anything", onClick: () => toast("Image generation — coming soon") },
  ];

  return (
    <div
      className="composer"
      onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={(e) => { e.preventDefault(); setIsDragOver(false); addFiles(e.dataTransfer.files); }}
    >
      <div
        className={`composer-inner glass ${isDragOver ? "drag-over" : ""}`}
        style={isDragOver ? { borderColor: "var(--primary)", backgroundColor: "var(--primary-soft)" } : {}}
      >
        <input type="file" ref={fileInputRef} multiple style={{ display: "none" }}
          onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }} />

        {/* "+" menu */}
        <div style={{ position: "relative", alignSelf: "flex-end" }}>
          <button
            className={`icon-btn sm ${menuOpen ? "on" : ""}`}
            title="Add"
            onClick={() => setMenuOpen((o) => !o)}
            style={{ marginBottom: "4px" }}
          >
            <Plus size={18} />
          </button>
          {menuOpen && (
            <>
              <div className="menu-backdrop" onClick={() => setMenuOpen(false)} />
              <div className="composer-menu">
                {menuItems.map(({ icon: Icon, label, hint, onClick }) => (
                  <button key={label} className="composer-menu-item"
                    onClick={() => { setMenuOpen(false); onClick(); }}>
                    <Icon size={17} />
                    <span className="mi-label">{label}</span>
                    <span className="mi-hint">{hint}</span>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        <div style={{ display: "flex", flexDirection: "column", flex: 1 }}>
          {files.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "8px", marginTop: "4px" }}>
              {files.map((f, idx) => (
                <div key={idx} className="file-chip">
                  <FileText size={12} />
                  <span>{f.name}</span>
                  <button onClick={() => setFiles((prev) => prev.filter((_, i) => i !== idx))} aria-label={`Remove ${f.name}`}>×</button>
                </div>
              ))}
            </div>
          )}
          <textarea
            ref={ref}
            className="composer-input"
            placeholder="Ask Nexora"
            rows={1}
            value={value}
            onChange={(e) => { onChange(e.target.value); autoresize(); }}
            onKeyDown={handleKey}
          />
        </div>

        <div className="composer-tools">
          {/* Voice command */}
          <button
            className={`icon-btn sm mic-btn ${listening ? "listening" : ""}`}
            title={listening ? "Stop listening" : "Voice input"}
            onClick={toggleVoice}
          >
            <Mic size={17} />
          </button>

          {busy ? (
            <button className="send-btn stop" onClick={onStop} title="Stop generation">
              <Square size={14} fill="currentColor" />
            </button>
          ) : (
            <button className="send-btn" onClick={doSend}
              disabled={preparing || (!value.trim() && files.length === 0)}
              title={preparing ? "Reading files…" : "Send message"}>
              {preparing ? <span className="btn-spinner" /> : <ArrowUp size={18} />}
            </button>
          )}
        </div>
      </div>
      <p className="composer-hint">
        Nexora may produce inaccurate information. Consider verifying important details.
      </p>
    </div>
  );
}

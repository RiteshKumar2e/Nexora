import type {
  Conversation,
  ConversationDetail,
  DoneEvent,
  MetaEvent,
} from "./types";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

function getAuthHeaders(): HeadersInit {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("nexora_token");
    if (token) {
      return {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json",
      };
    }
  }
  return {
    "Content-Type": "application/json",
  };
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    let message = `${res.status} ${res.statusText}`;
    try {
      const parsed = JSON.parse(text);
      if (parsed.detail) message = parsed.detail;
    } catch {}
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listConversations: () =>
    fetch(`${API_URL}/api/conversations`, {
      headers: getAuthHeaders(),
    }).then(json<Conversation[]>),

  getConversation: (id: string) =>
    fetch(`${API_URL}/api/conversations/${id}`, {
      headers: getAuthHeaders(),
    }).then(json<ConversationDetail>),

  deleteConversation: (id: string) =>
    fetch(`${API_URL}/api/conversations/${id}`, {
      method: "DELETE",
      headers: getAuthHeaders(),
    }),

  renameConversation: (id: string, title: string) =>
    fetch(`${API_URL}/api/conversations/${id}`, {
      method: "PATCH",
      headers: getAuthHeaders(),
      body: JSON.stringify({ title }),
    }).then(json<Conversation>),

  setPinned: (id: string, pinned: boolean) =>
    fetch(`${API_URL}/api/conversations/${id}`, {
      method: "PATCH",
      headers: getAuthHeaders(),
      body: JSON.stringify({ pinned }),
    }).then(json<Conversation>),
};

export interface StreamHandlers {
  onMeta?: (e: MetaEvent) => void;
  onToken: (delta: string) => void;
  onDone?: (e: DoneEvent) => void;
  onError?: (message: string) => void;
}

/**
 * POST /api/chat and consume the Server-Sent Events stream.
 * Returns an AbortController so the caller can cancel generation.
 */
export function streamChat(
  body: { message: string; conversation_id?: string; model?: string },
  handlers: StreamHandlers,
): AbortController {
  const controller = new AbortController();

  (async () => {
    const headers = getAuthHeaders() as Record<string, string>;
    const res = await fetch(`${API_URL}/api/chat`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    if (!res.ok || !res.body) {
      let errText = `Request failed: ${res.status}`;
      try {
        const jsonErr = await res.json();
        if (jsonErr.detail) errText = jsonErr.detail;
      } catch {}
      handlers.onError?.(errText);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";

      for (const frame of frames) {
        let event = "message";
        let data = "";
        for (const line of frame.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) data += line.slice(5).trim();
        }
        if (!data) continue;
        const payload = JSON.parse(data);

        if (event === "meta") handlers.onMeta?.(payload);
        else if (event === "token") handlers.onToken(payload.delta);
        else if (event === "done") handlers.onDone?.(payload);
        else if (event === "error") handlers.onError?.(payload.message);
      }
    }
  })().catch((err) => {
    if (err?.name !== "AbortError") handlers.onError?.(String(err));
  });

  return controller;
}

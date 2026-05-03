import React from "react";

interface ChatSectionProps {
  token: string | null;
  wsStatus: string;
  wsStatusText: string;
  lastPing: string | null;
  connect: () => void;
  disconnect: () => void;
  text: string;
  setText: (val: string) => void;
  handleSendMessage: (e: React.SyntheticEvent) => void;
  messages: string[];
}

export function ChatSection({
  token,
  wsStatus,
  wsStatusText,
  lastPing,
  connect,
  disconnect,
  text,
  setText,
  handleSendMessage,
  messages,
}: ChatSectionProps) {
  return (
    <section>
      <h2>③ リアルタイムチャット</h2>
      <div style={{ display: "flex", alignItems: "center", gap: "1rem", marginBottom: "1rem", flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button onClick={connect} disabled={!token || wsStatus !== "disconnected"}>
            接続
          </button>
          <button
            onClick={disconnect}
            disabled={wsStatus === "disconnected"}
            style={{ background: "rgba(255,255,255,0.1)", border: "1px solid var(--border)" }}
          >
            切断
          </button>
        </div>
        <div style={{ display: "flex", gap: "1rem", fontSize: "0.9rem" }}>
          <span>状態: <b style={{ color: wsStatus === "connected" ? "var(--success)" : "var(--accent-primary)" }}>{wsStatusText}</b></span>
          <span>Ping: <b style={{ color: "var(--accent-primary)" }}>{lastPing ?? "-"}</b></span>
        </div>
      </div>

      <form onSubmit={handleSendMessage} style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <input
          style={{ flex: 1 }}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="メッセージを入力..."
          disabled={wsStatus !== "connected"}
        />
        <button type="submit" disabled={wsStatus !== "connected" || !text}>
          送信
        </button>
      </form>

      <div style={{ background: "rgba(0,0,0,0.2)", borderRadius: "0.5rem", padding: "1rem", minHeight: "200px", maxHeight: "300px", overflowY: "auto" }}>
        {messages.length === 0 ? (
          <p style={{ color: "var(--text-secondary)", textAlign: "center", marginTop: "4rem" }}>
            メッセージはありません
          </p>
        ) : (
          <ul style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            {messages.map((m, i) => (
              <li key={i} style={{ border: "none", background: "rgba(255,255,255,0.05)", padding: "0.5rem 0.8rem", borderRadius: "0.4rem" }}>
                {m}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

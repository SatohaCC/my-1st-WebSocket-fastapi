"use client";

import { useEffect, useRef, useState } from "react";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";

type ServerMessage =
  | { type: "message"; username: string; text: string }
  | { type: "join"; username: string }
  | { type: "leave"; username: string }
  | { type: "error"; text: string };

export default function Home() {
  const [username, setUsername] = useState("");
  const [text, setText] = useState("");
  const [messages, setMessages] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // アンマウント時に接続を閉じる
  useEffect(() => {
    return () => wsRef.current?.close();
  }, []);

  function connect() {
    if (!username || wsRef.current) return;
    const ws = new WebSocket(`${WS_URL}?username=${encodeURIComponent(username)}`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onmessage = (e: MessageEvent<string>) => {
      const msg: ServerMessage = JSON.parse(e.data);
      setMessages((prev) => {
        if (msg.type === "message") return [...prev, `${msg.username}: ${msg.text}`];
        if (msg.type === "join")    return [...prev, `[${msg.username} が入室しました]`];
        if (msg.type === "leave")   return [...prev, `[${msg.username} が退室しました]`];
        if (msg.type === "error")   return [...prev, `[エラー: ${msg.text}]`];
        return prev;
      });
    };
    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;
    };
    ws.onerror = () => ws.close();
  }

  function disconnect() {
    wsRef.current?.close();
  }

  function sendMessage(e: React.SyntheticEvent) {
    e.preventDefault();
    if (wsRef.current?.readyState !== WebSocket.OPEN || !text) return;
    wsRef.current.send(JSON.stringify({ type: "message", text }));
    setText("");
  }

  return (
    <main style={{ padding: "1rem", fontFamily: "monospace" }}>
      <h1>WebSocket JSON Chat (Next.js)</h1>

      <div style={{ marginBottom: "0.5rem" }}>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="名前"
          disabled={connected}
        />
        <button onClick={connect} disabled={connected || !username}>
          入室
        </button>
        <button onClick={disconnect} disabled={!connected}>
          退室
        </button>
      </div>

      <p>状態: {connected ? "接続済み" : "未接続"}</p>

      <form onSubmit={sendMessage} style={{ marginBottom: "0.5rem" }}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="メッセージ"
          disabled={!connected}
        />
        <button type="submit" disabled={!connected || !text}>
          Send
        </button>
      </form>

      <ul>
        {messages.map((m, i) => (
          <li key={i}>{m}</li>
        ))}
      </ul>
    </main>
  );
}

"use client";

import {useEffect, useRef, useState} from "react";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";

// サーバー設定と合わせる（PING_INTERVAL + PONG_TIMEOUT + 余裕）
const PING_TIMEOUT_MS = (10 + 5 + 2) * 1000;

type ServerMessage =
  | { type: "message"; username: string; text: string }
  | { type: "join"; username: string }
  | { type: "leave"; username: string }
  | { type: "error"; text: string }
  | { type: "ping" };

export default function Home() {
  const [username, setUsername] = useState("");
  const [text, setText] = useState("");
  const [messages, setMessages] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);
  const [lastPing, setLastPing] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      wsRef.current?.close();
      clearPingTimeout();
    };
  }, []);

  function clearPingTimeout() {
    if (pingTimeoutRef.current) {
      clearTimeout(pingTimeoutRef.current);
      pingTimeoutRef.current = null;
    }
  }

  function resetPingTimeout(ws: WebSocket) {
    clearPingTimeout();
    pingTimeoutRef.current = setTimeout(() => {
      // ネットワーク断中は ws.close() が onclose を発火しないため直接状態を更新する
      setConnected(false);
      wsRef.current = null;
      clearPingTimeout();
      ws.close();
    }, PING_TIMEOUT_MS);
  }

  function connect() {
    if (!username || wsRef.current) return;
    const ws = new WebSocket(`${WS_URL}?username=${encodeURIComponent(username)}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      resetPingTimeout(ws);
    };
    ws.onmessage = (e: MessageEvent<string>) => {
      const msg: ServerMessage = JSON.parse(e.data);
      if (msg.type === "ping") {
        setLastPing(new Date().toLocaleTimeString());
        ws.send(JSON.stringify({ type: "pong" }));
        resetPingTimeout(ws);  // ping を受け取るたびにタイムアウトをリセット
        return;
      }
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
      clearPingTimeout();
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
      <h1>WebSocket Chat + Ping/Pong (Next.js)</h1>

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
      <p>最後の Ping: {lastPing ?? "-"}</p>

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

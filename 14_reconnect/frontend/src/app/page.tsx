"use client";

import { useEffect, useRef, useState } from "react";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";
const PING_TIMEOUT_MS = (10 + 5 + 2) * 1000;
const INITIAL_RETRY_MS = 1000;
const MAX_RETRY_MS = 30000;

type ServerMessage =
  | { type: "message"; username: string; text: string }
  | { type: "join"; username: string }
  | { type: "leave"; username: string }
  | { type: "error"; text: string }
  | { type: "ping" };

type Status = "disconnected" | "connected" | "reconnecting";

export default function Home() {
  const [username, setUsername] = useState("");
  const [text, setText] = useState("");
  const [messages, setMessages] = useState<string[]>([]);
  const [status, setStatus] = useState<Status>("disconnected");
  const [lastPing, setLastPing] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const pingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryMsRef = useRef(INITIAL_RETRY_MS);
  const isManualRef = useRef(false);
  const usernameRef = useRef("");

  useEffect(() => { usernameRef.current = username; }, [username]);

  useEffect(() => {
    return () => {
      isManualRef.current = true;
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

  function scheduleReconnect() {
    const delay = retryMsRef.current;
    setStatus("reconnecting");
    setMessages((prev) => [...prev, `[${delay / 1000}秒後に再接続します]`]);
    setTimeout(() => {
      if (!isManualRef.current) connectWithUsername(usernameRef.current);
    }, delay);
    retryMsRef.current = Math.min(delay * 2, MAX_RETRY_MS);
  }

  function connectWithUsername(uname: string) {
    if (wsRef.current) return;
    const ws = new WebSocket(`${WS_URL}?username=${encodeURIComponent(uname)}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("connected");
      retryMsRef.current = INITIAL_RETRY_MS;
      resetPingTimeout(ws);
    };
    ws.onmessage = (e: MessageEvent<string>) => {
      const msg: ServerMessage = JSON.parse(e.data);
      if (msg.type === "ping") {
        setLastPing(new Date().toLocaleTimeString());
        ws.send(JSON.stringify({ type: "pong" }));
        resetPingTimeout(ws);
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
      clearPingTimeout();
      const alreadyHandled = wsRef.current === null;
      wsRef.current = null;
      if (alreadyHandled) return;  // ping タイムアウトが先に処理済み
      if (isManualRef.current) {
        setStatus("disconnected");
      } else {
        scheduleReconnect();
      }
    };
    ws.onerror = () => ws.close();
  }

  function resetPingTimeout(ws: WebSocket) {
    clearPingTimeout();
    pingTimeoutRef.current = setTimeout(() => {
      wsRef.current = null;  // onclose より先に処理したことを示す
      clearPingTimeout();
      ws.close();
      if (isManualRef.current) {
        setStatus("disconnected");
      } else {
        setMessages((prev) => [...prev, "[ping タイムアウト]"]);
        scheduleReconnect();
      }
    }, PING_TIMEOUT_MS);
  }

  function connect() {
    if (!username || wsRef.current) return;
    isManualRef.current = false;
    retryMsRef.current = INITIAL_RETRY_MS;
    connectWithUsername(username);
  }

  function disconnect() {
    isManualRef.current = true;
    clearPingTimeout();
    if (wsRef.current) {
      wsRef.current.close();
    } else {
      // 再接続待機中（wsRef は null だが reconnecting 状態）
      setStatus("disconnected");
    }
  }

  function sendMessage(e: React.SyntheticEvent) {
    e.preventDefault();
    if (wsRef.current?.readyState !== WebSocket.OPEN || !text) return;
    wsRef.current.send(JSON.stringify({ type: "message", text }));
    setText("");
  }

  const statusText =
    status === "connected"    ? "接続済み" :
    status === "reconnecting" ? "再接続中..." :
    "未接続";

  return (
    <main style={{ padding: "1rem", fontFamily: "monospace" }}>
      <h1>WebSocket Chat + Ping/Pong + 再接続 (Next.js)</h1>

      <div style={{ marginBottom: "0.5rem" }}>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="名前"
          disabled={status !== "disconnected"}
        />
        <button onClick={connect} disabled={status !== "disconnected" || !username}>
          入室
        </button>
        <button onClick={disconnect} disabled={status === "disconnected"}>
          退室
        </button>
      </div>

      <p>状態: {statusText}</p>
      <p>最後の Ping: {lastPing ?? "-"}</p>

      <form onSubmit={sendMessage} style={{ marginBottom: "0.5rem" }}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="メッセージ"
          disabled={status !== "connected"}
        />
        <button type="submit" disabled={status !== "connected" || !text}>
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

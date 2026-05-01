"use client";

import { useEffect, useRef, useState } from "react";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";
// REST エンドポイントのベース URL（/token に POST する）
const HTTP_URL = process.env.NEXT_PUBLIC_HTTP_URL ?? "http://localhost:8000";
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
  // ログインフォーム用
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  // ログイン成功後に保持する JWT。null = 未ログイン
  const [token, setToken] = useState<string | null>(null);

  const [text, setText] = useState("");
  const [messages, setMessages] = useState<string[]>([]);
  const [status, setStatus] = useState<Status>("disconnected");
  const [lastPing, setLastPing] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const pingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryMsRef = useRef(INITIAL_RETRY_MS);
  const isManualRef = useRef(false);
  // setTimeout のコールバックは作成時の token を閉じ込める。
  // ref でミラーリングすることで再接続時に常に最新の JWT を使える
  const tokenRef = useRef<string | null>(null);

  useEffect(() => { tokenRef.current = token; }, [token]);

  // アンマウント時のクリーンアップ
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

  async function login() {
    const res = await fetch(`${HTTP_URL}/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      setMessages(["[ログイン失敗: ユーザー名またはパスワードが違います]"]);
      return;
    }
    const data = await res.json();
    setToken(data.access_token);
    setPassword(""); // パスワードをメモリに残さない
  }

  function logout() {
    // 手動切断と同じ扱いにして再接続を抑止する
    isManualRef.current = true;
    clearPingTimeout();
    if (wsRef.current) {
      wsRef.current.close();
    } else {
      setStatus("disconnected");
    }
    setToken(null);
    setPassword("");
    setMessages([]);
  }

  function scheduleReconnect() {
    const delay = retryMsRef.current;
    setStatus("reconnecting");
    setMessages((prev) => [...prev, `[${delay / 1000}秒後に再接続します]`]);
    setTimeout(() => {
      if (!isManualRef.current) connectWithToken();
    }, delay);
    retryMsRef.current = Math.min(delay * 2, MAX_RETRY_MS);
  }

  function connectWithToken() {
    if (wsRef.current || !tokenRef.current) return;
    // ユーザー名ではなく JWT をクエリパラメータで渡す。
    // サーバーは JWT を検証してユーザー名を取り出すため URL に username は不要
    const ws = new WebSocket(`${WS_URL}?token=${encodeURIComponent(tokenRef.current)}`);
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
      if (alreadyHandled) return;
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
      wsRef.current = null;
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
    if (!token || wsRef.current) return;
    isManualRef.current = false;
    retryMsRef.current = INITIAL_RETRY_MS;
    connectWithToken();
  }

  function disconnect() {
    isManualRef.current = true;
    clearPingTimeout();
    if (wsRef.current) {
      wsRef.current.close();
    } else {
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
      <h1>WebSocket Chat + JWT 認証 (Next.js)</h1>

      {token === null ? (
        // フェーズ1: ログインフォーム
        <div style={{ marginBottom: "0.5rem" }}>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="ユーザー名"
          />
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="パスワード"
            type="password"
          />
          <button onClick={login} disabled={!username || !password}>
            ログイン
          </button>
        </div>
      ) : (
        // フェーズ2: 接続フォーム（ログイン済み）
        <div style={{ marginBottom: "0.5rem" }}>
          <span>ユーザー: {username}</span>
          {"　"}
          <button onClick={connect} disabled={status !== "disconnected"}>
            接続
          </button>
          <button onClick={disconnect} disabled={status === "disconnected"}>
            切断
          </button>
          <button onClick={logout}>
            ログアウト
          </button>
        </div>
      )}

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

"use client";

import { useEffect, useRef, useState } from "react";

const HTTP_URL = process.env.NEXT_PUBLIC_HTTP_URL ?? "http://localhost:8000";
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

type WsStatus = "disconnected" | "connected" | "reconnecting";

// JWT のペイロード部分（中央のパート）を base64 デコードして JSON を返す
function decodeJwtPayload(token: string): object | null {
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const obj = JSON.parse(atob(base64));
    if (typeof obj.exp === "number") {
      obj.exp_readable = new Date(obj.exp * 1000).toLocaleString();
    }
    return obj;
  } catch {
    return null;
  }
}

// JWT を ヘッダー・ペイロード・署名 の3パートに色分けして表示するコンポーネント
function JwtDisplay({ token }: { token: string }) {
  const [h, p, s] = token.split(".");
  return (
    <pre style={{ wordBreak: "break-all", whiteSpace: "pre-wrap" }}>
      <span style={{ background: "#ffd6d6" }}>{h}</span>
      {".\n"}
      <span style={{ background: "#d6ffd6" }}>{p}</span>
      {".\n"}
      <span style={{ background: "#d6d6ff" }}>{s}</span>
    </pre>
  );
}

export default function Home() {
  // ログインフォーム用
  const [username, setUsername] = useState("alice");
  const [password, setPassword] = useState("password1");
  const [token, setToken] = useState<string | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);

  // GET /me 結果
  const [meResult, setMeResult] = useState<string | null>(null);

  // HTTP ログ
  const [httpLogs, setHttpLogs] = useState<string[]>([]);

  // WebSocket チャット用
  const [text, setText] = useState("");
  const [messages, setMessages] = useState<string[]>([]);
  const [wsStatus, setWsStatus] = useState<WsStatus>("disconnected");
  const [lastPing, setLastPing] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const pingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryMsRef = useRef(INITIAL_RETRY_MS);
  const isManualRef = useRef(false);
  // setTimeout のコールバックは作成時の token を閉じ込める。
  // ref でミラーリングすることで再接続時に常に最新の JWT を使える
  const tokenRef = useRef<string | null>(null);

  useEffect(() => {
    tokenRef.current = token;
  }, [token]);

  // アンマウント時のクリーンアップ
  useEffect(() => {
    return () => {
      isManualRef.current = true;
      wsRef.current?.close();
      clearPingTimeout();
    };
  }, []);

  function addHttpLog(msg: string) {
    setHttpLogs((prev) => [msg, ...prev]);
  }

  function clearPingTimeout() {
    if (pingTimeoutRef.current) {
      clearTimeout(pingTimeoutRef.current);
      pingTimeoutRef.current = null;
    }
  }

  async function login() {
    setLoginError(null);
    addHttpLog(`POST /token  { username: "${username}" }`);
    const res = await fetch(`${HTTP_URL}/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (!res.ok) {
      const msg = (data as { detail: string }).detail;
      setLoginError(msg);
      setToken(null);
      addHttpLog(`  → ${res.status} ${msg}`);
      return;
    }
    const jwt = (data as { access_token: string }).access_token;
    setToken(jwt);
    addHttpLog(`  → 200 OK`);
  }

  async function fetchMe(withToken: boolean) {
    const headers: HeadersInit = {};
    if (withToken && token) {
      headers["Authorization"] = `Bearer ${token}`;
      addHttpLog(`GET /me  Authorization: Bearer ${token.slice(0, 24)}...`);
    } else {
      addHttpLog("GET /me  （Authorization ヘッダーなし）");
    }
    const res = await fetch(`${HTTP_URL}/me`, { headers });
    const data = await res.json();
    setMeResult(`${res.status}\n${JSON.stringify(data, null, 2)}`);
    addHttpLog(`  → ${res.status}  ${JSON.stringify(data)}`);
  }

  function logout() {
    isManualRef.current = true;
    clearPingTimeout();
    if (wsRef.current) {
      wsRef.current.close();
    } else {
      setWsStatus("disconnected");
    }
    setToken(null);
    setPassword("");
    setMessages([]);
    setMeResult(null);
  }

  function scheduleReconnect() {
    const delay = retryMsRef.current;
    setWsStatus("reconnecting");
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
      setWsStatus("connected");
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
        setWsStatus("disconnected");
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
        setWsStatus("disconnected");
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
      setWsStatus("disconnected");
    }
  }

  function sendMessage(e: React.SyntheticEvent) {
    e.preventDefault();
    if (wsRef.current?.readyState !== WebSocket.OPEN || !text) return;
    wsRef.current.send(JSON.stringify({ type: "message", text }));
    setText("");
  }

  const payload = token ? decodeJwtPayload(token) : null;
  const wsStatusText =
    wsStatus === "connected"    ? "接続済み" :
    wsStatus === "reconnecting" ? "再接続中..." :
    "未接続";

  return (
    <main style={{ padding: "1rem", fontFamily: "monospace", maxWidth: "800px" }}>
      <h1>JWT 認証 + WebSocket チャット</h1>

      {/* ① ログイン */}
      <section style={{ marginBottom: "1.5rem" }}>
        <h2>① ログイン（POST /token）</h2>
        {token === null ? (
          <>
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
            {loginError && <p style={{ color: "red" }}>失敗: {loginError}</p>}
          </>
        ) : (
          <p style={{ color: "green" }}>
            ログイン済み: {username}{"　"}
            <button onClick={logout}>ログアウト</button>
          </p>
        )}
      </section>

      {/* ② JWT の中身 */}
      {token && (
        <section style={{ marginBottom: "1.5rem" }}>
          <h2>② 取得した JWT</h2>
          <p>
            JWT は{" "}
            <span style={{ background: "#ffd6d6", padding: "0 4px" }}>ヘッダー</span>
            {" . "}
            <span style={{ background: "#d6ffd6", padding: "0 4px" }}>ペイロード</span>
            {" . "}
            <span style={{ background: "#d6d6ff", padding: "0 4px" }}>署名</span>
            {" の3パートを . でつないだ文字列"}
          </p>
          <JwtDisplay token={token} />
          <h3>ペイロードのデコード（base64）</h3>
          <p>ペイロードは base64 なのでブラウザ側でも中身を読める。署名の検証はしない。</p>
          <pre style={{ background: "#f4f4f4", padding: "0.8rem" }}>
            {JSON.stringify(payload, null, 2)}
          </pre>
        </section>
      )}

      {/* ③ 保護されたエンドポイント（GET /me） */}
      <section style={{ marginBottom: "1.5rem" }}>
        <h2>③ 保護されたエンドポイント（GET /me）</h2>
        <p>リクエストヘッダー: <code>Authorization: Bearer &lt;token&gt;</code></p>
        <button onClick={() => fetchMe(true)} disabled={!token}>
          正しいトークンで GET /me
        </button>
        <button onClick={() => fetchMe(false)}>
          トークンなしで GET /me
        </button>
        {meResult && (
          <pre style={{ background: "#f4f4f4", padding: "0.8rem" }}>
            {meResult}
          </pre>
        )}
      </section>

      {/* ④ WebSocket チャット */}
      <section style={{ marginBottom: "1.5rem" }}>
        <h2>④ WebSocket チャット</h2>
        <p>
          JWT をクエリパラメータで渡して接続する:{" "}
          <code>ws://...?token=&lt;jwt&gt;</code>
        </p>
        <div style={{ marginBottom: "0.5rem" }}>
          <button onClick={connect} disabled={!token || wsStatus !== "disconnected"}>
            接続
          </button>
          <button onClick={disconnect} disabled={wsStatus === "disconnected"}>
            切断
          </button>
          <span style={{ marginLeft: "1rem" }}>状態: {wsStatusText}</span>
          <span style={{ marginLeft: "1rem" }}>最後の Ping: {lastPing ?? "-"}</span>
        </div>
        <form onSubmit={sendMessage} style={{ marginBottom: "0.5rem" }}>
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="メッセージ"
            disabled={wsStatus !== "connected"}
          />
          <button type="submit" disabled={wsStatus !== "connected" || !text}>
            Send
          </button>
        </form>
        <ul>
          {messages.map((m, i) => (
            <li key={i}>{m}</li>
          ))}
        </ul>
      </section>

      {/* ⑤ HTTP ログ */}
      <section>
        <h2>⑤ HTTP ログ</h2>
        <ul>
          {httpLogs.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
      </section>
    </main>
  );
}

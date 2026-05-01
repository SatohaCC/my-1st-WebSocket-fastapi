"use client";

import { useState } from "react";

const HTTP_URL = process.env.NEXT_PUBLIC_HTTP_URL ?? "http://localhost:8000";

// JWT のペイロード部分（中央のパート）を base64 デコードして JSON を返す
function decodeJwtPayload(token: string): object | null {
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const obj = JSON.parse(atob(base64));
    // exp は Unix 秒なので人間が読める形式を追加する
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
  const [username, setUsername] = useState("alice");
  const [password, setPassword] = useState("password1");
  const [token, setToken] = useState<string | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [meResult, setMeResult] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);

  function addLog(msg: string) {
    setLogs((prev) => [msg, ...prev]);
  }

  async function login() {
    setLoginError(null);
    addLog(`POST /token  { username: "${username}" }`);
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
      addLog(`  → ${res.status} ${msg}`);
      return;
    }
    const jwt = (data as { access_token: string }).access_token;
    setToken(jwt);
    addLog(`  → 200 OK`);
  }

  async function fetchMe(withToken: boolean) {
    const headers: HeadersInit = {};
    if (withToken && token) {
      headers["Authorization"] = `Bearer ${token}`;
      addLog(`GET /me  Authorization: Bearer ${token.slice(0, 24)}...`);
    } else {
      addLog("GET /me  （Authorization ヘッダーなし）");
    }
    const res = await fetch(`${HTTP_URL}/me`, { headers });
    const data = await res.json();
    setMeResult(`${res.status}\n${JSON.stringify(data, null, 2)}`);
    addLog(`  → ${res.status}  ${JSON.stringify(data)}`);
  }

  const payload = token ? decodeJwtPayload(token) : null;

  return (
    <main style={{ padding: "1rem", fontFamily: "monospace", maxWidth: "800px" }}>
      <h1>JWT 学習</h1>

      {/* ① ログイン */}
      <section style={{ marginBottom: "1.5rem" }}>
        <h2>① ログイン（POST /token）</h2>
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
        {loginError && (
          <p style={{ color: "red" }}>失敗: {loginError}</p>
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

      {/* ③ 保護されたエンドポイント */}
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

      {/* ④ HTTP ログ */}
      <section>
        <h2>④ HTTP ログ</h2>
        <ul>
          {logs.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
      </section>
    </main>
  );
}

"use client";

import {useState} from "react";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";

export default function Home() {
  const [username, setUsername] = useState("");
  const [text, setText] = useState("");
  const [messages, setMessages] = useState<string[]>([]);
  const [ws, setWs] = useState<WebSocket | null>(null);

  function connect() {
    if (!username || ws) return;
    const newWs = new WebSocket(`${WS_URL}?username=${username}`);
    newWs.onmessage = (e) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const msg: any = JSON.parse(e.data);
      const line =
        msg.type === "message" ? `${msg.username}: ${msg.text}` :
        msg.type === "join"    ? `[${msg.username} が入室しました]` :
        msg.type === "leave"   ? `[${msg.username} が退室しました]` :
                                 `[エラー: ${msg.text}]`;
      setMessages((prev) => [...prev, line]);
    };
    newWs.onclose = () => setWs(null);
    setWs(newWs);
  }

  function disconnect() {
    ws?.close();
  }

  function sendMessage(e: React.SyntheticEvent) {
    e.preventDefault();
    if (!ws || !text) return;
    ws.send(JSON.stringify({ type: "message", text }));
    setText("");
  }

  return (
    <main style={{ padding: "1rem", fontFamily: "monospace" }}>
      <h1>WebSocket Chat (Next.js)</h1>

      <div style={{ marginBottom: "0.5rem" }}>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="名前"
          disabled={!!ws}
        />
        <button onClick={connect} disabled={!!ws || !username}>
          入室
        </button>
        <button onClick={disconnect} disabled={!ws}>
          退室
        </button>
      </div>

      <p>状態: {ws ? "接続済み" : "未接続"}</p>

      <form onSubmit={sendMessage} style={{ marginBottom: "0.5rem" }}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="メッセージ"
          disabled={!ws}
        />
        <button type="submit" disabled={!ws || !text}>
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

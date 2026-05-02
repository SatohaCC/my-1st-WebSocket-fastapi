"use client";

import {useEffect, useRef, useState} from "react";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";
// サーバーの PING_INTERVAL(10) + PONG_TIMEOUT(5) + 余裕(2) 秒
const PING_TIMEOUT_MS = (10 + 5 + 2) * 1000;
const INITIAL_RETRY_MS = 1000;
const MAX_RETRY_MS = 30000;
// as const: 要素の型を string ではなく "general" | "tech" | "random" のリテラル型に絞る
const CHANNELS = ["general", "tech", "random"] as const;

// CHANNELS の要素から Union 型を導出する。CHANNELS を変えれば自動で追従する
type Channel = (typeof CHANNELS)[number];

// discriminated union: type フィールドで絞り込むと他フィールドの型も確定する
type ServerMessage =
  | { type: "message"; channel: Channel; username: string; text: string }
  | { type: "join"; channel: Channel; username: string }
  | { type: "leave"; channel: Channel; username: string }
  | { type: "error"; text: string }
  | { type: "ping" };

type Status = "disconnected" | "connected" | "reconnecting";

export default function Home() {
  const [username, setUsername] = useState("");
  const [text, setText] = useState("");
  const [messages, setMessages] = useState<string[]>([]);
  const [status, setStatus] = useState<Status>("disconnected");
  const [lastPing, setLastPing] = useState<string | null>(null);
  // Set を state にすることで subscribedChannels.has() の結果が変わると再レンダリングされる
  const [subscribedChannels, setSubscribedChannels] = useState<Set<Channel>>(new Set());
  const [selectedChannel, setSelectedChannel] = useState<Channel>("general");

  const wsRef = useRef<WebSocket | null>(null);
  const pingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryMsRef = useRef(INITIAL_RETRY_MS);
  // true のとき onclose / ping タイムアウトで再接続しない
  const isManualRef = useRef(false);
  // setTimeout のコールバックは作成時の username を閉じ込める。
  // ref でミラーリングすることで常に最新値を参照できる
  const usernameRef = useRef("");

  useEffect(() => { usernameRef.current = username; }, [username]);

  // アンマウント時のクリーンアップ。isManualRef を先に立てることで onclose が再接続しない
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
    // 再接続すると新しい WebSocket オブジェクトになるためサーバー側の購読も消える
    setSubscribedChannels(new Set());
    setMessages((prev) => [...prev, `[${delay / 1000}秒後に再接続します]`]);
    setTimeout(() => {
      // 待機中に手動切断された場合はスキップ
      if (!isManualRef.current) connectWithUsername(usernameRef.current);
    }, delay);
    // 次回の待機時間を倍にする（上限あり）
    retryMsRef.current = Math.min(delay * 2, MAX_RETRY_MS);
  }

  function connectWithUsername(uname: string) {
    // 再接続ループで二重接続しないためのガード
    if (wsRef.current) return;
    const ws = new WebSocket(`${WS_URL}?username=${encodeURIComponent(uname)}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus("connected");
      retryMsRef.current = INITIAL_RETRY_MS; // 再接続成功したら待機時間をリセット
      resetPingTimeout(ws);
    };
    ws.onmessage = (e: MessageEvent<string>) => {
      const msg: ServerMessage = JSON.parse(e.data);
      if (msg.type === "ping") {
        setLastPing(new Date().toLocaleTimeString());
        ws.send(JSON.stringify({ type: "pong" }));
        resetPingTimeout(ws); // ping を受け取るたびにタイムアウトをリセット
        return; // ping はメッセージ履歴に流さない
      }
      setMessages((prev) => {
        if (msg.type === "message")
          return [...prev, `[#${msg.channel}] ${msg.username}: ${msg.text}`];
        if (msg.type === "join")
          return [...prev, `[#${msg.channel}] ${msg.username} が参加しました`];
        if (msg.type === "leave")
          return [...prev, `[#${msg.channel}] ${msg.username} が退室しました`];
        if (msg.type === "error")
          return [...prev, `[エラー: ${msg.text}]`];
        return prev;
      });
    };
    ws.onclose = () => {
      clearPingTimeout();
      // wsRef.current === null は「ping タイムアウトが先に処理した」を意味するフラグ
      const alreadyHandled = wsRef.current === null;
      wsRef.current = null;
      if (alreadyHandled) return; // 二重に scheduleReconnect を呼ばないようにスキップ
      if (isManualRef.current) {
        setStatus("disconnected");
        setSubscribedChannels(new Set());
      } else {
        scheduleReconnect();
      }
    };
    ws.onerror = () => ws.close();
  }

  function resetPingTimeout(ws: WebSocket) {
    clearPingTimeout();
    pingTimeoutRef.current = setTimeout(() => {
      // onclose より先に処理したことを示すフラグ。
      // ネットワーク断では ws.close() が onclose を発火しないためここで直接状態を更新する
      wsRef.current = null;
      clearPingTimeout();
      ws.close();
      if (isManualRef.current) {
        setStatus("disconnected");
        setSubscribedChannels(new Set());
      } else {
        setMessages((prev) => [...prev, "[ping タイムアウト]"]);
        scheduleReconnect();
      }
    }, PING_TIMEOUT_MS);
  }

  function connect() {
    if (!username || wsRef.current) return;
    isManualRef.current = false; // 接続開始時に自動再接続を許可
    retryMsRef.current = INITIAL_RETRY_MS;
    connectWithUsername(username);
  }

  function disconnect() {
    isManualRef.current = true; // 以降の onclose / タイムアウトで再接続しない
    clearPingTimeout();
    if (wsRef.current) {
      wsRef.current.close(); // 接続中 → onclose 経由で状態更新
    } else {
      // wsRef が null でも reconnecting 状態（タイムアウト待機中）のケースがある
      setStatus("disconnected");
      setSubscribedChannels(new Set());
    }
  }

  function subscribe(channel: Channel) {
    if (wsRef.current?.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: "subscribe", channel }));
    // サーバーからの確認を待たずにローカル状態を先に更新する（楽観的更新）
    setSubscribedChannels((prev) => new Set([...prev, channel]));
  }

  function unsubscribe(channel: Channel) {
    if (wsRef.current?.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: "unsubscribe", channel }));
    setSubscribedChannels((prev) => {
      // Set はミュータブルなので、React に変更を検知させるためコピーしてから delete する
      const next = new Set(prev);
      next.delete(channel);
      return next;
    });
  }

  function sendMessage(e: React.SyntheticEvent) {
    e.preventDefault();
    if (
      wsRef.current?.readyState !== WebSocket.OPEN ||
      !text ||
      !subscribedChannels.has(selectedChannel) // 未参加のチャネルには送れない
    ) return;
    wsRef.current.send(JSON.stringify({ type: "message", channel: selectedChannel, text }));
    setText("");
  }

  const statusText =
    status === "connected"    ? "接続済み" :
    status === "reconnecting" ? "再接続中..." :
    "未接続";

  return (
    <main style={{ padding: "1rem", fontFamily: "monospace" }}>
      <h1>WebSocket Chat + チャネル (Next.js)</h1>

      <div style={{ marginBottom: "0.5rem" }}>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder="名前"
          disabled={status !== "disconnected"}
        />
        <button onClick={connect} disabled={status !== "disconnected" || !username}>
          接続
        </button>
        <button onClick={disconnect} disabled={status === "disconnected"}>
          切断
        </button>
      </div>

      <p>状態: {statusText}</p>
      <p>最後の Ping: {lastPing ?? "-"}</p>

      {status === "connected" && (
        <div style={{ marginBottom: "0.5rem" }}>
          <strong>チャネル: </strong>
          {CHANNELS.map((ch) => (
            <span key={ch} style={{ marginLeft: "0.5rem" }}>
              {subscribedChannels.has(ch) ? (
                <button onClick={() => unsubscribe(ch)}>#{ch} 退出</button>
              ) : (
                <button onClick={() => subscribe(ch)}>#{ch} 参加</button>
              )}
            </span>
          ))}
        </div>
      )}

      <form onSubmit={sendMessage} style={{ marginBottom: "0.5rem" }}>
        <select
          value={selectedChannel}
          onChange={(e) => setSelectedChannel(e.target.value as Channel)}
          disabled={status !== "connected"}
        >
          {CHANNELS.map((ch) => (
            <option key={ch} value={ch}>#{ch}</option>
          ))}
        </select>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="メッセージ"
          disabled={status !== "connected" || !subscribedChannels.has(selectedChannel)}
        />
        <button
          type="submit"
          disabled={status !== "connected" || !text || !subscribedChannels.has(selectedChannel)}
        >
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

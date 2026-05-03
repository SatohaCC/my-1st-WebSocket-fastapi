import type {RefObject} from "react";
import {useEffect, useRef, useState} from "react";
import type {ServerMessage, WsStatus} from "../types/chat";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";
const PING_TIMEOUT_MS = (10 + 5 + 2) * 1000;
const INITIAL_RETRY_MS = 1000;
const MAX_RETRY_MS = 30000;

export function useWebSocket(tokenRef: RefObject<string | null>) {
  const [messages, setMessages] = useState<string[]>([]);
  const [wsStatus, setWsStatus] = useState<WsStatus>("disconnected");
  const [lastPing, setLastPing] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const pingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryMsRef = useRef(INITIAL_RETRY_MS);
  const isManualRef = useRef(false);
  const lastMessageIdRef = useRef<number | null>(null);

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
    setWsStatus("reconnecting");
    setMessages((prev) => [...prev, `[${delay / 1000}秒後に再接続します]`]);
    setTimeout(() => {
      if (!isManualRef.current) connectWithToken();
    }, delay);
    retryMsRef.current = Math.min(delay * 2, MAX_RETRY_MS);
  }

  function connectWithToken() {
    if (wsRef.current || !tokenRef.current) return;
    const lastId = lastMessageIdRef.current;
    const url = lastId !== null
      ? `${WS_URL}?token=${encodeURIComponent(tokenRef.current)}&last_id=${lastId}`
      : `${WS_URL}?token=${encodeURIComponent(tokenRef.current)}`;
    const ws = new WebSocket(url);
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
        if (msg.type === "message") {
          if (msg.id !== undefined) {
            lastMessageIdRef.current = Math.max(lastMessageIdRef.current ?? 0, msg.id);
          }
          return [...prev, `${msg.username}: ${msg.text}`];
        }
        if (msg.type === "join")  return [...prev, `[${msg.username} が入室しました]`];
        if (msg.type === "leave") return [...prev, `[${msg.username} が退室しました]`];
        if (msg.type === "error") return [...prev, `[エラー: ${msg.text}]`];
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
    if (!tokenRef.current || wsRef.current) return;
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

  function sendMessage(text: string) {
    if (wsRef.current?.readyState !== WebSocket.OPEN || !text) return;
    wsRef.current.send(JSON.stringify({ type: "message", text }));
  }

  return {
    messages,
    clearMessages: () => setMessages([]),
    wsStatus,
    lastPing,
    connect,
    disconnect,
    sendMessage,
  };
}

"use client";

import {useEffect, useRef, useState} from "react";
import {useAuth} from "../hooks/useAuth";
import {useWebSocket} from "../hooks/useWebSocket";

// Components
import {AuthSection} from "../components/AuthSection";
import {ChatSection} from "../components/ChatSection";
import {JwtSection} from "../components/JwtSection";
import {LogSection} from "../components/LogSection";
import {ProfileSection} from "../components/ProfileSection";

export default function Home() {
  const [httpLogs, setHttpLogs] = useState<string[]>([]);
  const [text, setText] = useState("");

  const addHttpLog = (msg: string) => {
    setHttpLogs((prev) => [msg, ...prev]);
  };

  const {
    username,
    setUsername,
    password,
    setPassword,
    token,
    login,
    logout,
    loginError,
    fetchMe,
    meResult,
    payload,
    setMeResult,
  } = useAuth({ onLog: addHttpLog });

  const tokenRef = useRef<string | null>(null);
  useEffect(() => {
    tokenRef.current = token;
  }, [token]);

  const {
    messages,
    clearMessages,
    wsStatus,
    lastPing,
    connect,
    disconnect,
    sendMessage,
  } = useWebSocket(tokenRef);

  const handleLogout = () => {
    logout(() => {
      disconnect();
      clearMessages();
    });
  };

  const handleSendMessage = (e: React.SyntheticEvent) => {
    e.preventDefault();
    sendMessage(text);
    setText("");
  };

  const wsStatusText =
    wsStatus === "connected"
      ? "接続済み"
      : wsStatus === "reconnecting"
      ? "再接続中..."
      : "未接続";

  return (
    <main style={{ padding: "2rem", maxWidth: "1000px", margin: "0 auto" }}>
      <header style={{ marginBottom: "3rem", textAlign: "center" }}>
        <h1>WebSocket Chat Pro</h1>
        <p style={{ color: "var(--text-secondary)" }}>
          FastAPI Backend + Next.js Frontend Refactored Edition
        </p>
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))", gap: "1rem" }}>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <AuthSection
            username={username}
            setUsername={setUsername}
            password={password}
            setPassword={setPassword}
            token={token}
            login={login}
            logout={handleLogout}
            loginError={loginError}
          />

          {token && <JwtSection token={token} payload={payload} />}

          <ProfileSection token={token} fetchMe={fetchMe} meResult={meResult} />
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <ChatSection
            token={token}
            wsStatus={wsStatus}
            wsStatusText={wsStatusText}
            lastPing={lastPing}
            connect={connect}
            disconnect={disconnect}
            text={text}
            setText={setText}
            handleSendMessage={handleSendMessage}
            messages={messages}
          />

          <LogSection httpLogs={httpLogs} />
        </div>
      </div>
    </main>
  );
}

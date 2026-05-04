interface AuthSectionProps {
  username: string;
  setUsername: (val: string) => void;
  password: string;
  setPassword: (val: string) => void;
  token: string | null;
  login: () => void;
  logout: () => void;
  loginError: string | null;
}

export function AuthSection({
  username,
  setUsername,
  password,
  setPassword,
  token,
  login,
  logout,
  loginError,
}: AuthSectionProps) {
  return (
    <section>
      <h2>① ログイン</h2>
      {token === null ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", alignItems: "center" }}>
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
          {loginError && <p style={{ color: "var(--error)", width: "100%" }}>失敗: {loginError}</p>}
        </div>
      ) : (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <p style={{ color: "var(--success)", fontWeight: 600 }}>
            ログイン済み: {username}
          </p>
          <button
            onClick={logout}
            style={{ background: "rgba(244, 63, 94, 0.2)", color: "var(--error)", border: "1px solid var(--error)" }}
          >
            ログアウト
          </button>
        </div>
      )}
    </section>
  );
}

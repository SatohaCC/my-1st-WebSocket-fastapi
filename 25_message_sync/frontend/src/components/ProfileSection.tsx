interface ProfileSectionProps {
  token: string | null;
  fetchMe: (withToken: boolean) => void;
  meResult: string | null;
}

export function ProfileSection({ token, fetchMe, meResult }: ProfileSectionProps) {
  return (
    <section>
      <h2>② プロフィール取得</h2>
      <p style={{ color: "var(--text-secondary)", marginBottom: "1rem" }}>
        <code>Authorization: Bearer &lt;token&gt;</code> ヘッダーの検証テスト
      </p>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
        <button onClick={() => fetchMe(true)} disabled={!token}>
          正しいトークンで取得
        </button>
        <button
          onClick={() => fetchMe(false)}
          style={{ background: "transparent", border: "1px solid var(--border)" }}
        >
          トークンなしで取得
        </button>
      </div>
      {meResult && <pre>{meResult}</pre>}
    </section>
  );
}

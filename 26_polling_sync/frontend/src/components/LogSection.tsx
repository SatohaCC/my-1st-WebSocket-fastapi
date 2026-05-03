interface LogSectionProps {
  httpLogs: string[];
}

export function LogSection({ httpLogs }: LogSectionProps) {
  return (
    <section>
      <h2>④ システムログ</h2>
      <div style={{ maxHeight: "200px", overflowY: "auto", fontSize: "0.85rem" }}>
        {httpLogs.length === 0 ? (
          <p style={{ color: "var(--text-secondary)" }}>ログはありません</p>
        ) : (
          <ul style={{ fontFamily: "monospace" }}>
            {httpLogs.map((l, i) => (
              <li key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", color: l.includes("→") ? "var(--accent-primary)" : "var(--text-primary)" }}>
                {l}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

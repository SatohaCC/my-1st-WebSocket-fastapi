import {JwtDisplay} from "./JwtDisplay";

interface JwtSectionProps {
  token: string;
  payload: any;
}

export function JwtSection({ token, payload }: JwtSectionProps) {
  const badgeStyle = (bgColor: string, textColor: string) => ({
    background: bgColor,
    color: textColor,
    padding: "0 4px",
    borderRadius: "3px",
    fontSize: "0.9em",
    fontWeight: "bold",
  });

  return (
    <section>
      <h2>② JWT デコード詳細</h2>
      <p style={{ color: "var(--text-secondary)", marginBottom: "1rem", fontSize: "0.9rem" }}>
        JWT は{" "}
        <span style={badgeStyle("#fecaca", "#7f1d1d")}>ヘッダー</span>
        {" . "}
        <span style={badgeStyle("#bbf7d0", "#064e3b")}>ペイロード</span>
        {" . "}
        <span style={badgeStyle("#e0e7ff", "#1e3a8a")}>署名</span>
        {" の3パート構成です。"}
      </p>
      <JwtDisplay token={token} />
      <h3 style={{ marginTop: "1rem", fontSize: "1rem" }}>Payload (Base64 Decoded)</h3>
      <pre>{JSON.stringify(payload, null, 2)}</pre>
    </section>
  );
}

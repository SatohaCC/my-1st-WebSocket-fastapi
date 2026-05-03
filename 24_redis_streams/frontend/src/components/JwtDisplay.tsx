export function JwtDisplay({ token }: { token: string }) {
  const [h, p, s] = token.split(".");

  // コントラスト比を確保するためのスタイル定義
  const partStyle = (bgColor: string, textColor: string) => ({
    background: bgColor,
    color: textColor,
    padding: "0.1rem 0.3rem",
    borderRadius: "0.25rem",
    fontWeight: "600",
  });

  return (
    <pre style={{ wordBreak: "break-all", whiteSpace: "pre-wrap", lineHeight: "1.8" }}>
      <span style={partStyle("#fecaca", "#7f1d1d")}>{h}</span>
      {" . "}
      <span style={partStyle("#bbf7d0", "#064e3b")}>{p}</span>
      {" . "}
      <span style={partStyle("#e0e7ff", "#1e3a8a")}>{s}</span>
    </pre>
  );
}

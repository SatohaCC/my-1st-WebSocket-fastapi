export function decodeJwtPayload(token: string): object | null {
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const obj = JSON.parse(atob(base64));
    if (typeof obj.exp === "number") {
      obj.exp_readable = new Date(obj.exp * 1000).toLocaleString();
    }
    return obj;
  } catch {
    return null;
  }
}

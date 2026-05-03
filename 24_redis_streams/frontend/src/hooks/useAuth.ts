import { useState } from "react";
import { loginApi, fetchMeApi } from "../lib/api";
import { decodeJwtPayload } from "../lib/jwt";

interface UseAuthProps {
  onLog?: (message: string) => void;
}

export function useAuth({ onLog }: UseAuthProps = {}) {
  const [username, setUsername] = useState("alice");
  const [password, setPassword] = useState("password1");
  const [token, setToken] = useState<string | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [meResult, setMeResult] = useState<string | null>(null);

  const addLog = (msg: string) => {
    if (onLog) onLog(msg);
  };

  const login = async () => {
    setLoginError(null);
    addLog(`POST /token  { username: "${username}" }`);
    
    const { res, data } = await loginApi(username, password);
    
    if (!res.ok) {
      const msg = (data as { detail: string }).detail;
      setLoginError(msg);
      setToken(null);
      addLog(`  → ${res.status} ${msg}`);
      return;
    }
    
    const accessToken = (data as { access_token: string }).access_token;
    setToken(accessToken);
    addLog("  → 200 OK");
  };

  const logout = (onLogout?: () => void) => {
    if (onLogout) onLogout();
    setToken(null);
    setPassword("");
    setMeResult(null);
    addLog("Logout");
  };

  const fetchMe = async (withToken: boolean) => {
    const t = withToken ? token : null;
    
    if (withToken && token) {
      addLog(`GET /me  Authorization: Bearer ${token.slice(0, 24)}...`);
    } else {
      addLog("GET /me  （Authorization ヘッダーなし）");
    }
    
    const { res, data } = await fetchMeApi(t);
    setMeResult(`${res.status}\n${JSON.stringify(data, null, 2)}`);
    addLog(`  → ${res.status}  ${JSON.stringify(data)}`);
  };

  const payload = token ? decodeJwtPayload(token) : null;

  return {
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
  };
}

export type ServerMessage =
  | { type: "message"; username: string; text: string; id?: number }
  | { type: "join"; username: string }
  | { type: "leave"; username: string }
  | { type: "error"; text: string }
  | { type: "ping" };

export type WsStatus = "disconnected" | "connected" | "reconnecting";

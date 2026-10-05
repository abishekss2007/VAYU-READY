"use client";
import * as React from "react";
import { api, clearToken, getToken, wsUrl } from "./api";
import type { Role } from "./nav";

export type Me = { email: string; name: string; role: Role; squadron_code: string | null; read_only: boolean; notice_acknowledged: boolean; session_minutes: number };
type Toast = { id: number; text: string; kind: "ok" | "error" };
type Ctx = {
  me: Me | null; setMe: (m: Me | null) => void; logout: () => void;
  notify: (text: string, kind?: "ok" | "error") => void; toasts: Toast[];
  tick: number;            // increases whenever the server says data changed: pages reload on it
  live: boolean;           // WebSocket connected
  classification: string;
};
const SessionContext = React.createContext<Ctx>(null as any);
export const useSession = () => React.useContext(SessionContext);

/** Runs an action, shows the server's message, and reports failure in plain English. */
export function useAction() {
  const { notify } = useSession();
  const [busy, setBusy] = React.useState<string | null>(null);
  const run = async (key: string, fn: () => Promise<any>, after?: (r: any) => void) => {
    setBusy(key);
    try {
      const r = await fn();
      if (r?.message) notify(r.message + (r.fleet_health_score !== undefined ? ` Fleet Health Score: ${r.fleet_health_score}.` : ""));
      after?.(r);
      return r;
    } catch (e: any) {
      notify(e.message, "error");
    } finally {
      setBusy(null);
    }
  };
  return { busy, run };
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = React.useState<Me | null>(null);
  const [toasts, setToasts] = React.useState<Toast[]>([]);
  const [tick, setTick] = React.useState(0);
  const [live, setLive] = React.useState(false);
  const [classification, setClassification] = React.useState("DEMO DATA – UNCLASSIFIED");

  const notify = React.useCallback((text: string, kind: "ok" | "error" = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t.slice(-2), { id, text, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "error" ? 9000 : 6000);
  }, []);

  const logout = React.useCallback(() => {
    clearToken();
    setMe(null);
    location.href = "/login";
  }, []);

  React.useEffect(() => {
    api("/config/public").then((c) => setClassification(c.classification)).catch(() => {});
  }, [tick]);

  // Live updates: the server pushes "refresh" when a twin changes and "sensor" for the MQTT feed.
  React.useEffect(() => {
    if (!me) return;
    let ws: WebSocket | null = null;
    let stop = false;
    let ping: any, retry: any;
    const connect = () => {
      if (stop || !getToken()) return;
      ws = new WebSocket(wsUrl());
      ws.onopen = () => { setLive(true); ping = setInterval(() => ws?.readyState === 1 && ws.send("ping"), 20000); };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.type === "refresh") setTick((t) => t + 1);
        if (msg.type === "sensor") window.dispatchEvent(new CustomEvent("vayu-sensor", { detail: msg }));
      };
      ws.onclose = () => { setLive(false); clearInterval(ping); if (!stop) retry = setTimeout(connect, 5000); };
    };
    connect();
    return () => { stop = true; clearInterval(ping); clearTimeout(retry); ws?.close(); };
  }, [me]);

  return (
    <SessionContext.Provider value={{ me, setMe, logout, notify, toasts, tick, live, classification }}>
      {children}
    </SessionContext.Provider>
  );
}

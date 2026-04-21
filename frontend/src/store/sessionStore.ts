import { create } from "zustand";
import type { SessionDetail } from "../types/session";

interface SessionStore {
  session: SessionDetail | null;
  setSession: (s: SessionDetail) => void;
  clearSession: () => void;
}

export const useSessionStore = create<SessionStore>((set) => ({
  session: null,
  setSession: (s) => set({ session: s }),
  clearSession: () => set({ session: null }),
}));

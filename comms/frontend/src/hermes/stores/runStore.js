import { create } from 'zustand'

export const useHermesRunStore = create((set) => ({
  activeRun: null,
  events: [],
  setActiveRun: (run) => set({ activeRun: run }),
  addEvent: (event) => set((state) => ({ events: [...state.events, event] })),
  clearEvents: () => set({ events: [] }),
}))

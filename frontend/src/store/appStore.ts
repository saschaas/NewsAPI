import { create } from 'zustand';

interface Notification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  message: string;
  timestamp: Date;
}

interface AppState {
  // WebSocket
  wsConnected: boolean;
  setWsConnected: (connected: boolean) => void;

  // Notifications
  notifications: Notification[];
  addNotification: (type: Notification['type'], message: string) => void;
  removeNotification: (id: string) => void;

  // UI State
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;

  // Global pause
  globalPause: boolean;
  setGlobalPause: (paused: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // WebSocket
  wsConnected: false,
  setWsConnected: (connected) => set({ wsConnected: connected }),

  // Notifications
  notifications: [],
  addNotification: (type, message) =>
    set((state) => ({
      notifications: [
        ...state.notifications,
        {
          id: Math.random().toString(36).substring(7),
          type,
          message,
          timestamp: new Date(),
        },
      ],
    })),
  removeNotification: (id) =>
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
    })),

  // UI State
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),

  // Global pause
  globalPause: false,
  setGlobalPause: (paused) => set({ globalPause: paused }),
}));

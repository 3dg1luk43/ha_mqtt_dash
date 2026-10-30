import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// The panel (device id) the in-HA editor loads from / deploys to.
export const useHaStore = create(persist(
  (set) => ({
    deviceId: '',
    setDeviceId: (id) => set({ deviceId: id }),
  }),
  { name: 'mqttdash-editor-panel' }
));

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const useEntityStore = create(
  persist(
    (set) => ({
      entities: [], // array of entity ID strings

      addEntity: (id) => {
        const clean = id.trim();
        if (!clean) return;
        set((s) => ({ entities: [...new Set([...s.entities, clean])] }));
      },

      removeEntity: (id) => set((s) => ({ entities: s.entities.filter((e) => e !== id) })),

      // Bulk add — accepts newline / comma separated text
      bulkAdd: (text) => set((s) => {
        const incoming = text.split(/[\n,]+/).map((t) => t.trim()).filter(Boolean);
        return { entities: [...new Set([...s.entities, ...incoming])] };
      }),

      clearAll: () => set({ entities: [] }),
    }),
    { name: 'mqttdash-entities-v1' }
  )
);

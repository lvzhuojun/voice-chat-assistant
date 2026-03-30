/**
 * 音色状态 Store（Zustand）
 */

import { create } from 'zustand'
import type { VoiceModel } from '@/types'

interface VoiceState {
  voices: VoiceModel[]
  currentVoice: VoiceModel | null
  isLoading: boolean
  setVoices: (voices: VoiceModel[]) => void
  setCurrentVoice: (voice: VoiceModel | null) => void
  addVoice: (voice: VoiceModel) => void
  removeVoice: (id: number) => void
  setLoading: (loading: boolean) => void
}

export const useVoiceStore = create<VoiceState>((set) => ({
  voices: [],
  currentVoice: null,
  isLoading: false,

  setVoices: (voices) => set({ voices }),
  setCurrentVoice: (voice) => set({ currentVoice: voice }),
  addVoice: (voice) =>
    set((state) => ({ voices: [voice, ...state.voices] })),
  removeVoice: (id) =>
    set((state) => ({
      voices: state.voices.filter((v) => v.id !== id),
      currentVoice:
        state.currentVoice?.id === id ? null : state.currentVoice,
    })),
  setLoading: (loading) => set({ isLoading: loading }),
}))

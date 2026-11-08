export interface Preferences { theme: string; textSize: number; reducedMotion: boolean; developer: boolean; mode: string; engine: string; profile: string }
export const defaults: Preferences = { theme: 'system', textSize: 100, reducedMotion: false, developer: false, mode: 'easy', engine: 'auto', profile: 'digital' };
export function loadPreferences(): Preferences { try { return { ...defaults, ...JSON.parse(localStorage.getItem('preferences') || '{}') }; } catch { return { ...defaults }; } }
export function savePreferences(value: Preferences): void { localStorage.setItem('preferences', JSON.stringify(value)); }

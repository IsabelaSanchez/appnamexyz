import { env } from '$env/dynamic/public';
export const apiBase = env.PUBLIC_API_URL || '';
export const diagnostics: { method: string; path: string; status: number; duration: number }[] = [];
export function resource(path: string): string { return `${apiBase}${path}`; }
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const start = performance.now();
  const response = await fetch(resource(`/api/v1${path}`), { ...options, headers: options.body instanceof FormData ? options.headers : { 'Content-Type': 'application/json', ...options.headers }, signal: AbortSignal.timeout(30000) });
  diagnostics.unshift({ method: options.method || 'GET', path, status: response.status, duration: Math.round(performance.now() - start) });
  diagnostics.splice(40);
  const body = await response.text();
  let data: unknown;
  if (body.trim()) {
    try {
      data = JSON.parse(body) as typeof data;
    } catch {
      if (!response.ok) throw new Error(`Request failed (${response.status}) for ${path}.`);
      throw new Error(`The server returned an invalid JSON response for ${path} (HTTP ${response.status}).`);
    }
  }
  if (!response.ok) {
    const errorMessage = (data as { error?: { message?: string } } | undefined)?.error?.message;
    throw new Error(errorMessage || `Request failed (${response.status}) for ${path}.`);
  }
  if (!body.trim() && response.status !== 204 && response.status !== 205) {
    throw new Error(`The server returned an empty response for ${path} (HTTP ${response.status}).`);
  }
  return data as T;
}
export interface Geometry { type: string; coordinates: number[][]; parts: number[][][] }
export interface Element { id: string; category: string; label: string; description: string; visible: boolean; confidence: number; geometry: Geometry; provenance: string }
export interface Representation { project_id: string; description: string; map_type: string; elements: Element[]; warnings: string[]; processing_metadata: Record<string, unknown>; modifications: string[] }
export interface Project { id: string; revision: number; latest_revision: number; source: { filename: string; width: number; height: number }; config: Config }
export interface Config { engine: string; language: string; map_type: string; include: string[]; simplification: number; density: string; preprocess: boolean; output: { profile: string; page_width_mm: number; page_height_mm: number; line_width: number; label_size: number; symbol_size: number; minimum_spacing_mm: number; legend: boolean; texture: string; contrast: string } }
export interface Job { id: string; status: string; stage: string; progress: number; message?: string; error?: string; clarification?: boolean }
export interface Status { enabled: boolean; ai_available: boolean; active_jobs: number; session_hours: number; max_upload_mb: number }
export interface Branding { name: string; tagline: string; description: string; themeColor: string; logo: string; favicon: string; publicUrl: string }
export interface Engine { id: string; name: string; available: boolean; description: string }

const PROFILE_KEY = 'campus-sathi-profile';

/**
 * A small browser-local identity keeps this minor-project demo useful without
 * introducing accounts. The same ID is sent with every owner-specific request.
 */
export function getBrowserProfileId(): string {
  if (typeof window === 'undefined') return 'campus-sathi-student';
  const existing = window.localStorage.getItem(PROFILE_KEY);
  if (existing) return existing;
  const id = `student-${window.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`}`;
  window.localStorage.setItem(PROFILE_KEY, id);
  return id;
}

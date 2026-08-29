export type Item = {
  id: string;
  name: string;
  added_at: string;
  added_by?: string | null;
  quantity?: number | null;
  unit?: string | null;
  source?: string | null;
  notes?: string | null;
  category?: string | null;
  location?: string | null;
  photo_url?: string | null;
  consumed_at?: string | null;
  consumed_by?: string | null;
  /** Set only on the single-item route, which shows deleted items to anyone
   *  who knows the ID (i.e. is holding the printed label). */
  deleted_at?: string | null;
  deleted_by?: string | null;
};

export type ItemIn = {
  name: string;
  quantity?: number;
  unit?: string;
  source?: string;
  notes?: string;
  category?: string;
  location?: string;
  added_by?: string;
};

// The name is only used for "added by" / "consumed by" attribution — it is
// not a credential. The API has no auth at all.
const USER_STORAGE = 'frz.user';

export function getUser(): string { return localStorage.getItem(USER_STORAGE) ?? ''; }
export function setUser(u: string) { localStorage.setItem(USER_STORAGE, u); }

async function req(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has('Content-Type') && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  const r = await fetch(path, { ...init, headers });
  if (!r.ok) throw new Error(`${r.status}: ${(await r.text()).slice(0, 200)}`);
  return r;
}

export async function listItems(
  opts: { q?: string; consumed?: boolean; category?: string; stale_days?: number } = {},
): Promise<Item[]> {
  const p = new URLSearchParams();
  if (opts.q) p.set('q', opts.q);
  if (opts.consumed) p.set('consumed', '1');
  if (opts.category) p.set('category', opts.category);
  if (opts.stale_days) p.set('stale_days', String(opts.stale_days));
  const r = await req('/api/items?' + p.toString());
  return r.json();
}

export async function uploadPhoto(id: string, file: File): Promise<{ photo_url: string }> {
  const form = new FormData();
  form.append('file', file);
  const r = await req(`/api/items/${encodeURIComponent(id)}/photo`, { method: 'POST', body: form });
  return r.json();
}

export async function getItem(id: string): Promise<Item> {
  const r = await req(`/api/items/${encodeURIComponent(id)}`);
  return r.json();
}

export async function createItem(body: ItemIn): Promise<Item> {
  const r = await req('/api/items', { method: 'POST', body: JSON.stringify(body) });
  return r.json();
}

export async function patchItem(id: string, body: Partial<ItemIn>): Promise<Item> {
  const r = await req(`/api/items/${encodeURIComponent(id)}`, {
    method: 'PATCH', body: JSON.stringify(body),
  });
  return r.json();
}

export async function consumeItem(id: string, by?: string): Promise<Item> {
  const p = by ? `?by=${encodeURIComponent(by)}` : '';
  const r = await req(`/api/items/${encodeURIComponent(id)}/consume${p}`, { method: 'POST' });
  return r.json();
}

export async function unconsumeItem(id: string): Promise<Item> {
  const r = await req(`/api/items/${encodeURIComponent(id)}/unconsume`, { method: 'POST' });
  return r.json();
}

/** Soft delete — the row stays in the DB and the item stays reachable by ID,
 *  so scanning its label still works. It just leaves every list. */
export async function deleteItem(id: string, by?: string): Promise<void> {
  const p = by ? `?by=${encodeURIComponent(by)}` : '';
  await req(`/api/items/${encodeURIComponent(id)}${p}`, { method: 'DELETE' });
}

export async function undeleteItem(id: string): Promise<Item> {
  const r = await req(`/api/items/${encodeURIComponent(id)}/undelete`, { method: 'POST' });
  return r.json();
}

export async function deletePhoto(id: string): Promise<void> {
  await req(`/api/items/${encodeURIComponent(id)}/photo`, { method: 'DELETE' });
}

export async function enqueuePrint(id: string, by?: string): Promise<void> {
  const p = by ? `?by=${encodeURIComponent(by)}` : '';
  await req(`/api/items/${encodeURIComponent(id)}/print${p}`, { method: 'POST' });
}

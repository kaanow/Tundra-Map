import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  consumeItem, deleteItem, deletePhoto, enqueuePrint, getItem, patchItem,
  unconsumeItem, undeleteItem, uploadPhoto, type Item,
} from '../api';
import { CATEGORIES, LOCATIONS } from '../options';
import PhotoPicker from '../PhotoPicker';

/** A field you can change in place. Saves when you leave it or pick a
 *  suggestion, since things get moved around the freezer far more often than
 *  they get renamed. */
function EditableField({
  label, value, options, listId, onSave,
}: {
  label: string;
  value: string;
  options: string[];
  listId: string;
  onSave: (v: string) => Promise<void>;
}) {
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);

  // Re-sync if the item is reloaded or changed elsewhere.
  useEffect(() => { setDraft(value); }, [value]);

  async function commit() {
    const next = draft.trim();
    if (next === value.trim()) return;
    setSaving(true);
    try {
      await onSave(next);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ flex: '1 1 140px', minWidth: 0 }}>
      <label style={{ opacity: saving ? 0.5 : 1 }}>
        {label}{saving && ' — saving…'}
      </label>
      <input
        value={draft}
        list={listId}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); }}
      />
      <datalist id={listId}>
        {options.map((o) => <option key={o} value={o} />)}
      </datalist>
    </div>
  );
}

export default function ItemDetail() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const [item, setItem] = useState<Item | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => { if (id) getItem(id).then(setItem).catch((e) => setErr(String(e))); }, [id]);

  function flash(m: string) { setToast(m); setTimeout(() => setToast(null), 2000); }

  async function onConsume() {
    if (!item) return;
    if (!confirm(`Mark "${item.name}" as consumed?`)) return;
    setItem(await consumeItem(item.id));
    flash('Consumed');
  }
  async function onUnconsume() {
    if (!item) return;
    setItem(await unconsumeItem(item.id));
    flash('Back in the freezer');
  }
  async function onPrint() {
    if (!item) return;
    await enqueuePrint(item.id);
    flash('Print queued');
  }
  async function onDelete() {
    if (!item) return;
    if (!confirm(`Delete "${item.name}"? It leaves the list, but scanning its label still finds it.`)) return;
    await deleteItem(item.id);
    nav('/', { replace: true });
  }
  async function onUndelete() {
    if (!item) return;
    setItem(await undeleteItem(item.id));
    flash('Restored');
  }
  async function onPhoto(f: File | null) {
    if (!item || !f) return;
    const { photo_url } = await uploadPhoto(item.id, f);
    setItem({ ...item, photo_url });
    flash('Photo updated');
  }
  async function onPhotoRemove() {
    if (!item) return;
    if (!confirm('Remove this photo? The file is deleted for good.')) return;
    await deletePhoto(item.id);
    setItem({ ...item, photo_url: null });
    flash('Photo removed');
  }
  async function saveField(field: 'category' | 'location', value: string) {
    if (!item) return;
    try {
      setItem(await patchItem(item.id, { [field]: value || null }));
      flash(value ? `${field} updated` : `${field} cleared`);
    } catch (e) {
      setErr(String(e));
    }
  }

  if (err) return <div className="err">{err}</div>;
  if (!item) return <div className="empty">Loading…</div>;

  const deleted = !!item.deleted_at;

  return (
    <div className="detail">
      {deleted && (
        <div className="err" style={{ marginBottom: 16 }}>
          <strong>This item was deleted</strong>
          <div style={{ marginTop: 4, fontWeight: 400 }}>
            {new Date(item.deleted_at!).toLocaleDateString()}
            {' — '}it is hidden from the list, but you found it by its label.
          </div>
          <div style={{ marginTop: 12 }}>
            <button onClick={onUndelete}>Restore to the list</button>
          </div>
        </div>
      )}

      <h2>{item.name}</h2>
      <div className="date">Added {new Date(item.added_at).toLocaleDateString()}</div>

      {deleted && item.photo_url && (
        <img src={item.photo_url} alt=""
             style={{ width: '100%', maxHeight: 320, objectFit: 'cover', borderRadius: 12, margin: '8px 0 16px' }} />
      )}

      {!deleted && (
        <div style={{ display: 'flex', gap: 12, margin: '16px 0 4px' }}>
          <EditableField label="Category" value={item.category ?? ''} options={CATEGORIES}
                         listId="cats" onSave={(v) => saveField('category', v)} />
          <EditableField label="Location" value={item.location ?? ''} options={LOCATIONS}
                         listId="locs" onSave={(v) => saveField('location', v)} />
        </div>
      )}

      <dl className="kv">
        {item.quantity != null && (<><dt>Quantity</dt><dd>{item.quantity}{item.unit ? ` ${item.unit}` : ''}</dd></>)}
        {deleted && item.category && (<><dt>Category</dt><dd>{item.category}</dd></>)}
        {deleted && item.location && (<><dt>Location</dt><dd>{item.location}</dd></>)}
        {item.source   && (<><dt>Source</dt>  <dd>{item.source}</dd></>)}
        {item.notes    && (<><dt>Notes</dt>   <dd style={{ whiteSpace: 'pre-wrap' }}>{item.notes}</dd></>)}
        {item.consumed_at && (
          <><dt>Consumed</dt><dd>{new Date(item.consumed_at).toLocaleDateString()}</dd></>
        )}
      </dl>

      {!deleted && (
        <>
          <label>Photo</label>
          <PhotoPicker onPick={onPhoto} currentUrl={item.photo_url} onRemove={onPhotoRemove} />

          <div className="actions" style={{ marginTop: 20 }}>
            {item.consumed_at
              ? <button className="ghost" onClick={onUnconsume}>Undo consume</button>
              : <button className="ok" onClick={onConsume}>Mark consumed</button>}
            <button className="ghost" onClick={onPrint}>Print label again</button>
            <button className="danger" onClick={onDelete}>Delete</button>
          </div>
        </>
      )}

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

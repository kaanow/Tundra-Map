import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { consumeItem, enqueuePrint, getItem, getUser, unconsumeItem, uploadPhoto, type Item } from '../api';

export default function ItemDetail() {
  const { id } = useParams<{ id: string }>();
  const [item, setItem] = useState<Item | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => { if (id) getItem(id).then(setItem).catch((e) => setErr(String(e))); }, [id]);

  function flash(m: string) { setToast(m); setTimeout(() => setToast(null), 2000); }

  async function onConsume() {
    if (!item) return;
    if (!confirm(`Mark "${item.name}" as consumed?`)) return;
    setItem(await consumeItem(item.id, getUser() || undefined));
    flash('Consumed');
  }
  async function onUnconsume() {
    if (!item) return;
    setItem(await unconsumeItem(item.id));
    flash('Back in the freezer');
  }
  async function onPrint() {
    if (!item) return;
    await enqueuePrint(item.id, getUser() || undefined);
    flash('Print queued');
  }
  async function onPhoto(f: File | null) {
    if (!item || !f) return;
    const { photo_url } = await uploadPhoto(item.id, f);
    setItem({ ...item, photo_url });
    flash('Photo updated');
  }

  if (err) return <div className="err">{err}</div>;
  if (!item) return <div className="empty">Loading…</div>;

  return (
    <div className="detail">
      <h2>{item.name}</h2>
      <div className="date">
        Added {new Date(item.added_at).toLocaleDateString()}
        {item.added_by && <> by {item.added_by}</>}
      </div>

      {item.photo_url && (
        <img src={item.photo_url} alt=""
             style={{ width: '100%', maxHeight: 320, objectFit: 'cover', borderRadius: 12, margin: '8px 0 16px' }} />
      )}

      <dl className="kv">
        {item.quantity != null && (<><dt>Quantity</dt><dd>{item.quantity}{item.unit ? ` ${item.unit}` : ''}</dd></>)}
        {item.category && (<><dt>Category</dt><dd>{item.category}</dd></>)}
        {item.location && (<><dt>Location</dt><dd>{item.location}</dd></>)}
        {item.source   && (<><dt>Source</dt>  <dd>{item.source}</dd></>)}
        {item.notes    && (<><dt>Notes</dt>   <dd style={{ whiteSpace: 'pre-wrap' }}>{item.notes}</dd></>)}
        {item.consumed_at && (
          <><dt>Consumed</dt>
            <dd>{new Date(item.consumed_at).toLocaleDateString()}
              {item.consumed_by && <> by {item.consumed_by}</>}</dd></>
        )}
      </dl>

      <div className="actions">
        {item.consumed_at
          ? <button className="ghost" onClick={onUnconsume}>Undo consume</button>
          : <button className="ok" onClick={onConsume}>Mark consumed</button>}
        <button className="ghost" onClick={onPrint}>Print label again</button>
        <label className="ghost" style={{ textAlign: 'center', cursor: 'pointer',
                                          padding: '12px 14px', borderRadius: 8,
                                          border: '1px solid var(--line)', background: 'transparent' }}>
          {item.photo_url ? 'Replace photo' : 'Add photo'}
          <input type="file" accept="image/*" capture="environment" hidden
                 onChange={(e) => onPhoto(e.target.files?.[0] ?? null)} />
        </label>
      </div>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

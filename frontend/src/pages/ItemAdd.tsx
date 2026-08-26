import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createItem, enqueuePrint, getUser } from '../api';

export default function ItemAdd() {
  const nav = useNavigate();
  const [name, setName] = useState('');
  const [quantity, setQuantity] = useState('');
  const [unit, setUnit] = useState('');
  const [category, setCategory] = useState('');
  const [location, setLocation] = useState('');
  const [source, setSource] = useState('');
  const [notes, setNotes] = useState('');
  const [printLabel, setPrintLabel] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const item = await createItem({
        name: name.trim(),
        quantity: quantity ? Number(quantity) : undefined,
        unit: unit || undefined,
        category: category || undefined,
        location: location || undefined,
        source: source || undefined,
        notes: notes || undefined,
        added_by: getUser() || undefined,
      });
      if (printLabel) await enqueuePrint(item.id, getUser() || undefined);
      nav('/', { replace: true });
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      {err && <div className="err">{err}</div>}
      <label>Name *</label>
      <input autoFocus required value={name} onChange={(e) => setName(e.target.value)} placeholder="Beef stew" />

      <div className="row">
        <div>
          <label>Quantity</label>
          <input type="number" step="any" inputMode="decimal"
                 value={quantity} onChange={(e) => setQuantity(e.target.value)} />
        </div>
        <div>
          <label>Unit</label>
          <input value={unit} onChange={(e) => setUnit(e.target.value)} placeholder="portions" />
        </div>
      </div>

      <div className="row">
        <div>
          <label>Category</label>
          <input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="meat" list="cats" />
          <datalist id="cats">
            <option value="meat" /><option value="fish" /><option value="veg" />
            <option value="prepared" /><option value="stock" /><option value="bread" />
            <option value="fruit" /><option value="dairy" />
          </datalist>
        </div>
        <div>
          <label>Location</label>
          <input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="top drawer" />
        </div>
      </div>

      <label>Source</label>
      <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="Costco 2026-08" />

      <label>Notes</label>
      <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} />

      <label style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 16, color: 'var(--fg)' }}>
        <input type="checkbox" style={{ width: 'auto' }}
               checked={printLabel} onChange={(e) => setPrintLabel(e.target.checked)} />
        Print label
      </label>

      <div className="actions">
        <button disabled={busy || !name.trim()}>{busy ? 'Saving…' : 'Add'}</button>
        <button type="button" className="ghost" onClick={() => nav(-1)}>Cancel</button>
      </div>
    </form>
  );
}

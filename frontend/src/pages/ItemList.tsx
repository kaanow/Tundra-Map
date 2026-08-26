import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { listItems, type Item } from '../api';

function daysAgo(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 86400000;
  if (diff < 1) return 'today';
  if (diff < 2) return 'yesterday';
  const d = Math.floor(diff);
  if (d < 30) return `${d}d ago`;
  const m = Math.floor(d / 30);
  return `${m}mo ago`;
}

export default function ItemList() {
  const [items, setItems] = useState<Item[]>([]);
  const [q, setQ] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [showConsumed, setShowConsumed] = useState(false);
  const nav = useNavigate();

  useEffect(() => {
    const t = setTimeout(() => {
      listItems({ q, consumed: showConsumed })
        .then(setItems)
        .catch((e) => setErr(String(e)));
    }, 100);
    return () => clearTimeout(t);
  }, [q, showConsumed]);

  return (
    <div>
      <div className="search">
        <input
          placeholder="Search…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      <div style={{ marginBottom: 8 }}>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--muted)' }}>
          <input type="checkbox" style={{ width: 'auto' }}
                 checked={showConsumed} onChange={(e) => setShowConsumed(e.target.checked)} />
          Include consumed
        </label>
      </div>
      {err && <div className="err">{err}</div>}
      {items.length === 0 && !err && <div className="empty">Nothing here yet.</div>}
      {items.map((it) => (
        <Link className="card" key={it.id} to={`/i/${it.id}`}>
          <div className="name">
            {it.name}
            {it.consumed_at && <span className="pill" style={{ marginLeft: 8 }}>consumed</span>}
          </div>
          <div className="meta">
            {daysAgo(it.added_at)}
            {it.category && <> · <span>{it.category}</span></>}
            {it.location && <> · <span>{it.location}</span></>}
            {it.quantity != null && <> · <span>{it.quantity}{it.unit ? ` ${it.unit}` : ''}</span></>}
          </div>
        </Link>
      ))}
      <button className="fab" onClick={() => nav('/add')} aria-label="Add">+</button>
    </div>
  );
}

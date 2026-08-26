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

type Filter = 'all' | 'stale90' | 'stale180';

export default function ItemList() {
  const [items, setItems] = useState<Item[]>([]);
  const [q, setQ] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [showConsumed, setShowConsumed] = useState(false);
  const [filter, setFilter] = useState<Filter>('all');
  const nav = useNavigate();

  useEffect(() => {
    const t = setTimeout(() => {
      const stale_days = filter === 'stale90' ? 90 : filter === 'stale180' ? 180 : undefined;
      listItems({ q, consumed: showConsumed, stale_days })
        .then(setItems)
        .catch((e) => setErr(String(e)));
    }, 100);
    return () => clearTimeout(t);
  }, [q, showConsumed, filter]);

  return (
    <div>
      <div className="search">
        <input
          placeholder="Search…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      <div style={{ marginBottom: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        <button className={filter === 'all' ? '' : 'ghost'}
                onClick={() => setFilter('all')}
                style={{ padding: '6px 12px', fontSize: 13 }}>All</button>
        <button className={filter === 'stale90' ? '' : 'ghost'}
                onClick={() => setFilter('stale90')}
                style={{ padding: '6px 12px', fontSize: 13 }}>Stale 90d+</button>
        <button className={filter === 'stale180' ? '' : 'ghost'}
                onClick={() => setFilter('stale180')}
                style={{ padding: '6px 12px', fontSize: 13 }}>Stale 180d+</button>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--muted)', marginLeft: 'auto' }}>
          <input type="checkbox" style={{ width: 'auto' }}
                 checked={showConsumed} onChange={(e) => setShowConsumed(e.target.checked)} />
          Consumed
        </label>
      </div>
      {err && <div className="err">{err}</div>}
      {items.length === 0 && !err && <div className="empty">Nothing here yet.</div>}
      {items.map((it) => (
        <Link className="card" key={it.id} to={`/i/${it.id}`}
              style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          {it.photo_url ? (
            <img src={it.photo_url} alt=""
                 style={{ width: 56, height: 56, borderRadius: 8, objectFit: 'cover', flex: '0 0 auto' }} />
          ) : (
            <div style={{ width: 56, height: 56, borderRadius: 8, background: 'var(--panel-2)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          color: 'var(--muted)', fontSize: 20, flex: '0 0 auto' }}>
              {(it.category?.[0] ?? it.name[0] ?? '?').toUpperCase()}
            </div>
          )}
          <div style={{ flex: 1, minWidth: 0 }}>
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
          </div>
        </Link>
      ))}
      <button className="fab" onClick={() => nav('/add')} aria-label="Add">+</button>
    </div>
  );
}

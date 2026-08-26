import { useEffect, useState } from 'react';
import { Routes, Route, useSearchParams, useNavigate, Link } from 'react-router-dom';
import { getKey, setKey, getUser, setUser } from './api';
import ItemList from './pages/ItemList';
import ItemAdd from './pages/ItemAdd';
import ItemDetail from './pages/ItemDetail';

function KeyGate({ children }: { children: React.ReactNode }) {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const [ready, setReady] = useState(false);
  const [input, setInput] = useState('');
  const [userInput, setUserInput] = useState(getUser());

  useEffect(() => {
    // Absorb ?k=... from URL (e.g., scanned QR) and strip it from the address bar.
    const fromUrl = params.get('k');
    if (fromUrl) {
      setKey(fromUrl);
      params.delete('k');
      nav({ search: params.toString() }, { replace: true });
    }
    setReady(true);
  }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  if (!ready) return null;
  if (!getKey()) {
    return (
      <div className="app">
        <div className="top"><h1>Tundra-Map</h1></div>
        <p className="empty">Enter the shared key to unlock.</p>
        <label>Shared key</label>
        <input autoFocus value={input} onChange={(e) => setInput(e.target.value)} />
        <label>Your name (for attribution)</label>
        <input value={userInput} onChange={(e) => setUserInput(e.target.value)} placeholder="Kaan" />
        <div style={{ height: 16 }} />
        <button onClick={() => { setKey(input.trim()); setUser(userInput.trim()); location.reload(); }}>
          Unlock
        </button>
      </div>
    );
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <KeyGate>
      <div className="app">
        <div className="top">
          <h1><Link to="/" style={{ color: 'inherit' }}>Tundra-Map</Link></h1>
          <div className="spacer" />
          <Link to="/settings" className="pill">{getUser() || 'set name'}</Link>
        </div>
        <Routes>
          <Route path="/" element={<ItemList />} />
          <Route path="/add" element={<ItemAdd />} />
          <Route path="/i/:id" element={<ItemDetail />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </div>
    </KeyGate>
  );
}

function Settings() {
  const [user, setLocalUser] = useState(getUser());
  const nav = useNavigate();
  return (
    <div>
      <label>Your name (used for &quot;added by&quot; on new items)</label>
      <input value={user} onChange={(e) => setLocalUser(e.target.value)} />
      <div style={{ height: 12 }} />
      <button onClick={() => { setUser(user.trim()); nav(-1); }}>Save</button>
      <div style={{ height: 24 }} />
      <button className="ghost" onClick={() => { localStorage.clear(); location.href = '/'; }}>
        Sign out (clear key)
      </button>
    </div>
  );
}

import { useState } from 'react';
import { Routes, Route, useNavigate, Link } from 'react-router-dom';
import { getUser, setUser } from './api';
import ItemList from './pages/ItemList';
import ItemAdd from './pages/ItemAdd';
import ItemDetail from './pages/ItemDetail';

export default function App() {
  return (
    <div className="app">
      <div className="top">
        <h1><Link to="/" style={{ color: 'inherit' }}>What is in the freezer?</Link></h1>
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
    </div>
  );
}

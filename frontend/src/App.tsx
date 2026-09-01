import { Routes, Route, Link } from 'react-router-dom';
import ItemList from './pages/ItemList';
import ItemAdd from './pages/ItemAdd';
import ItemDetail from './pages/ItemDetail';

export default function App() {
  return (
    <div className="app">
      <div className="top">
        <h1><Link to="/" style={{ color: 'inherit' }}>What is in the freezer?</Link></h1>
      </div>
      <Routes>
        <Route path="/" element={<ItemList />} />
        <Route path="/add" element={<ItemAdd />} />
        <Route path="/i/:id" element={<ItemDetail />} />
      </Routes>
    </div>
  );
}

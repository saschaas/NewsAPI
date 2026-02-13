import { Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout/Layout';
import { Dashboard } from './pages/Dashboard';
import { Sources } from './pages/Sources';
import { Stocks } from './pages/Stocks';
import { Settings } from './pages/Settings';
import { Config } from './pages/Config';
import { Help } from './pages/Help';

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/sources" element={<Sources />} />
        <Route path="/stocks" element={<Stocks />} />
        <Route path="/stocks/:ticker" element={<Stocks />} />
        <Route path="/database" element={<Settings />} />
        <Route path="/config" element={<Config />} />
        <Route path="/help" element={<Help />} />
      </Routes>
    </Layout>
  );
}

export default App;

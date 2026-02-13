import { NavLink } from 'react-router-dom';
import { Home, Rss, TrendingUp, Database, Settings, HelpCircle } from 'lucide-react';
import { useAppStore } from '@/store/appStore';
import { cn } from '@/utils/cn';

const navItems = [
  { to: '/', icon: Home, label: 'Dashboard' },
  { to: '/sources', icon: Rss, label: 'Sources' },
  { to: '/stocks', icon: TrendingUp, label: 'Stocks' },
  { to: '/database', icon: Database, label: 'Database' },
  { to: '/config', icon: Settings, label: 'Config' },
  { to: '/help', icon: HelpCircle, label: 'Help' },
];

export function Sidebar() {
  const { sidebarOpen } = useAppStore();

  if (!sidebarOpen) return null;

  return (
    <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-4 py-3 rounded-lg transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-gray-700 hover:bg-gray-100'
              )
            }
          >
            <item.icon className="w-5 h-5" />
            <span className="font-medium">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-gray-200">
        <div className="text-xs text-gray-500 space-y-1">
          <p>Stock News API v1.0.0</p>
          <p>Local-first AI News</p>
        </div>
      </div>
    </aside>
  );
}

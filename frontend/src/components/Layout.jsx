import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Menu } from 'lucide-react';
import Sidebar from './Sidebar';

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_#dbeafe_0%,_#f8fafc_45%,_#eef2ff_100%)]">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200/70 bg-white/70 px-4 py-3 backdrop-blur md:hidden">
        <h1 className="text-base font-black tracking-wide text-slate-900">SPORTPREDICT</h1>
        <button
          type="button"
          onClick={() => setSidebarOpen(true)}
          className="rounded-lg border border-slate-200 bg-white p-2 text-slate-700"
          aria-label="Відкрити меню"
        >
          <Menu className="h-5 w-5" />
        </button>
      </header>

      <main className="p-4 md:ml-64 md:p-8">
        <Outlet />
      </main>
    </div>
  );
}

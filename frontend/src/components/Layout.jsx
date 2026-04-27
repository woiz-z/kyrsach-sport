import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Menu } from 'lucide-react';
import Sidebar from './Sidebar';
import AnimatedBackground from './AnimatedBackground';

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-[#060E1C]">
      <AnimatedBackground />
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <header className="relative z-30 sticky top-0 flex items-center justify-between border-b border-white/[0.06] bg-[#060E1C]/80 px-4 py-3 backdrop-blur md:hidden">
        <h1 className="text-base font-black tracking-widest gradient-text">SPORTPREDICT</h1>
        <button
          type="button"
          onClick={() => setSidebarOpen(true)}
          className="rounded-lg border border-white/10 bg-white/5 p-2 text-slate-300 hover:bg-white/10 transition-colors"
          aria-label="Відкрити меню"
        >
          <Menu className="h-5 w-5" />
        </button>
      </header>

      <main className="relative z-10 p-4 md:ml-64 md:p-8">
        <Outlet />
      </main>
    </div>
  );
}


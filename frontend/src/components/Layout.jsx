import { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { Menu } from 'lucide-react';
import Sidebar from './Sidebar';
import AnimatedBackground from './AnimatedBackground';
import VideoBackground from './VideoBackground';
import { useSportMode } from '../context/SportModeContext';

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { theme } = useSportMode();

  // Inject sport theme as CSS variables onto :root so index.css utilities pick them up
  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty('--sport-accent', theme.accent);
    root.style.setProperty('--sport-accent2', theme.accent2);
    root.style.setProperty('--sport-glow', theme.glow);
    root.style.setProperty('--sport-gradient', theme.gradient);
    root.style.setProperty('--sport-gradient-text', theme.gradientText);
    root.style.setProperty('--sport-card-border', theme.cardBorder);
    root.style.setProperty('--sport-input-focus', theme.inputFocus);
    root.style.setProperty('--sport-input-focus-shadow', theme.inputFocusShadow);
    root.style.setProperty('--sport-scrollbar', theme.scrollbar);
    root.style.setProperty('--sport-radial1', theme.bodyRadial1);
    root.style.setProperty('--sport-radial2', theme.bodyRadial2);
    root.style.setProperty('--sport-radial3', theme.bodyRadial3);
    document.body.style.background = theme.bg;
  }, [theme]);

  return (
    <div className="min-h-screen" style={{ background: theme.bg }}>
      <VideoBackground />
      <AnimatedBackground />
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <header className="relative z-30 sticky top-0 flex items-center justify-between border-b px-4 py-3 backdrop-blur md:hidden"
        style={{ background: `${theme.bg}cc`, borderColor: `${theme.accent}18` }}>
        <h1 className="brand-gradient-text text-base font-black tracking-widest">SPORTPREDICT</h1>
        <button
          type="button"
          onClick={() => setSidebarOpen(true)}
          className="rounded-lg p-2 transition-colors"
          style={{ border: `1px solid ${theme.accent}28`, background: `${theme.accent}0a`, color: '#cbd5e1' }}
          aria-label="Відкрити меню"
        >
          <Menu className="h-5 w-5" />
        </button>
      </header>

      <main className="relative z-10 p-4 md:ml-64 md:p-8 min-h-screen"
        style={{
          background: `linear-gradient(180deg, transparent 0%, rgba(4,10,22,0.35) 100%)`,
        }}>
        <Outlet />
      </main>
    </div>
  );
}


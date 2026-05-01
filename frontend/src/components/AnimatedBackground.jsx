import { useEffect, useRef } from 'react';
import { useSportMode } from '../context/SportModeContext';

const PARTICLE_COUNT = 70;
const MAX_DIST = 130;
const SPEED = 0.28;

function rand(min, max) {
  return Math.random() * (max - min) + min;
}

function initParticles(w, h, colors) {
  return Array.from({ length: PARTICLE_COUNT }, () => {
    const color = colors[Math.floor(Math.random() * colors.length)];
    return {
      x: rand(0, w),
      y: rand(0, h),
      vx: rand(-SPEED, SPEED),
      vy: rand(-SPEED, SPEED),
      r: rand(1.2, 3.2),
      color,
      pulse: rand(0, Math.PI * 2),
      pulseSpeed: rand(0.008, 0.02),
      bright: Math.random() < 0.18,
    };
  });
}

export default function AnimatedBackground() {
  const { theme } = useSportMode();
  const canvasRef = useRef(null);
  const stateRef = useRef({ particles: [], animId: null, w: 0, h: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const state = stateRef.current;
    const colors = theme?.particleColors || [[59, 130, 246], [8, 145, 178], [16, 185, 129]];

    const resize = () => {
      state.w = canvas.width = window.innerWidth;
      state.h = canvas.height = window.innerHeight;
      state.particles = initParticles(state.w, state.h, colors);
    };

    resize();
    window.addEventListener('resize', resize);

    const draw = () => {
      const { w, h, particles } = state;
      ctx.clearRect(0, 0, w, h);

      // update & draw particles
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.pulse += p.pulseSpeed;

        // bounce
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;

        // draw connections
        for (let j = i + 1; j < particles.length; j++) {
          const q = particles[j];
          const dx = p.x - q.x;
          const dy = p.y - q.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < MAX_DIST) {
            const alpha = (1 - dist / MAX_DIST) * 0.18;
            const [r, g, b] = p.color;
            ctx.strokeStyle = `rgba(${r},${g},${b},${alpha})`;
            ctx.lineWidth = 0.8;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(q.x, q.y);
            ctx.stroke();
          }
        }

        // draw particle
        const pulseScale = p.bright ? 1 + 0.35 * Math.sin(p.pulse) : 1;
        const radius = p.r * pulseScale;
        const baseAlpha = p.bright ? 0.75 + 0.25 * Math.sin(p.pulse) : 0.35;
        const [r, g, b] = p.color;

        if (p.bright) {
          // glow ring
          const grd = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, radius * 3.5);
          grd.addColorStop(0, `rgba(${r},${g},${b},0.25)`);
          grd.addColorStop(1, `rgba(${r},${g},${b},0)`);
          ctx.fillStyle = grd;
          ctx.beginPath();
          ctx.arc(p.x, p.y, radius * 3.5, 0, Math.PI * 2);
          ctx.fill();
        }

        ctx.fillStyle = `rgba(${r},${g},${b},${baseAlpha})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
        ctx.fill();
      }

      state.animId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(state.animId);
    };
  }, [theme]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none"
      style={{ zIndex: 1, opacity: 0.35 }}
    />
  );
}

/**
 * VideoBackground — спорт-специфічне відео на фоні через YouTube iframe.
 *
 * Відео ID верифіковані вручну (офіційні канали: Premier League, NBA, ATP Tour, NHL…).
 * Якщо відео недоступне або заблоковано — плавно відображається темний фон.
 *
 * Autoplay: використовуємо enablejsapi=1 + postMessage YT API щоб примусово
 * запустити відео одразу після завантаження гравця.
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useSportMode } from '../context/SportModeContext';

// ── Curated YouTube video IDs per sport (verified 2026-05) ─────────────────
const SPORT_VIDEOS = {
  football: [
    'wz1r_VJaJZw', // 1 HOUR Premier League BEST Goals Last 10 Years
    's0ZOd1ghabU', // 1 HOUR ICONIC Solo Moments Premier League
    'upukb0i4vi4', // 1 HOUR BEST Acrobatic Goals Premier League
    'aQds7_Drif0', // 1 HOUR Most Beautiful Team Goals
  ],
  basketball: [
    '4Dm3vXtrQpQ', // 1 HOUR NBA BEST Dunks Last 10 Years
    'FW4pK6hIbAk', // 1 HOUR BEST Dunks 2023-24 NBA Season
    '924jorx_zn4', // 1 HOUR BEST Dunks 2022-23 NBA Season
    'JMXT7HW4_N8', // NBA Top 100 Dunks Last 25 Years
  ],
  tennis: [
    'ne6hTv4SrvI', // TOP 50 ATP SHOTS RALLIES 2010s DECADE
    '0V0HQDwM22E', // Brutal Tennis Rallies BEST OF ATP
    'U7uhxZF7oQM', // TOP 100 SHOTS 2024 ATP SEASON
  ],
  hockey: [
    'kx7pSI7U5yM', // Filthiest Goals 2024-25 NHL Season
    'RSdyKRpJhhE', // Most Beautiful NHL Plays This Season
    'fvuwePX7AKQ', // Filthiest Goals 2023-24 NHL Season
  ],
  volleyball: [
    '_QbSPuTv-WA', // TOP 20 Volleyball Moments Shocked the World
    'PRXc9-Zw0aw', // TOP 20 Unreal Volleyball Spikes Shocked the World
    'WDMbQp4M6aI', // 40 Most Powerful Spikes World Championship 2025
  ],
  esports: [
    'iDBPLD3a8us', // Top 17 Plays VALORANT Champions Tour 2024 (VCT official)
    'hQyGZB5nS9A', // Top 25 Plays VALORANT Champions Tour 2025 (VCT official)
    'oNTfL3-2saw', // The BEST CS2 Moments of 2024 (ESLCS official)
    'crwcXwFUJy8', // TOP 50 BEST LOL ESPORTS MOMENTS OF 2024
    '5UktyVCfFUc', // 50 Iconic Valorant Moments in 2024
  ],
};

function pickRandom(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function pickStart() {
  return Math.floor(Math.random() * 75) + 15;
}

export default function VideoBackground() {
  const { activeSport, theme } = useSportMode();
  const prevSportRef = useRef(activeSport);
  const iframeRef = useRef(null);

  const [videoId, setVideoId] = useState(() => pickRandom(SPORT_VIDEOS[activeSport] || SPORT_VIDEOS.football));
  const [startTime, setStartTime] = useState(pickStart);
  const [visible, setVisible] = useState(false);
  const fadeTimer = useRef(null);
  // track whether YT player is ready
  const ytReadyRef = useRef(false);

  // ── Force play via postMessage (YT IFrame API) ──────────────────────────
  const forcePlay = useCallback(() => {
    const el = iframeRef.current;
    if (!el) return;
    // YT IFrame API command
    el.contentWindow?.postMessage(
      JSON.stringify({ event: 'command', func: 'playVideo', args: [] }),
      '*'
    );
    el.contentWindow?.postMessage(
      JSON.stringify({ event: 'command', func: 'mute', args: [] }),
      '*'
    );
    el.contentWindow?.postMessage(
      JSON.stringify({ event: 'command', func: 'setVolume', args: [0] }),
      '*'
    );
  }, []);

  // ── Listen for YT player ready / state change ──────────────────────────
  useEffect(() => {
    const handleMessage = (e) => {
      if (!e.data) return;
      try {
        const data = typeof e.data === 'string' ? JSON.parse(e.data) : e.data;
        // YT sends {event:'onReady'} or {event:'infoDelivery', info:{playerState:...}}
        if (data.event === 'onReady') {
          ytReadyRef.current = true;
          forcePlay();
          clearTimeout(fadeTimer.current);
          fadeTimer.current = setTimeout(() => setVisible(true), 400);
        }
        if (data.event === 'infoDelivery' && data.info?.playerState === -1) {
          // unstarted — player loaded but hasn't started, nudge it
          forcePlay();
        }
      } catch { /* non-YT message, ignore */ }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [forcePlay]);

  // ── On sport change → fade out, pick new video ─────────────────────────
  useEffect(() => {
    if (prevSportRef.current === activeSport) return;
    prevSportRef.current = activeSport;
    setVisible(false);
    ytReadyRef.current = false;
    clearTimeout(fadeTimer.current);
    const t = setTimeout(() => {
      const ids = SPORT_VIDEOS[activeSport] || SPORT_VIDEOS.football;
      setVideoId(pickRandom(ids));
      setStartTime(pickStart());
    }, 600);
    return () => clearTimeout(t);
  }, [activeSport]);

  // ── onLoad fallback: iframe HTML loaded, try forcePlay + fade in ────────
  const handleLoad = useCallback(() => {
    clearTimeout(fadeTimer.current);
    // Give YT player script 2s to initialise before fading in
    // (onReady will fire sooner and trigger fade if it works)
    fadeTimer.current = setTimeout(() => {
      forcePlay();
      setVisible(true);
    }, 2000);
  }, [forcePlay]);

  useEffect(() => () => clearTimeout(fadeTimer.current), []);

  // enablejsapi=1 enables postMessage API; origin is required for it to work
  const src = [
    `https://www.youtube.com/embed/${videoId}`,
    `?autoplay=1&mute=1&loop=1&playlist=${videoId}`,
    `&controls=0&showinfo=0&rel=0&modestbranding=1`,
    `&playsinline=1&start=${startTime}`,
    `&iv_load_policy=3&disablekb=1`,
    `&vq=hd1080`,
    `&enablejsapi=1&origin=${encodeURIComponent(window.location.origin)}`,
  ].join('');

  const bg = theme?.bg || '#000';

  return (
    <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none" aria-hidden="true">

      {/* ── Fallback solid background ───────────────────────────────── */}
      <div className="absolute inset-0 transition-colors duration-700" style={{ backgroundColor: bg }} />

      {/* ── YouTube iframe ─────────────────────────────────────────── */}
      <div className="absolute inset-0" style={{ overflow: 'hidden' }}>
        <iframe
          ref={iframeRef}
          key={videoId}
          src={src}
          title="sport-background-video"
          allow="autoplay; encrypted-media; picture-in-picture"
          onLoad={handleLoad}
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            width: 'max(177.78vh, 100vw)',
            height: 'max(56.25vw, 100vh)',
            transform: 'translate(-50%, -50%)',
            border: 'none',
            pointerEvents: 'none',
            opacity: visible ? 1 : 0,
            transition: 'opacity 1.8s ease',
          }}
        />
      </div>

      {/* ── Overlay (darkens video for readability while keeping cinematic feel) */}
      <div
        className="absolute inset-0"
        style={{
          background: `
            linear-gradient(
              to bottom,
              ${bg}f0 0%,
              ${bg}aa 15%,
              ${bg}77 40%,
              ${bg}77 60%,
              ${bg}aa 85%,
              ${bg}f0 100%
            )
          `,
          transition: 'background 0.8s ease',
        }}
      />

      {/* ── Vignette ─────────────────────────────────────────────────── */}
      <div
        className="absolute inset-0"
        style={{
          background: `radial-gradient(ellipse at center, transparent 25%, ${bg}66 65%, ${bg}cc 100%)`,
        }}
      />
    </div>
  );
}


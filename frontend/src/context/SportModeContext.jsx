import { createContext, useContext, useState, useEffect } from 'react';
import { SPORT_THEMES, SPORT_KEYS, resolveSportKey } from '../constants/sports';
import api from '../services/api';

const SportModeContext = createContext(null);

const DEFAULT_SPORT = 'football';

export function SportModeProvider({ children }) {
  const [activeSport, setActiveSport] = useState(
    () => localStorage.getItem('activeSport') || DEFAULT_SPORT
  );
  // Map sport key → DB sport id (loaded once from API)
  const [sportIdMap, setSportIdMap] = useState({});
  const [sportMapLoaded, setSportMapLoaded] = useState(false);

  useEffect(() => {
    api.get('/sports/').then(res => {
      const list = Array.isArray(res.data) ? res.data : [];
      const map = {};
      list.forEach(s => {
        const key = resolveSportKey(s.name);
        map[key] = s.id;
      });
      setSportIdMap(map);
    }).catch(() => {}).finally(() => {
      setSportMapLoaded(true);
    });
  }, []);

  const switchSport = (key) => {
    if (!SPORT_KEYS.includes(key)) return;
    setActiveSport(key);
    localStorage.setItem('activeSport', key);
  };

  const theme = SPORT_THEMES[activeSport] || SPORT_THEMES[DEFAULT_SPORT];
  const activeSportId = sportIdMap[activeSport] ?? null;

  return (
    <SportModeContext.Provider value={{ activeSport, theme, activeSportId, sportIdMap, sportMapLoaded, switchSport }}>
      {children}
    </SportModeContext.Provider>
  );
}

export const useSportMode = () => useContext(SportModeContext);

import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 20000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

api.fetchSports = async () => {
  const res = await api.get('/sports/');
  return Array.isArray(res.data) ? res.data : [];
};

api.fetchSeasons = async (sportId) => {
  const params = sportId ? { sport_id: sportId } : undefined;
  const res = await api.get('/sports/seasons', { params });
  return Array.isArray(res.data) ? res.data : [];
};

export default api;

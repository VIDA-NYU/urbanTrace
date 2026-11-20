// Base URL of the UrbanTrace backend. Set VITE_API_BASE_URL (in frontend/.env.local, or the
// environment of `vite build`) to point the interface at another server; the default is the
// local development backend.
export const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');

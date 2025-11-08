// Désactiver SSR pour cette page car elle dépend de fetch() vers le backend
// qui n'est accessible que côté client via le proxy Vite
export const ssr = false;

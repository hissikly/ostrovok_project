import React from 'react'

// Линейные иконки 20 px в духе иконок Островка (stroke, скруглённые концы)
const P = {
  pin: 'M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21zM12 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z',
  mountain: 'M3 19l6-10 4 6 3-4 5 8H3z',
  waves: 'M3 9c2 0 2-2 4.5-2S10 9 12 9s2-2 4.5-2S19 9 21 9M3 15c2 0 2-2 4.5-2s2.5 2 4.5 2 2-2 4.5-2 2.5 2 4.5 2',
  sunset: 'M4 18h16M7 14a5 5 0 0 1 10 0M12 4v3M5.6 7.6l1.8 1.8M18.4 7.6l-1.8 1.8M3 14h1.5M19.5 14H21',
  building: 'M5 21V5l7-2v18M12 8h7v13M8 8v.01M8 12v.01M8 16v.01M15.5 12v.01M15.5 16v.01M3 21h18',
  window: 'M5 4h14v16H5zM12 4v16M5 12h14',
  calendar: 'M4 6h16v14H4zM4 10h16M8 3v4M16 3v4',
  beach: 'M3 11a9 7 0 0 1 18 0zM12 4v17M7 21h10',
  sparkle: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.7 1.8 1.8.7-1.8.7L19 21l-.7-1.8-1.8-.7 1.8-.7z',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  x: 'M7 7l10 10M17 7L7 17',
  question: 'M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6v.6M12 17.5v.01',
  half: 'M5 12h14',
  cart: 'M3 4h2l2.4 11h10.2L20 7H6.2M9 20a1 1 0 1 0 0-.01M17 20a1 1 0 1 0 0-.01',
  card: 'M3 6h18v12H3zM3 10h18M7 15h3',
  cup: 'M5 8h11v5a5 5 0 0 1-5 5h-1a5 5 0 0 1-5-5zM16 9h2a2 2 0 0 1 0 4h-2M8 3v2M11 3v2',
  tree: 'M12 3l5 7h-3l4 6H6l4-6H7zM12 16v5',
  eye: 'M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12zM12 14.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z',
  star: 'M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z',
  dumbbell: 'M6 7v10M18 7v10M3 9.5v5M21 9.5v5M6 12h12',
  child: 'M12 7a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM12 9v6M8 11l4-2 4 2M10 21l2-6 2 6',
  pill: 'M10.5 20.5a5 5 0 0 1-7-7l6-6a5 5 0 0 1 7 7zM8.5 8.5l7 7',
  health: 'M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10zM12 9v5M9.5 11.5h5',
  moon: 'M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z',
  bus: 'M6 4h12a2 2 0 0 1 2 2v10H4V6a2 2 0 0 1 2-2zM4 11h16M7 19v-3M17 19v-3M8 14h.01M16 14h.01',
  car: 'M5 16l1.5-5h11l1.5 5M4 16h16v3H4zM7 19v1.5M17 19v1.5M7.5 11l1-3h7l1 3',
  paw: 'M8 9a1.5 2 0 1 0 0-.01M16 9a1.5 2 0 1 0 0-.01M5 13a1.4 1.8 0 1 0 0-.01M19 13a1.4 1.8 0 1 0 0-.01M12 13c-3 0-5 3-4 5s3 1 4 1 3 1 4-1-1-5-4-5z',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0',
}

export default function Icon({ name, size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={P[name]} />
    </svg>
  )
}

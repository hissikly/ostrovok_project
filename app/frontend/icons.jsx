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

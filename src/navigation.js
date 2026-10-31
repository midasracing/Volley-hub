import { Home, CalendarDays, Trophy, Heart } from 'lucide-react';

export const NAV = [
  { id: 'home', label: 'Główna', Icon: Home },
  { id: 'matches', label: 'Mecze', Icon: CalendarDays },
  { id: 'competitions', label: 'Rozgrywki', Icon: Trophy },
  { id: 'favorites', label: 'Ulubione', Icon: Heart }
];
export const ROUTES = NAV.map(item => item.id);

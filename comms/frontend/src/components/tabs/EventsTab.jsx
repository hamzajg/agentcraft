import React from 'react';
import { EventsBusPanel } from '../EventsBusPanel';

/* ─────────────────────────────────────────────────────────
   Events Tab Component
   Features:
   • Event stream visualization
   • Real-time updates
   • Event filtering
   ───────────────────────────────────────────────────────── */

export function EventsTab() {
  return <EventsBusPanel events={[]} />;
}

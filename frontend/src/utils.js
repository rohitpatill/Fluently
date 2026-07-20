export function relativeTime(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  const now = new Date();
  const diffMs = now - d;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'now';
  if (diffMin < 60) return `${diffMin}m`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d`;
  return d.toLocaleDateString([], { month: 'short', day: '2-digit' });
}

export function formatClockTime(dateStr) {
  const d = dateStr ? new Date(dateStr) : new Date();
  if (isNaN(d.getTime())) return '';
  return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

export function formatThreadTime(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return '';
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  const diffDay = Math.floor((now - d) / 86400000);
  if (diffDay < 7) return d.toLocaleDateString([], { weekday: 'short' });
  return d.toLocaleDateString([], { month: 'short', day: '2-digit' });
}

export function nowClockLabel() {
  const d = new Date();
  return d.toLocaleDateString([], { weekday: 'short' }) + ', ' + d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

export function parsePersonaName(raw) {
  if (!raw) return null;
  // persona.md header line: "Name: Jack" (no trailing period)
  const m = raw.match(/^Name:\s*(.+)$/m);
  const name = m ? m[1].trim() : '';
  return name || null;
}

export function parsePersonaRelation(raw) {
  if (!raw) return null;
  const m = raw.match(/^Relation to user:\s*(.+)$/m);
  const rel = m ? m[1].trim() : '';
  return rel || null;
}

export function parseIdentityName(raw) {
  if (!raw) return null;
  // identity.md entry line: "[i001] ... | Name: Rohit."
  const m = raw.match(/Name:\s*([^.\n|]+)/);
  const name = m ? m[1].trim() : '';
  return name || null;
}

export function initial(name) {
  if (!name) return '?';
  return name.trim().charAt(0).toUpperCase();
}

export function scoreColor(score) {
  if (score >= 80) return 'accent';
  if (score < 40) return 'slip';
  return 'normal';
}


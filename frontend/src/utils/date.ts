/**
 * Format a date string or Date object for display in German 24h format.
 * Uses the Europe/Berlin timezone.
 */

const DE_DATETIME: Intl.DateTimeFormatOptions = {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone: 'Europe/Berlin',
};

const DE_DATE: Intl.DateTimeFormatOptions = {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  timeZone: 'Europe/Berlin',
};

const DE_SHORT: Intl.DateTimeFormatOptions = {
  day: '2-digit',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone: 'Europe/Berlin',
};

const DE_FULL: Intl.DateTimeFormatOptions = {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone: 'Europe/Berlin',
};

/** "20.03.2026, 14:58" */
export function formatDateTime(value: string | Date): string {
  return new Date(value).toLocaleString('de-DE', DE_DATETIME);
}

/** "20.03.2026" */
export function formatDate(value: string | Date): string {
  return new Date(value).toLocaleString('de-DE', DE_DATE);
}

/** "20. Mär., 14:58" */
export function formatShortDateTime(value: string | Date): string {
  return new Date(value).toLocaleString('de-DE', DE_SHORT);
}

/** "20. Mär. 2026, 14:58" */
export function formatFullDateTime(value: string | Date): string {
  return new Date(value).toLocaleString('de-DE', DE_FULL);
}

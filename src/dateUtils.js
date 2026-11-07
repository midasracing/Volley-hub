// Shared date formats and local-noon anchor for the calendar and match lists.
export const DATE_FORMAT = new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'long', year: 'numeric' });
export const NOW = () => { const today = new Date(); today.setHours(12, 0, 0, 0); return today; };
export const MONTH_FORMAT = new Intl.DateTimeFormat('pl-PL', { month: 'long' });

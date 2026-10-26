/**
 * TanStack Query keys — one place so realtime events and mutations invalidate the right data.
 * Convention: the first element is the domain; invalidating a prefix (e.g. ["inquiries"]) refreshes all lists
 * and details of that domain. Add new domains here, not inline in components.
 */
export const qk = {
  me: ["me"] as const,
  counters: ["me", "counters"] as const,
  favoriteIds: ["me", "favorites", "ids"] as const,
  favorites: (type?: string) => ["me", "favorites", "list", type ?? "all"] as const,
  notifications: ["notifications"] as const,
  conversations: ["conversations"] as const,
  conversation: (id: string) => ["conversations", id] as const,
  messages: (conversationId: string) => ["conversations", conversationId, "messages"] as const,
  inquiries: ["inquiries"] as const,
  inquiry: (id: string) => ["inquiries", id] as const,
  bookings: ["bookings"] as const,
  booking: (id: string) => ["bookings", id] as const,
  media: (id: string) => ["media", id] as const,
  myOrganizations: ["me", "organizations"] as const,
  myInvites: ["me", "invites"] as const,
};

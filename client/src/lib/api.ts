/**
 * API configuration for DevLabo client.
 *
 * In development: Uses Vite proxy (requests to /connect/* and /agent/* are proxied)
 * In production: Uses VITE_API_URL environment variable
 */

declare const __API_URL__: string

// Get API base URL from build-time env variable
const API_URL = __API_URL__ || ''

/**
 * Build full URL for API endpoints.
 * In dev mode with proxy, returns relative path.
 * In production, prepends the API_URL.
 */
export function apiUrl(path: string): string {
  if (API_URL) {
    return `${API_URL}${path}`
  }
  return path
}

/**
 * Build URL for sandbox preview iframe.
 */
export function previewUrl(userId: string, projectId: string, module: string): string {
  return apiUrl(`/connect/${userId}/${projectId}/${module}/`)
}

/**
 * Build URL for agent chat endpoint.
 */
export function agentChatUrl(): string {
  return apiUrl('/agent/chat')
}

/**
 * Build URL for sandbox file API.
 */
export function sandboxFilesUrl(userId: string, projectId: string, module: string): string {
  return apiUrl(`/connect/${userId}/${projectId}/${module}/api/files`)
}

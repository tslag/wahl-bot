/**
 * Frontend Authentication Service with Refresh Token Support
 *
 * This shows how to handle tokens on the client side.
 */

import { API_BASE_URL } from '../util';

class AuthService {
  constructor() {
    this.accessToken = null;
    // refresh token must be HttpOnly cookie set by the server
    this.tokenRefreshTimeout = null;
    this._refreshPromise = null; // single-flight refresh lock
  }

  /**
   * LOGIN FLOW
   * 1. Send credentials to /auth/token
   * 2. Store both tokens
   * 3. Schedule automatic refresh before access token expires
   */
  async login(username, password) {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    // Use credentials: 'include' so server-set HttpOnly refresh cookie is stored
    const response = await fetch(`${API_BASE_URL}/auth/token`, {
      method: 'POST',
      body: formData,
      credentials: 'include',
    });

    if (!response.ok) {
      throw new Error('Login failed');
    }

    const data = await response.json();

    // Access token is returned in JSON; refresh token is stored in HttpOnly cookie
    this.accessToken = data.access_token;

    // Schedule token refresh. Use server-provided expiry where possible.
    const expiresIn = data.expires_in || 30 * 60; // seconds, default 30 minutes
    const refreshBefore = Math.max(60, Math.floor(expiresIn * 0.2)); // refresh at 20% before expiry, min 60s
    const refreshIn = (expiresIn - refreshBefore) * 1000;
    this.scheduleTokenRefresh(refreshIn);

    return data;
  }

  /**
   * AUTOMATIC TOKEN REFRESH
   * Refresh access token before it expires to avoid API request failures
   */
  scheduleTokenRefresh(delay) {
    // Clear existing timeout
    if (this.tokenRefreshTimeout) {
      clearTimeout(this.tokenRefreshTimeout);
    }

    // Schedule refresh
    this.tokenRefreshTimeout = setTimeout(() => {
      // fire-and-forget; refreshAccessToken handles failure
      this.refreshAccessToken().catch((error) => {
        console.error('Scheduled token refresh failed:', error);
        this.logout();
        window.location.href = '/login';
      });
    }, delay);
  }

  /**
   * REFRESH TOKEN FLOW
   * 1. Send refresh token to /auth/refresh
   * 2. Get new access token (and possibly new refresh token)
   * 3. Update stored tokens
   * 4. Schedule next refresh
   */
  async refreshAccessToken() {
    // Single-flight refresh: if another refresh is in progress, wait for it
    if (this._refreshPromise) {
      return this._refreshPromise;
    }

    this._refreshPromise = (async () => {
      // Server reads refresh token from HttpOnly cookie; include credentials
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      });

      if (!response.ok) {
        this._refreshPromise = null;
        throw new Error('Token refresh failed');
      }

      const data = await response.json();

      this.accessToken = data.access_token;

      // Schedule next refresh using `expires_in` if present
      const expiresIn = data.expires_in || 30 * 60;
      const refreshBefore = Math.max(60, Math.floor(expiresIn * 0.2));
      const refreshIn = (expiresIn - refreshBefore) * 1000;
      this.scheduleTokenRefresh(refreshIn);

      this._refreshPromise = null;
      return data;
    })();

    return this._refreshPromise;
  }

  /**
   * API REQUEST WITH AUTOMATIC TOKEN HANDLING
   * 1. Add access token to request
   * 2. If request fails with 401, try to refresh token and retry
   */
  async apiRequest(url, options = {}) {
    // Add access token to request
    const headers = {
      ...options.headers,
    };

    if (this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }

    // Always include credentials so cookie-based refresh is sent

    // Resolve full URL via API_BASE_URL (so Vite proxy can forward it)
    let fullUrl = url;
    if (!/^https?:\/\//i.test(url)) {
      if (url.startsWith(API_BASE_URL)) {
        fullUrl = url;
      } else if (url.startsWith('/')) {
        fullUrl = `${API_BASE_URL}${url}`;
      } else {
        fullUrl = `${API_BASE_URL}/${url}`;
      }
    }

    let response = await fetch(fullUrl, {
      ...options,
      headers,
      credentials: 'include',
    });

    // If 401 Unauthorized, try to refresh token and retry
    if (response.status === 401) {
      try {
        await this.refreshAccessToken();

        // Retry request with new token
        if (this.accessToken) headers['Authorization'] = `Bearer ${this.accessToken}`;
        // reuse resolution logic
        let retryUrl = url;
        if (!/^https?:\/\//i.test(url)) {
          if (url.startsWith(API_BASE_URL)) retryUrl = url;
          else if (url.startsWith('/')) retryUrl = `${API_BASE_URL}${url}`;
          else retryUrl = `${API_BASE_URL}/${url}`;
        }
        response = await fetch(retryUrl, {
          ...options,
          headers,
          credentials: 'include',
        });
      } catch (error) {
        // Refresh failed, logout locally and navigate to login
        this.logout();
        window.location.href = '/login';
        throw error;
      }
    }

    return response;
  }

  /**
   * LOGOUT FLOW
   * 1. Revoke refresh token on server
   * 2. Clear local tokens
   * 3. Cancel scheduled refresh
   */
  async logout() {
    try {
      // Ask server to revoke refresh cookie/session. Server should clear cookie.
      await fetch(`${API_BASE_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      });
    } catch (error) {
      console.error('Logout request failed:', error);
    }

    // Clear local state
    this.accessToken = null;

    if (this.tokenRefreshTimeout) {
      clearTimeout(this.tokenRefreshTimeout);
      this.tokenRefreshTimeout = null;
    }
  }

  /**
   * LOGOUT FROM ALL DEVICES
   * Revokes all user's refresh tokens
   */
  async logoutAllDevices() {
    await this.apiRequest('/auth/logout-all', { method: 'POST' });

    // Then logout locally
    await this.logout();
  }

  /**
   * GET ACTIVE SESSIONS
   * See where user is logged in
   */
  async getActiveSessions() {
    const response = await this.apiRequest('/auth/users/me/sessions');
    return response.json();
  }
}

// Export a single instance for the app to use
const authService = new AuthService();
export default authService;

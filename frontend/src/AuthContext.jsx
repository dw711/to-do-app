/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState } from 'react';
import { apiJson, clearToken, getToken, setToken } from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setAuthToken] = useState(getToken());
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(token));

  useEffect(() => {
    if (!token) {
      return;
    }
    apiJson('/api/auth/me')
      .then(({ user: currentUser }) => setUser(currentUser))
      .catch(() => {
        clearToken();
        setAuthToken(null);
      })
      .finally(() => setLoading(false));
  }, [token]);

  async function authenticate(path, credentials) {
    const result = await apiJson(path, { method: 'POST', body: JSON.stringify(credentials) });
    setToken(result.token);
    setAuthToken(result.token);
    setUser(result.user);
  }

  function logout() {
    clearToken();
    setAuthToken(null);
    setUser(null);
    window.location.replace('/login');
  }

  return (
    <AuthContext.Provider value={{
      token, user, loading,
      login: credentials => authenticate('/api/auth/login', credentials),
      signup: credentials => authenticate('/api/auth/register', credentials),
      logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

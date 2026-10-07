import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';

export default function LoginPage() {
  const { token, login } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  if (token) return <Navigate to="/board" replace />;

  async function submit(event) {
    event.preventDefault();
    setError('');
    const form = new FormData(event.currentTarget);
    try {
      await login({ email: form.get('email'), password: form.get('password') });
      navigate('/board', { replace: true });
    } catch (err) {
      setError(err.message === 'Incorrect email or password' ? err.message : 'Unable to log in');
    }
  }

  return (
    <main className="auth-page">
      <form className="auth-form" onSubmit={submit}>
        <h1>Log in</h1>
        <input name="email" type="email" placeholder="Email" required autoComplete="email" />
        <input name="password" type="password" placeholder="Password" required autoComplete="current-password" />
        {error && <div className="auth-error">{error}</div>}
        <button type="submit">Log in</button>
        <p>Need an account? <Link to="/signup">Sign up</Link></p>
      </form>
    </main>
  );
}

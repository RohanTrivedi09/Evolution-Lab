import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';

import { Lab } from './lab/Lab';
import { Story } from './story/Story';
import './styles/tokens.css';
import './styles/base.css';
import './styles/glass.css';
import './styles/lab.css';
import './styles/story.css';

type View = 'lab' | 'story';
type Theme = 'light' | 'dark';

const readTheme = (): Theme => {
  const stored = localStorage.getItem('evolution-lab-theme');
  if (stored === 'light' || stored === 'dark') return stored;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};

const readHash = (): View =>
  window.location.hash.replace(/^#\/?/, '') === 'story' ? 'story' : 'lab';

function App() {
  const [view, setView] = useState<View>(readHash);
  const [theme, setTheme] = useState<Theme>(readTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('evolution-lab-theme', theme);
  }, [theme]);

  useEffect(() => {
    const sync = () => {
      setView(readHash());
      window.scrollTo({ top: 0 });
    };
    window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, []);

  const go = (next: View) => { window.location.hash = `#/${next}`; };

  return (
    <>
      <div className="ambient" aria-hidden="true" />
      <nav className="view-switch" aria-label="View">
        {(['lab', 'story'] as View[]).map(name => (
          <button key={name} type="button" onClick={() => go(name)}
                  className={view === name ? 'active' : ''}
                  aria-current={view === name ? 'page' : undefined}>
            {name === 'lab' ? 'Lab' : 'Story'}
          </button>
        ))}
        <button type="button" className="theme-toggle"
                onClick={() => setTheme(t => (t === 'dark' ? 'light' : 'dark'))}
                aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} appearance`}>
          {theme === 'dark' ? '☀' : '☾'}
        </button>
      </nav>
      {view === 'story' ? <Story onEnterLab={() => go('lab')} /> : <Lab />}
    </>
  );
}

createRoot(document.getElementById('root')!).render(<App />);

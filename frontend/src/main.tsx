import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';

import { Lab } from './lab/Lab';
import { Story } from './story/Story';
import './style.css';
import './styles/story.css';

type View = 'lab' | 'story';

const readHash = (): View =>
  window.location.hash.replace(/^#\/?/, '') === 'story' ? 'story' : 'lab';

function App() {
  const [view, setView] = useState<View>(readHash);

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
      <nav className="view-switch" aria-label="View">
        {(['lab', 'story'] as View[]).map(name => (
          <button key={name} type="button" onClick={() => go(name)}
                  className={view === name ? 'active' : ''}
                  aria-current={view === name ? 'page' : undefined}>
            {name === 'lab' ? 'Lab' : 'Story'}
          </button>
        ))}
      </nav>
      {view === 'story' ? <Story onEnterLab={() => go('lab')} /> : <Lab />}
    </>
  );
}

createRoot(document.getElementById('root')!).render(<App />);

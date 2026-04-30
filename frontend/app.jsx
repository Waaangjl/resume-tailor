/* Resume Tailor Wizard — Plan B aesthetic, one focus per page */

const { useState, useRef, useEffect, useMemo, Fragment } = React;

const STEPS = [
  { id: 'resume',  title: 'Resume',   sub: 'Where should we start from?' },
  { id: 'jd',      title: 'JD',       sub: 'Paste the job description.' },
  { id: 'profile', title: 'Profile',  sub: 'Tell us about yourself.' },
  { id: 'stories', title: 'Stories',  sub: 'Add a few experience stories.' },
  { id: 'voice',   title: 'Voice',    sub: 'Optional: a writing sample.' },
  { id: 'review',  title: 'Review',   sub: 'Looks good? Generate.' },
];

const SUGGESTED_TAGS = ['Quant', 'Research', 'ML', 'Backend', 'Frontend', 'Data', 'Leadership', 'Open-source'];

const wordCount = (s) => s.trim().split(/\s+/).filter(Boolean).length;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "step": 0,
  "showSkips": true
}/*EDITMODE-END*/;

const RESUME_VALID = {
  scratch:  d => !!d.template,
  file:     d => !!d.file,
  overleaf: d => !!d.latex.trim(),
  previous: () => true,
};

function _load(key, fallback) {
  try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; }
  catch { return fallback; }
}

const PERSIST_KEYS = ['rt:profile', 'rt:stories', 'rt:voice'];

function App() {
  const [tweaks, setTweak] = window.useTweaks(TWEAK_DEFAULTS);

  const [data, setData] = useState({
    resume: { mode: null, file: null, template: null, latex: '' },
    jd:     { mode: 'url', url: '', text: '', fetched: false, fetchState: 'idle' },
    profile: _load('rt:profile', { name: '', email: '', phone: '', location: '', linkedin: '', github: '', website: '' }),
    stories: _load('rt:stories', [{ id: 'STAR_1', tags: [], text: '' }]),
    voice:   _load('rt:voice',   { sample: '' }),
    model:  'sonnet',
  });
  const update = (key, patch) => setData(d => ({ ...d, [key]: { ...d[key], ...patch } }));

  useEffect(() => { localStorage.setItem('rt:profile', JSON.stringify(data.profile)); }, [data.profile]);
  useEffect(() => { localStorage.setItem('rt:stories', JSON.stringify(data.stories)); }, [data.stories]);
  useEffect(() => { localStorage.setItem('rt:voice',   JSON.stringify(data.voice));   }, [data.voice]);

  const clearMemory = () => {
    PERSIST_KEYS.forEach(k => { try { localStorage.removeItem(k); } catch {} });
    setData(d => ({
      ...d,
      profile: { name: '', email: '', phone: '', location: '', linkedin: '', github: '', website: '' },
      stories: [{ id: 'STAR_1', tags: [], text: '' }],
      voice:   { sample: '' },
    }));
  };

  const [phase, setPhase] = useState('wizard'); // wizard | generating | results
  const [progress, setProgress] = useState({ step: -1, label: '' });
  const [results, setResults] = useState(null);
  const [genError, setGenError] = useState(null);

  const stepIdx = Math.min(tweaks.step, STEPS.length - 1);
  const goto = (i) => setTweak('step', Math.max(0, Math.min(STEPS.length - 1, i)));
  const next = () => goto(stepIdx + 1);
  const back = () => goto(stepIdx - 1);

  const timersRef = useRef([]);
  const abortRef  = useRef(null);
  const clearTimers = () => { timersRef.current.forEach(clearTimeout); timersRef.current = []; };
  useEffect(() => clearTimers, []);

  const startGen = async () => {
    clearTimers();
    if (abortRef.current) abortRef.current.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setGenError(null);
    setPhase('generating');
    setProgress({ step: -1, label: 'Starting…' });

    const body = {
      resume:  { latex: data.resume.latex },
      jd:      { text: data.jd.text, url: data.jd.url },
      profile: data.profile,
      stories: data.stories.map(({ _draft, ...s }) => s),
      voice:   data.voice,
      model:   data.model,
    };

    try {
      const resp = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: ctrl.signal,
      });
      if (!resp.ok) throw new Error(`Server error ${resp.status}`);

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const chunks = buf.split('\n\n');
        buf = chunks.pop();
        for (const chunk of chunks) {
          if (!chunk.trim()) continue;
          let evt = 'message', dataStr = '';
          for (const line of chunk.split('\n')) {
            if (line.startsWith('event: ')) evt = line.slice(7).trim();
            if (line.startsWith('data: '))  dataStr = line.slice(6);
          }
          if (!dataStr) continue;
          const payload = JSON.parse(dataStr);
          if (evt === 'progress') {
            setProgress({ step: payload.step, label: payload.label });
          } else if (evt === 'done') {
            setResults({
              generatedAt: new Date(),
              tailoredTex: payload.tailored_tex,
              coverLetter: payload.cover_letter,
              diffHtml:    payload.diff_html,
              company:     payload.company,
              role:        payload.role,
            });
            setProgress({ step: 5, label: 'Done' });
            timersRef.current.push(setTimeout(() => setPhase('results'), 700));
          } else if (evt === 'error') {
            setGenError(payload.message);
            setPhase('wizard');
          }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        setGenError(e.message || 'Generation failed. Is server.py running?');
        setPhase('wizard');
      }
    } finally {
      abortRef.current = null;
    }
  };

  const reset = () => {
    clearTimers();
    if (abortRef.current) { abortRef.current.abort(); abortRef.current = null; }
    setGenError(null);
    setPhase('wizard');
    setResults(null);
    goto(0);
  };

  const canContinue = useMemo(() => {
    const id = STEPS[stepIdx].id;
    if (id === 'resume')  return !!data.resume.mode && (RESUME_VALID[data.resume.mode]?.(data.resume) ?? false);
    if (id === 'jd')      return data.jd.mode === 'url' ? !!data.jd.url.trim() : !!data.jd.text.trim();
    if (id === 'profile') return !!data.profile.name.trim() && !!data.profile.email.trim();
    if (id === 'stories') return data.stories.some(s => s.text.trim().length > 20);
    return true;
  }, [stepIdx, data]);

  const hasMemory = useMemo(
    () => !!(data.profile.name || data.stories.some(s => s.text.trim()) || data.voice.sample),
    [data.profile.name, data.stories, data.voice.sample]
  );

  const ProgressHeader = () => (
    <Fragment>
      <div className="progress-rail"><div className="progress-fill" style={{ width: `${(stepIdx / (STEPS.length - 1)) * 100}%` }} /></div>
      <div className="topbar">
        <span className="brand"><span className="mark"><Icon name="logo" size={22}/></span>resume-tailor</span>
        <div className="steplist">
          {STEPS.map((s, i) => (
            <button key={s.id} className={`pip ${i < stepIdx ? 'done' : ''} ${i === stepIdx ? 'active' : ''}`} onClick={() => goto(i)}>
              <span className="dot"/>{String(i+1).padStart(2,'0')} {s.title}
            </button>
          ))}
        </div>
        <div style={{display:'flex', gap:14, alignItems:'center'}}>
          {hasMemory && (
            <button
              className="skip"
              title="Profile, stories, and voice sample are saved in this browser. Click to forget."
              onClick={() => { if (confirm('Forget saved profile, stories, and voice sample?')) clearMemory(); }}
            >clear memory</button>
          )}
          <button className="skip" onClick={reset}>start over</button>
        </div>
      </div>
    </Fragment>
  );

  if (phase === 'generating') return <GenerationScreen progress={progress} model={data.model} />;
  if (phase === 'results')    return <ResultsScreen results={results} reset={reset} data={data} />;

  return (
    <Fragment>
      <ProgressHeader />
      {genError && (
        <div className="error-banner">
          {genError}
          <button onClick={() => setGenError(null)}>×</button>
        </div>
      )}
      <main className="stage">
        {STEPS[stepIdx].id === 'resume'  && <StepResume  data={data} update={update}/>}
        {STEPS[stepIdx].id === 'jd'      && <StepJD      data={data} update={update}/>}
        {STEPS[stepIdx].id === 'profile' && <StepProfile data={data} update={update} showSkips={tweaks.showSkips}/>}
        {STEPS[stepIdx].id === 'stories' && <StepStories data={data} setData={setData}/>}
        {STEPS[stepIdx].id === 'voice'   && <StepVoice   data={data} update={update} setData={setData}/>}
        {STEPS[stepIdx].id === 'review'  && <StepReview  data={data} setData={setData} goto={goto}/>}
      </main>
      <footer className="footer-nav">
        <button className="btn ghost" onClick={back} disabled={stepIdx === 0}>
          <Icon name="arrow-left" size={14}/>Back
        </button>
        <span className="meta-row" style={{margin:0,fontSize:11}}>
          step {String(stepIdx+1).padStart(2,'0')} / {String(STEPS.length).padStart(2,'0')}
        </span>
        {stepIdx < STEPS.length - 1 ? (
          <button className="btn primary lg" onClick={next} disabled={!canContinue}>
            Continue<Icon name="arrow-right" size={14}/>
          </button>
        ) : (
          <button className="btn primary lg" onClick={startGen}>
            <Icon name="sparkles" size={14}/>Generate
          </button>
        )}
      </footer>
    </Fragment>
  );
}

function StepResume({ data, update }) {
  const fileRef = useRef();
  const [drag, setDrag] = useState(false);
  const mode = data.resume.mode;

  const choose = (m) => update('resume', { mode: m });

  const readFile = (f) => {
    if (!f) return;
    if (f.name.endsWith('.tex')) {
      const r = new FileReader();
      r.onload = ev => update('resume', { file: f.name, latex: ev.target.result });
      r.readAsText(f);
    } else {
      update('resume', { file: f.name });
    }
  };

  const TEMPLATES = [
    { id: 'classic',  name: 'Classic',  desc: 'Times-style, single column' },
    { id: 'modern',   name: 'Modern',   desc: 'Sans-serif, clear hierarchy' },
    { id: 'compact',  name: 'Compact',  desc: 'Two-column, dense' },
  ];

  if (!mode) {
    return (
      <div className="step">
        <div className="eyebrow">step 01 / 06 · resume</div>
        <h1 className="step-title">Where should we start from?</h1>
        <p className="step-subtitle">Pick one. You can change later.</p>
        <div className="choice-list">
          <button className="choice" onClick={() => choose('file')}>
            <span className="gly"><Icon name="file" size={20}/></span>
            <div className="body">
              <p className="title">Upload an existing resume</p>
              <p className="desc">Drop a .tex file — we'll extract structure.</p>
            </div>
            <Icon name="arrow-right" size={16} className="arrow"/>
          </button>
          <button className="choice" onClick={() => choose('overleaf')}>
            <span className="gly"><Icon name="overleaf" size={20}/></span>
            <div className="body">
              <p className="title">Paste from Overleaf</p>
              <p className="desc">Drop in your .tex source directly.</p>
            </div>
            <Icon name="arrow-right" size={16} className="arrow"/>
          </button>
          <button className="choice" onClick={() => choose('scratch')}>
            <span className="gly"><Icon name="spark" size={20}/></span>
            <div className="body">
              <p className="title">Start from a template</p>
              <p className="desc">Pick a clean LaTeX layout — we'll fill it in.</p>
            </div>
            <Icon name="arrow-right" size={16} className="arrow"/>
          </button>
          <button className="choice" onClick={() => choose('previous')}>
            <span className="gly"><Icon name="archive" size={20}/></span>
            <div className="body">
              <p className="title">Use a previous tailored resume</p>
              <p className="desc">Continue from your last session (if any).</p>
            </div>
            <Icon name="arrow-right" size={16} className="arrow"/>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="step">
      <div className="eyebrow">
        <button className="skip" onClick={() => choose(null)} style={{padding:'0',background:'none',color:'inherit',fontFamily:'inherit',fontSize:'inherit',letterSpacing:'inherit',textTransform:'inherit'}}>← change source</button>
      </div>

      {mode === 'file' && (
        <Fragment>
          <h1 className="step-title">Upload your resume</h1>
          <p className="step-subtitle">.tex file (LaTeX source). Drop it below.</p>
          <div
            className={`dropzone ${drag ? 'over' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); readFile(e.dataTransfer.files[0]); }}
            onClick={() => fileRef.current.click()}
            style={{ cursor: 'pointer' }}
          >
            <input type="file" ref={fileRef} hidden accept=".tex" onChange={(e) => readFile(e.target.files[0])}/>
            <Icon name="upload" size={28} style={{ color: 'var(--ink-3)' }}/>
            <p style={{margin:'12px 0 4px',fontSize:14,color:'var(--ink)'}}>Drop your .tex file here</p>
            <p style={{margin:0,fontSize:12,color:'var(--ink-3)'}}>or click to browse · tex only</p>
            {data.resume.file && <p className="filename">✓ {data.resume.file}</p>}
          </div>
        </Fragment>
      )}

      {mode === 'overleaf' && (
        <Fragment>
          <h1 className="step-title">Paste your LaTeX source</h1>
          <p className="step-subtitle">From Overleaf or any .tex file. We'll parse it.</p>
          <textarea
            className="text mono"
            rows="14"
            placeholder={'\\documentclass{article}\n\\begin{document}\n...\n\\end{document}'}
            value={data.resume.latex}
            onChange={(e) => update('resume', { latex: e.target.value })}
          />
          <div className="meta-row"><span>{data.resume.latex.length} chars</span><span>{data.resume.latex.split('\n').length} lines</span></div>
        </Fragment>
      )}

      {mode === 'scratch' && (
        <Fragment>
          <h1 className="step-title">Pick a template</h1>
          <p className="step-subtitle">All clean, single-page, ATS-friendly.</p>
          <div className="template-grid">
            {TEMPLATES.map(t => (
              <button key={t.id} className={`template-card ${data.resume.template === t.id ? 'selected' : ''}`} onClick={() => update('resume', { template: t.id })}>
                <div className="preview">{t.name}.tex</div>
                <div className="meta"><div className="t">{t.name}</div><div className="d">{t.desc}</div></div>
              </button>
            ))}
          </div>
        </Fragment>
      )}

      {mode === 'previous' && (
        <Fragment>
          <h1 className="step-title">Continue from last session</h1>
          <p className="step-subtitle">Your most recent tailored resume.</p>
          <div className="card">
            <div className="row">
              <Icon name="file-text" size={20} style={{color:'var(--ink-3)'}}/>
              <div>
                <div style={{fontSize:14,fontWeight:500}}>Anthropic_RA_2025-04-14.tex</div>
                <div style={{fontSize:12,color:'var(--ink-3)',fontFamily:'var(--mono)',marginTop:2}}>2 days ago · 12 inserts · 8 removals</div>
              </div>
              <span className="spacer"/>
              <button className="btn" onClick={() => update('resume', { file: 'Anthropic_RA_2025-04-14.tex' })}>Use this</button>
            </div>
          </div>
        </Fragment>
      )}
    </div>
  );
}

function StepJD({ data, update }) {
  const fetchUrl = async () => {
    update('jd', { fetchState: 'fetch' });
    try {
      const resp = await fetch('/api/fetch-jd', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: data.jd.url }),
      });
      const json = await resp.json();
      if (json.ok) {
        update('jd', { fetchState: 'ok', fetched: true, text: json.text });
      } else {
        update('jd', { fetchState: 'err', fetched: false });
      }
    } catch {
      update('jd', { fetchState: 'err', fetched: false });
    }
  };

  const tooShort = data.jd.mode === 'text' && data.jd.text.trim().length > 0 && data.jd.text.trim().length < 200;
  return (
    <div className="step">
      <div className="eyebrow">step 02 / 06 · job description</div>
      <h1 className="step-title">Paste the job description</h1>
      <p className="step-subtitle">A URL works if the page is publicly accessible (Workday JDs supported). Otherwise paste the full text.</p>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:16}}>
        <div className="pill-toggle">
          <button className={data.jd.mode==='url'?'active':''}  onClick={() => update('jd',{mode:'url'})}>URL</button>
          <button className={data.jd.mode==='text'?'active':''} onClick={() => update('jd',{mode:'text'})}>Paste text</button>
        </div>
      </div>
      {data.jd.mode === 'url' ? (
        <Fragment>
          <div className="row">
            <input className="text" placeholder="https://jobs.company.com/posting/..." value={data.jd.url} onChange={(e) => update('jd',{url:e.target.value, fetched:false, fetchState:'idle'})}/>
            <button className="btn" disabled={!data.jd.url.trim() || data.jd.fetchState==='fetch'} onClick={fetchUrl}>
              {data.jd.fetchState === 'fetch' ? 'Fetching…' : 'Fetch'}
            </button>
          </div>
          <div className="meta-row" style={{justifyContent:'flex-start'}}>
            <span><span className={`status-dot ${data.jd.fetchState}`}/>
              {data.jd.fetchState === 'idle' && 'idle — paste URL and hit Fetch, or just Continue to let the server fetch during generation'}
              {data.jd.fetchState === 'fetch' && 'fetching…'}
              {data.jd.fetchState === 'ok' && `fetched · ${(data.jd.text.length / 1024).toFixed(1)} kb`}
              {data.jd.fetchState === 'err' && 'failed — paste text instead'}
            </span>
          </div>
          {data.jd.fetched && (
            <div className="card" style={{marginTop:14}}>
              <div style={{fontSize:11,fontFamily:'var(--mono)',color:'var(--ink-3)',marginBottom:8,letterSpacing:'.08em',textTransform:'uppercase'}}>Preview</div>
              <div style={{fontSize:13,color:'var(--ink-2)',whiteSpace:'pre-wrap',maxHeight:180,overflow:'auto'}}>{data.jd.text}</div>
            </div>
          )}
        </Fragment>
      ) : (
        <Fragment>
          <textarea className="text" rows="12" placeholder="Paste the full job description here..." value={data.jd.text} onChange={(e) => update('jd',{text:e.target.value})}/>
          <div className="meta-row">
            <span>{wordCount(data.jd.text)} words</span>
          </div>
          {tooShort && <div className="warn-note">That's pretty short — paste the full JD for better tailoring.</div>}
        </Fragment>
      )}
    </div>
  );
}

/* Defined at module scope so React doesn't unmount/remount the <input> on every keystroke */
function ProfileField({ k, label, req, opt, ph, type, value, showSkips, update }) {
  return (
    <div className="field">
      <div className="field-label">
        {label} {req && <span className="req">*</span>} {opt && <span className="badge-opt">optional</span>}
        {showSkips && opt && value && <button className="skip-inline" onClick={() => update('profile', { [k]: '' })}>clear</button>}
      </div>
      <input className="text" type={type || 'text'} placeholder={ph} value={value} onChange={(e) => update('profile', { [k]: e.target.value })}/>
    </div>
  );
}

function StepProfile({ data, update, showSkips }) {
  const fp = (k) => ({ k, value: data.profile[k], showSkips, update });
  return (
    <div className="step">
      <div className="eyebrow">step 03 / 06 · profile</div>
      <h1 className="step-title">Your contact info</h1>
      <p className="step-subtitle">This goes at the top of your resume. Only name and email are required.</p>
      <ProfileField {...fp('name')}     label="Full name"  req ph="Jialong Li"/>
      <ProfileField {...fp('email')}    label="Email"      req type="email" ph="jl@columbia.edu"/>
      <ProfileField {...fp('phone')}    label="Phone"      opt ph="+1 (212) 555-0123"/>
      <ProfileField {...fp('location')} label="Location"   opt ph="New York, NY"/>
      <ProfileField {...fp('linkedin')} label="LinkedIn"   opt ph="linkedin.com/in/…"/>
      <ProfileField {...fp('github')}   label="GitHub"     opt ph="github.com/…"/>
      <ProfileField {...fp('website')}  label="Website"    opt ph="yourname.com"/>
    </div>
  );
}

function StepStories({ data, setData }) {
  const [drafting, setDrafting] = useState(false);
  const [draftErr, setDraftErr] = useState('');

  const update = (i, patch) => setData(d => ({
    ...d,
    stories: d.stories.map((s, j) => {
      if (j !== i) return s;
      const next = { ...s, ...patch };
      if ('text' in patch && patch.text !== s.text) next._draft = false;
      return next;
    }),
  }));
  const remove = (i) => setData(d => ({ ...d, stories: d.stories.filter((_, j) => j !== i) }));
  const add    = () => setData(d => ({ ...d, stories: [...d.stories, { id: `STAR_${d.stories.length + 1}`, tags: [], text: '' }] }));

  const allEmpty  = data.stories.every(s => !s.text.trim());
  const hasResume = !!(data.resume.latex && data.resume.latex.trim());
  const hasJd     = !!((data.jd.text && data.jd.text.trim()) || (data.jd.url && data.jd.url.trim()));

  const draftFromResume = async () => {
    setDrafting(true);
    setDraftErr('');
    try {
      const resp = await fetch('/api/draft-stories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resume: { latex: data.resume.latex },
          jd:     { text: data.jd.text, url: data.jd.url },
          model:  data.model,
        }),
      });
      const json = await resp.json();
      if (!json.ok) throw new Error(json.error || 'Could not draft stories');
      const drafts = json.stories.map(s => ({ ...s, _draft: true }));
      setData(d => ({ ...d, stories: drafts.length ? drafts : d.stories }));
    } catch (e) {
      setDraftErr(e.message || 'Network error — is server.py running?');
    } finally {
      setDrafting(false);
    }
  };

  return (
    <div className="step wide">
      <div className="eyebrow">step 04 / 06 · stories</div>
      <h1 className="step-title">Add a few experience stories</h1>
      <p className="step-subtitle">Each story is one project, role, or achievement in 40–80 words. Tag it so we can match it to relevant JDs.</p>

      {allEmpty && (
        <div className="draft-hero">
          <div className="draft-hero-body">
            <div className="draft-hero-title">No stories yet? We'll draft them.</div>
            <div className="softnote" style={{marginTop:0}}>
              Two starter stories, pulled from your resume{hasJd ? ' and the JD' : ''}.
              You edit before continuing — what you keep is what we use.
            </div>
            {!hasResume && <div className="warn-note" style={{marginTop:10}}>Pick a resume in step 01 first — we need it to draft.</div>}
            {draftErr && <div className="warn-note" style={{marginTop:10,background:'var(--sub-bg)',color:'var(--sub-fg)'}}>{draftErr}</div>}
          </div>
          <button
            className="btn primary lg"
            onClick={draftFromResume}
            disabled={!hasResume || drafting}
          >
            {drafting
              ? <Fragment><span className="dots"><span>.</span><span>.</span><span>.</span></span>Drafting</Fragment>
              : <Fragment><Icon name="sparkles" size={14}/>Draft from my resume</Fragment>}
          </button>
        </div>
      )}

      {data.stories.map((s, i) => {
        const wc = wordCount(s.text);
        return (
          <div key={i} className={`story-card ${s._draft ? 'is-draft' : ''}`}>
            {s._draft && (
              <div className="draft-banner">
                <Icon name="sparkles" size={12}/>
                <span>Drafted from your resume — edit anything; this becomes your story.</span>
              </div>
            )}
            <div className="scrow">
              <input className="text id-input" value={s.id} onChange={(e) => update(i, { id: e.target.value })} placeholder="STORY_ID"/>
              <TagInput tags={s.tags} onChange={(tags) => update(i, { tags })}/>
              {data.stories.length > 1 && (
                <button className="trash" onClick={() => remove(i)} title="Remove story"><Icon name="trash" size={16}/></button>
              )}
            </div>
            <textarea className="text" rows="4" placeholder="Built X to solve Y. Used Z. Result: …" value={s.text} onChange={(e) => update(i, { text: e.target.value })}/>
            <div className="meta-row">
              <span></span>
              <span className={`wc ${wc >= 40 && wc <= 80 ? 'good' : wc > 80 ? 'warn' : ''}`}>{wc} / 40–80 words</span>
            </div>
          </div>
        );
      })}

      <button className="btn" onClick={add} style={{marginTop:8}}>
        <Icon name="plus" size={14}/>Add another story
      </button>
    </div>
  );
}

function TagInput({ tags, onChange }) {
  const [input, setInput] = useState('');
  const add = (t) => { t = t.trim(); if (!t || tags.includes(t)) return; onChange([...tags, t]); setInput(''); };
  const rm = (t) => onChange(tags.filter(x => x !== t));
  return (
    <div style={{flex:1}}>
      <div className="tag-input">
        {tags.map(t => <span key={t} className="tag">{t}<button className="x" onClick={() => rm(t)}>×</button></span>)}
        <input
          value={input} placeholder={tags.length ? 'add tag…' : 'tags (e.g. ML, Research)'}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add(input); } }}
        />
      </div>
      <div className="tag-suggest">
        {SUGGESTED_TAGS.filter(t => !tags.includes(t)).slice(0, 6).map(t => (
          <span key={t} className="tag" onClick={() => add(t)}>+ {t}</span>
        ))}
      </div>
    </div>
  );
}

// Per-file and aggregate caps so a stray binary or huge log doesn't blow
// the localStorage quota or freeze the textarea on every render.
const VOICE_FILE_MAX = 200_000;   // 200 KB per file
const VOICE_TOTAL_MAX = 800_000;  // 800 KB joined cap

function StepVoice({ data, update, setData }) {
  const wc = wordCount(data.voice.sample);
  const onFiles = async (e) => {
    const files = Array.from(e.target.files || []);
    e.target.value = '';
    const accepted = files.filter(f => f.size > 0 && f.size <= VOICE_FILE_MAX);
    const skipped = files.length - accepted.length;
    if (!accepted.length) {
      if (skipped) alert(`Skipped ${skipped} file(s): each must be ≤ ${VOICE_FILE_MAX/1000}KB of text.`);
      return;
    }
    const texts = await Promise.all(accepted.map(f => f.text()));
    const joined = texts.join('\n\n---\n\n');
    // Functional update so we don't clobber edits the user makes while files load.
    setData(d => {
      const existing = d.voice.sample.trim();
      const merged = (existing ? `${existing}\n\n---\n\n${joined}` : joined).slice(0, VOICE_TOTAL_MAX);
      return { ...d, voice: { ...d.voice, sample: merged } };
    });
    if (skipped) alert(`Skipped ${skipped} file(s) over ${VOICE_FILE_MAX/1000}KB.`);
  };
  return (
    <div className="step">
      <div className="eyebrow">step 05 / 06 · voice <span className="badge-opt" style={{marginLeft:8}}>optional</span></div>
      <h1 className="step-title">Drop in a writing sample</h1>
      <p className="step-subtitle">A paragraph from your blog, a cover letter, an email — anything in your natural voice. We'll match its tone in the cover letter.</p>
      <textarea className="text" rows="11" placeholder="Paste a paragraph or two of your own writing…" value={data.voice.sample} onChange={(e) => update('voice', { sample: e.target.value })}/>
      <div className="meta-row">
        <span>{wc} words</span>
        <span>{wc >= 80 ? 'good signal' : wc > 0 ? 'a bit short — more helps' : ''}</span>
      </div>
      <div style={{display:'flex', gap:10, marginTop:10}}>
        <label className="btn">
          <Icon name="upload" size={14}/> Upload .txt / .md
          <input type="file" multiple accept=".txt,.md,text/plain,text/markdown" style={{display:'none'}} onChange={onFiles}/>
        </label>
        {data.voice.sample && (
          <button className="btn ghost" onClick={() => update('voice', { sample: '' })}>Clear sample</button>
        )}
      </div>
      <p className="softnote">Multiple files are appended. Your sample is remembered locally for next session — skip and come back any time.</p>
    </div>
  );
}

function StepReview({ data, setData, goto }) {
  const items = [
    { step: 0, label: 'Resume',  value: data.resume.file || (data.resume.template ? `Template: ${data.resume.template}` : data.resume.latex ? `${data.resume.latex.length} chars of LaTeX` : '—'), done: !!(data.resume.file || data.resume.template || data.resume.latex) },
    { step: 1, label: 'JD',      value: data.jd.mode === 'url' ? data.jd.url : `${wordCount(data.jd.text)} words pasted`, done: !!(data.jd.url || data.jd.text) },
    { step: 2, label: 'Profile', value: `${data.profile.name} · ${data.profile.email}`, done: !!(data.profile.name && data.profile.email) },
    { step: 3, label: 'Stories', value: `${data.stories.filter(s => s.text.trim()).length} stories`, done: data.stories.some(s => s.text.trim()) },
    { step: 4, label: 'Voice',   value: data.voice.sample ? `${wordCount(data.voice.sample)} words` : 'skipped', done: true, skipped: !data.voice.sample },
  ];
  return (
    <div className="step">
      <div className="eyebrow">step 06 / 06 · review</div>
      <h1 className="step-title">Looks good?</h1>
      <p className="step-subtitle">Review your inputs, then generate. This usually takes 30–90 seconds.</p>
      <ul className="summary">
        {items.map(it => (
          <li key={it.step}>
            <span className={`check ${it.skipped ? 'skip' : 'done'}`}><Icon name={it.skipped ? 'arrow-right' : 'check'} size={12} stroke={2}/></span>
            <div style={{flex:1}}>
              <div className="label">{it.label}</div>
              <div className="value">{it.value || <em style={{color:'var(--ink-3)'}}>—</em>}</div>
            </div>
            <button className="edit" onClick={() => goto(it.step)}>edit</button>
          </li>
        ))}
      </ul>
      <div className="card" style={{marginTop:24}}>
        <div className="field-label" style={{marginBottom:12}}>Model</div>
        <div className="segmented">
          <button className={data.model==='haiku'?'active':''}  onClick={() => setData(d => ({...d, model: 'haiku'}))}>Haiku</button>
          <button className={data.model==='sonnet'?'active':''} onClick={() => setData(d => ({...d, model: 'sonnet'}))}>Sonnet</button>
          <button className={data.model==='opus'?'active':''}   onClick={() => setData(d => ({...d, model: 'opus'}))}>Opus</button>
        </div>
        <p className="softnote">Sonnet is the default. Opus is slower but stronger; Haiku is faster but rougher.</p>
      </div>
    </div>
  );
}

function GenerationScreen({ progress, model }) {
  const STAGES = [
    'Fetching job description',
    'Extracting job metadata',
    'Tailoring resume',
    'Building diff',
    'Writing cover letter',
  ];
  const pct = progress.step < 0 ? 2 : Math.min(100, ((progress.step + 1) / STAGES.length) * 100);
  return (
    <div className="gen-stage">
      <div className="gen-card">
        <h1 className="gen-headline">Tailoring your resume</h1>
        <p className="gen-note">{model} · usually 30–90s</p>
        <div className="feed">
          {STAGES.map((s, i) => {
            const state = i < progress.step ? 'done' : i === progress.step ? 'active' : 'pending';
            return (
              <div key={i} className={`row ${state}`} style={{animationDelay:`${i*60}ms`}}>
                <span className="check">
                  {state === 'done' && <Icon name="check" size={10} stroke={2.5}/>}
                  {state === 'active' && <span style={{width:6,height:6,background:'var(--ink)',borderRadius:'50%',animation:'blink 1s ease infinite'}}/>}
                </span>
                <span>{s}{state === 'active' && <span className="dots"><span>.</span><span>.</span><span>.</span></span>}</span>
              </div>
            );
          })}
        </div>
        <div className="gen-progress"><div className="fill" style={{width:`${pct}%`}}/></div>
      </div>
      {progress.step >= STAGES.length && <Confetti />}
    </div>
  );
}

function Confetti() {
  const colors = ['#1a1a17', '#16a34a', '#dc2626', '#854d0e', '#8a8780'];
  const pieces = useMemo(() => Array.from({length: 28}, (_, i) => ({
    left: 50 + (Math.random() - 0.5) * 30 + '%',
    top: '50%',
    dx: ((Math.random() - 0.5) * 600) + 'px',
    dy: ((Math.random() * 400) + 100) + 'px',
    rot: (Math.random() * 720 - 360) + 'deg',
    color: colors[i % colors.length],
    delay: (Math.random() * 100) + 'ms',
  })), []);
  return (
    <div className="confetti">
      {pieces.map((p, i) => (
        <i key={i} style={{ left: p.left, top: p.top, '--dx': p.dx, '--dy': p.dy, '--rot': p.rot, background: p.color, animationDelay: p.delay }}/>
      ))}
    </div>
  );
}

function PDFTab({ tailoredTex, downloadFile }) {
  const [state, setState] = useState('idle'); // idle | loading | done | error
  const [pdfUrl, setPdfUrl] = useState(null);
  const [errMsg, setErrMsg] = useState('');

  useEffect(() => {
    if (!tailoredTex) return;
    setState('loading');
    let url = null;
    fetch('/api/compile-pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ latex: tailoredTex }),
    })
      .then(resp => {
        if (!resp.ok) return resp.json().then(j => { throw new Error(j.error || `HTTP ${resp.status}`); });
        return resp.blob();
      })
      .then(blob => {
        url = URL.createObjectURL(blob);
        setPdfUrl(url);
        setState('done');
      })
      .catch(e => { setErrMsg(e.message); setState('error'); });
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [tailoredTex]);

  return (
    <Fragment>
      <div className="tab-toolbar">
        <span style={{fontSize:12,color:'var(--ink-3)',fontFamily:'var(--mono)'}}>
          {state === 'loading' && 'Compiling PDF…'}
          {state === 'done'    && 'resume.pdf · compiled with pdflatex'}
          {state === 'error'   && `Compilation failed: ${errMsg}`}
          {state === 'idle'    && 'PDF preview'}
        </span>
        <div className="right">
          {pdfUrl && (
            <a className="btn" style={{padding:'6px 12px',fontSize:12,textDecoration:'none'}} href={pdfUrl} download="resume.pdf">
              <Icon name="download" size={12}/>resume.pdf
            </a>
          )}
          <button className="btn" style={{padding:'6px 12px',fontSize:12}}
            onClick={() => downloadFile('resume.tex', tailoredTex)}>
            <Icon name="download" size={12}/>resume.tex
          </button>
        </div>
      </div>
      {state === 'loading' && <div className="pdf-mock">Compiling with pdflatex… this takes ~10s</div>}
      {state === 'error'   && <div className="pdf-mock" style={{color:'var(--sub-fg)'}}>{errMsg}<br/><br/>Download the .tex and open in Overleaf instead.</div>}
      {state === 'done' && pdfUrl && (
        <iframe className="embed" src={pdfUrl} title="PDF preview" style={{border:'none'}}/>
      )}
    </Fragment>
  );
}

function ResultsScreen({ results, reset, data }) {
  const [tab, setTab] = useState('changes');
  const [editing, setEditing] = useState(false);
  const [coverText, setCoverText] = useState(results?.coverLetter || '');

  const downloadFile = (filename, content) => {
    const url = URL.createObjectURL(new Blob([content]));
    const a = Object.assign(document.createElement('a'), { href: url, download: filename });
    a.click();
    URL.revokeObjectURL(url);
  };

  const company = results?.company || '';
  const role    = results?.role    || '';
  const label   = [company, role].filter(Boolean).join(' · ') || 'tailored';

  return (
    <Fragment>
      <div className="topbar" style={{position:'fixed',top:0}}>
        <span className="brand"><span className="mark"><Icon name="logo" size={22}/></span>resume-tailor</span>
        <span style={{fontFamily:'var(--mono)',fontSize:11,color:'var(--ink-3)',letterSpacing:'.08em',textTransform:'uppercase'}}>
          ✓ done · {results?.generatedAt?.toLocaleTimeString() || 'just now'}
        </span>
        <button className="btn ghost" onClick={reset}><Icon name="undo" size={14}/>Start over</button>
      </div>
      <div className="results">
        <div className="results-wrap">
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}}>
            <div className="tabs">
              <button className={tab==='changes'?'active':''} onClick={() => setTab('changes')}><Icon name="list" size={14}/>Changes</button>
              <button className={tab==='cover'?'active':''}   onClick={() => setTab('cover')}><Icon name="file-text" size={14}/>Cover Letter</button>
              <button className={tab==='pdf'?'active':''}     onClick={() => setTab('pdf')}><Icon name="eye" size={14}/>PDF preview</button>
            </div>
            <button className="btn primary" onClick={() => downloadFile('resume.tex', results?.tailoredTex || '')}>
              <Icon name="download" size={14}/>Download .tex
            </button>
          </div>

          <div className="tab-panel">
            {tab === 'changes' && (
              <Fragment>
                <div className="tab-toolbar">
                  <span style={{fontSize:12,color:'var(--ink-3)',fontFamily:'var(--mono)'}}>{label} · resume.tex</span>
                  <div className="right">
                    <button className="btn" style={{padding:'6px 12px',fontSize:12}}
                      onClick={() => downloadFile('resume.tex', results?.tailoredTex || '')}>
                      <Icon name="download" size={12}/>resume.tex
                    </button>
                  </div>
                </div>
                <iframe
                  className="embed"
                  srcDoc={results?.diffHtml || '<p style="padding:24px;color:#888">No diff available.</p>'}
                  title="Resume diff"
                  sandbox="allow-same-origin"
                />
              </Fragment>
            )}
            {tab === 'cover' && (
              <Fragment>
                <div className="tab-toolbar">
                  <span style={{fontSize:12,color:'var(--ink-3)',fontFamily:'var(--mono)'}}>cover_letter.txt · {wordCount(coverText)} words</span>
                  <div className="right">
                    <button className="btn" style={{padding:'6px 12px',fontSize:12}} onClick={() => setEditing(e => !e)}><Icon name={editing ? 'check' : 'edit'} size={12}/>{editing ? 'Done' : 'Edit'}</button>
                    <button className="btn" style={{padding:'6px 12px',fontSize:12}} onClick={() => downloadFile('cover_letter.txt', coverText)}><Icon name="download" size={12}/>Download</button>
                    <button className="btn" style={{padding:'6px 12px',fontSize:12}} onClick={() => navigator.clipboard?.writeText(coverText)}><Icon name="copy" size={12}/>Copy</button>
                  </div>
                </div>
                {editing ? (
                  <textarea className="text" style={{margin:24,width:'calc(100% - 48px)',border:'1px solid var(--line)'}} rows="18" value={coverText} onChange={(e) => setCoverText(e.target.value)}/>
                ) : (
                  <div className="cover-letter">
                    {(() => {
                      const paras = coverText.split('\n\n');
                      return paras.map((p, i) => (
                        <p key={i} className={i === 0 ? 'salut' : i === paras.length - 1 ? 'sig' : ''}>{p}</p>
                      ));
                    })()}
                  </div>
                )}
              </Fragment>
            )}
            {tab === 'pdf' && (
              <PDFTab tailoredTex={results?.tailoredTex || ''} downloadFile={downloadFile} />
            )}
          </div>
        </div>
      </div>
    </Fragment>
  );
}

function Tweaks() {
  const [t, setT] = window.useTweaks(TWEAK_DEFAULTS);
  return (
    <window.TweaksPanel title="Tweaks" defaultPosition={{x: window.innerWidth - 280, y: 90}} width={260}>
      <window.TweakSection title="Jump to step">
        <div className="tweak-step-list">
          {STEPS.map((s, i) => (
            <button key={s.id} className={t.step === i ? 'active' : ''} onClick={() => setT('step', i)}>
              <span className="num">{String(i+1).padStart(2,'0')}</span>{s.title}
            </button>
          ))}
        </div>
      </window.TweakSection>
      <window.TweakSection title="Options">
        <window.TweakToggle label="Show 'clear' shortcut on optional fields" value={t.showSkips} onChange={(v) => setT('showSkips', v)}/>
      </window.TweakSection>
    </window.TweaksPanel>
  );
}

function Root() {
  return (
    <Fragment>
      <App />
      <Tweaks />
    </Fragment>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<Root />);

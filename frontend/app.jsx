/* Resume Tailor Wizard — Plan B aesthetic, one focus per page */

const { useState, useRef, useEffect, useMemo, Fragment } = React;

/* ===================== STEP DEFINITIONS ===================== */
const STEPS = [
  { id: 'resume',  title: 'Resume',   sub: 'Where should we start from?' },
  { id: 'jd',      title: 'JD',       sub: 'Paste the job description.' },
  { id: 'profile', title: 'Profile',  sub: 'Tell us about yourself.' },
  { id: 'stories', title: 'Stories',  sub: 'Add a few experience stories.' },
  { id: 'voice',   title: 'Voice',    sub: 'Optional: a writing sample.' },
  { id: 'review',  title: 'Review',   sub: 'Looks good? Generate.' },
];

const SUGGESTED_TAGS = ['Quant', 'Research', 'ML', 'Backend', 'Frontend', 'Data', 'Leadership', 'Open-source'];

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "step": 0,
  "fastGen": false,
  "showSkips": true
}/*EDITMODE-END*/;

/* ===================== APP ===================== */
function App() {
  const [tweaks, setTweak] = window.useTweaks(TWEAK_DEFAULTS);

  // form state
  const [data, setData] = useState({
    resume: { mode: null, file: null, template: null, latex: '' },
    jd:     { mode: 'url', url: '', text: '', fetched: false, fetchState: 'idle' },
    profile:{ name: '', email: '', phone: '', location: '', linkedin: '', github: '', website: '' },
    stories:[{ id: 'STAR_1', tags: [], text: '' }],
    voice:  { sample: '' },
    model:  'sonnet',
  });
  const update = (key, patch) => setData(d => ({ ...d, [key]: { ...d[key], ...patch } }));

  const [phase, setPhase] = useState('wizard'); // wizard | generating | results
  const [progress, setProgress] = useState({ step: -1, sub: 0 });
  const [results, setResults] = useState(null);

  const stepIdx = Math.min(tweaks.step, STEPS.length - 1);
  const goto = (i) => setTweak('step', Math.max(0, Math.min(STEPS.length - 1, i)));
  const next = () => goto(stepIdx + 1);
  const back = () => goto(stepIdx - 1);

  /* ----- mock generation ----- */
  const startGen = () => {
    setPhase('generating');
    setProgress({ step: 0, sub: 0 });
    const stepDelay = tweaks.fastGen ? 250 : 900;
    const sequence = [
      'Parsing resume…',
      'Analyzing job description…',
      'Selecting relevant stories…',
      'Tailoring bullets…',
      'Drafting cover letter…',
      'Building diff…',
    ];
    sequence.forEach((_, i) => {
      setTimeout(() => setProgress({ step: i, sub: 0 }), i * stepDelay);
    });
    setTimeout(() => {
      setProgress({ step: sequence.length, sub: 0 });
      setResults({ generatedAt: new Date() });
      setTimeout(() => setPhase('results'), 600);
    }, sequence.length * stepDelay + 400);
  };

  const reset = () => { setPhase('wizard'); setResults(null); goto(0); };

  /* ----- step validity ----- */
  const canContinue = useMemo(() => {
    switch (STEPS[stepIdx].id) {
      case 'resume':  return !!data.resume.mode && (data.resume.mode === 'scratch' ? !!data.resume.template : data.resume.mode === 'file' ? !!data.resume.file : data.resume.mode === 'overleaf' ? !!data.resume.latex.trim() : data.resume.mode === 'previous');
      case 'jd':      return data.jd.mode === 'url' ? !!data.jd.url.trim() : !!data.jd.text.trim();
      case 'profile': return !!data.profile.name.trim() && !!data.profile.email.trim();
      case 'stories': return data.stories.some(s => s.text.trim().length > 20);
      case 'voice':   return true;
      case 'review':  return true;
      default: return true;
    }
  }, [stepIdx, data]);

  /* ----- header ----- */
  const ProgressHeader = () => (
    <Fragment>
      <div className="progress-rail"><div className="progress-fill" style={{ width: `${((stepIdx) / (STEPS.length - 1)) * 100}%` }} /></div>
      <div className="topbar">
        <span className="brand"><span className="mark"><Icon name="logo" size={22}/></span>resume-tailor</span>
        <div className="steplist">
          {STEPS.map((s, i) => (
            <button key={s.id} className={`pip ${i < stepIdx ? 'done' : ''} ${i === stepIdx ? 'active' : ''}`} onClick={() => goto(i)}>
              <span className="dot"/>{String(i+1).padStart(2,'0')} {s.title}
            </button>
          ))}
        </div>
        <button className="skip" onClick={reset}>start over</button>
      </div>
    </Fragment>
  );

  /* ----- phase rendering ----- */
  if (phase === 'generating') return <GenerationScreen progress={progress} fast={tweaks.fastGen} />;
  if (phase === 'results')    return <ResultsScreen results={results} reset={reset} data={data} />;

  return (
    <Fragment>
      <ProgressHeader />
      <main className="stage">
        {STEPS[stepIdx].id === 'resume'  && <StepResume  data={data} update={update}/>}
        {STEPS[stepIdx].id === 'jd'      && <StepJD      data={data} update={update}/>}
        {STEPS[stepIdx].id === 'profile' && <StepProfile data={data} update={update} showSkips={tweaks.showSkips}/>}
        {STEPS[stepIdx].id === 'stories' && <StepStories data={data} setData={setData}/>}
        {STEPS[stepIdx].id === 'voice'   && <StepVoice   data={data} update={update}/>}
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

/* ===================== STEP 1: RESUME ===================== */
function StepResume({ data, update }) {
  const fileRef = useRef();
  const [drag, setDrag] = useState(false);
  const mode = data.resume.mode;

  const choose = (m) => update('resume', { mode: m });

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
              <p className="desc">PDF, DOCX, or .tex — we'll extract structure.</p>
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

  /* sub-screens after picking a mode */
  return (
    <div className="step">
      <div className="eyebrow">
        <button className="skip" onClick={() => choose(null)} style={{padding:'0',background:'none',color:'inherit',fontFamily:'inherit',fontSize:'inherit',letterSpacing:'inherit',textTransform:'inherit'}}>← change source</button>
      </div>

      {mode === 'file' && (
        <Fragment>
          <h1 className="step-title">Upload your resume</h1>
          <p className="step-subtitle">PDF, DOCX, or LaTeX source. We'll extract the structure.</p>
          <div
            className={`dropzone ${drag ? 'over' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) update('resume', { file: f.name }); }}
            onClick={() => fileRef.current.click()}
            style={{ cursor: 'pointer' }}
          >
            <input type="file" ref={fileRef} hidden accept=".pdf,.docx,.tex" onChange={(e) => e.target.files[0] && update('resume', { file: e.target.files[0].name })}/>
            <Icon name="upload" size={28} style={{ color: 'var(--ink-3)' }}/>
            <p style={{margin:'12px 0 4px',fontSize:14,color:'var(--ink)'}}>Drop your file here</p>
            <p style={{margin:0,fontSize:12,color:'var(--ink-3)'}}>or click to browse · pdf · docx · tex</p>
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

/* ===================== STEP 2: JD ===================== */
function StepJD({ data, update }) {
  const fetchUrl = () => {
    update('jd', { fetchState: 'fetch' });
    setTimeout(() => {
      update('jd', { fetchState: 'ok', fetched: true, text: '[Sample JD] Senior Research Engineer\n\nWe are looking for someone with experience in...' });
    }, 1100);
  };
  const tooShort = data.jd.mode === 'text' && data.jd.text.trim().length > 0 && data.jd.text.trim().length < 200;
  return (
    <div className="step">
      <div className="eyebrow">step 02 / 06 · job description</div>
      <h1 className="step-title">Paste the job description</h1>
      <p className="step-subtitle">A URL works if the page is publicly accessible. Otherwise paste the full text.</p>
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
              {data.jd.fetchState === 'idle' && 'idle'}
              {data.jd.fetchState === 'fetch' && 'fetching…'}
              {data.jd.fetchState === 'ok' && 'fetched · 1.2 kb'}
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
            <span>{data.jd.text.trim().split(/\s+/).filter(Boolean).length} words</span>
          </div>
          {tooShort && <div className="warn-note">That's pretty short — paste the full JD for better tailoring.</div>}
        </Fragment>
      )}
    </div>
  );
}

/* ===================== STEP 3: PROFILE ===================== */
function StepProfile({ data, update, showSkips }) {
  const F = ({ k, label, req, opt, ph, type='text' }) => (
    <div className="field">
      <div className="field-label">
        {label} {req && <span className="req">*</span>} {opt && <span className="badge-opt">optional</span>}
        {showSkips && opt && data.profile[k] && <button className="skip-inline" onClick={() => update('profile', { [k]: '' })}>clear</button>}
      </div>
      <input className="text" type={type} placeholder={ph} value={data.profile[k]} onChange={(e) => update('profile', { [k]: e.target.value })}/>
    </div>
  );
  return (
    <div className="step">
      <div className="eyebrow">step 03 / 06 · profile</div>
      <h1 className="step-title">Your contact info</h1>
      <p className="step-subtitle">This goes at the top of your resume. Only name and email are required.</p>
      <F k="name"     label="Full name"   req ph="Jialong Li"/>
      <F k="email"    label="Email"       req type="email" ph="jl@columbia.edu"/>
      <F k="phone"    label="Phone"       opt ph="+1 (212) 555-0123"/>
      <F k="location" label="Location"    opt ph="New York, NY"/>
      <F k="linkedin" label="LinkedIn"    opt ph="linkedin.com/in/…"/>
      <F k="github"   label="GitHub"      opt ph="github.com/…"/>
      <F k="website"  label="Website"     opt ph="yourname.com"/>
    </div>
  );
}

/* ===================== STEP 4: STORIES ===================== */
function StepStories({ data, setData }) {
  const update = (i, patch) => setData(d => ({ ...d, stories: d.stories.map((s, j) => j === i ? { ...s, ...patch } : s) }));
  const remove = (i) => setData(d => ({ ...d, stories: d.stories.filter((_, j) => j !== i) }));
  const add = () => setData(d => ({ ...d, stories: [...d.stories, { id: `STAR_${d.stories.length + 1}`, tags: [], text: '' }] }));
  const wc = (s) => s.trim().split(/\s+/).filter(Boolean).length;

  return (
    <div className="step wide">
      <div className="eyebrow">step 04 / 06 · stories</div>
      <h1 className="step-title">Add a few experience stories</h1>
      <p className="step-subtitle">Each story is one project, role, or achievement in 40–80 words. Tag it so we can match it to relevant JDs.</p>

      {data.stories.map((s, i) => (
        <div key={i} className="story-card">
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
            <span className={`wc ${wc(s.text) >= 40 && wc(s.text) <= 80 ? 'good' : wc(s.text) > 80 ? 'warn' : ''}`}>{wc(s.text)} / 40–80 words</span>
          </div>
        </div>
      ))}

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

/* ===================== STEP 5: VOICE ===================== */
function StepVoice({ data, update }) {
  const wc = data.voice.sample.trim().split(/\s+/).filter(Boolean).length;
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
      <p className="softnote">Skip this if you'd rather use the default Claude voice. You can always come back.</p>
    </div>
  );
}

/* ===================== STEP 6: REVIEW ===================== */
function StepReview({ data, setData, goto }) {
  const items = [
    { step: 0, label: 'Resume',  value: data.resume.file || (data.resume.template ? `Template: ${data.resume.template}` : data.resume.latex ? `${data.resume.latex.length} chars of LaTeX` : '—'), done: !!(data.resume.file || data.resume.template || data.resume.latex) },
    { step: 1, label: 'JD',      value: data.jd.mode === 'url' ? data.jd.url : `${data.jd.text.trim().split(/\s+/).filter(Boolean).length} words pasted`, done: !!(data.jd.url || data.jd.text) },
    { step: 2, label: 'Profile', value: `${data.profile.name} · ${data.profile.email}`, done: !!(data.profile.name && data.profile.email) },
    { step: 3, label: 'Stories', value: `${data.stories.filter(s => s.text.trim()).length} stories`, done: data.stories.some(s => s.text.trim()) },
    { step: 4, label: 'Voice',   value: data.voice.sample ? `${data.voice.sample.trim().split(/\s+/).filter(Boolean).length} words` : 'skipped', done: true, skipped: !data.voice.sample },
  ];
  return (
    <div className="step">
      <div className="eyebrow">step 06 / 06 · review</div>
      <h1 className="step-title">Looks good?</h1>
      <p className="step-subtitle">Review your inputs, then generate. This usually takes 30–60 seconds.</p>
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

/* ===================== GENERATION SCREEN ===================== */
function GenerationScreen({ progress, fast }) {
  const STAGES = ['Parsing resume', 'Analyzing JD', 'Selecting stories', 'Tailoring bullets', 'Drafting cover letter', 'Building diff'];
  const pct = Math.min(100, ((progress.step + 1) / STAGES.length) * 100);
  return (
    <div className="gen-stage">
      <div className="gen-card">
        <h1 className="gen-headline">Tailoring your resume</h1>
        <p className="gen-note">claude-3.5-sonnet · {fast ? '~10s' : '~45s'}</p>
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
  const pieces = Array.from({length: 28}, (_, i) => ({
    left: 50 + (Math.random() - 0.5) * 30 + '%',
    top: '50%',
    dx: ((Math.random() - 0.5) * 600) + 'px',
    dy: ((Math.random() * 400) + 100) + 'px',
    rot: (Math.random() * 720 - 360) + 'deg',
    color: colors[i % colors.length],
    delay: (Math.random() * 100) + 'ms',
  }));
  return (
    <div className="confetti">
      {pieces.map((p, i) => (
        <i key={i} style={{ left: p.left, top: p.top, '--dx': p.dx, '--dy': p.dy, '--rot': p.rot, background: p.color, animationDelay: p.delay }}/>
      ))}
    </div>
  );
}

/* ===================== RESULTS ===================== */
function ResultsScreen({ results, reset, data }) {
  const [tab, setTab] = useState('changes');
  const [editing, setEditing] = useState(false);
  const [coverText, setCoverText] = useState(`Dear hiring team,

I'm applying for the Senior Research Engineer role. Over the past three years I've built and shipped ML systems at scale — most recently leading a project that cut inference latency by 38% while improving accuracy on a key benchmark.

What draws me to this role specifically is the focus on alignment research and the rigor your team brings to it. I'd love to bring my experience with distributed training, evaluation frameworks, and a habit of writing clearly to the work you're doing.

Happy to share more in conversation.

Best,
${data.profile.name || 'Jialong Li'}`);

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
            <button className="btn primary"><Icon name="download" size={14}/>Download all (.zip)</button>
          </div>

          <div className="tab-panel">
            {tab === 'changes' && (
              <Fragment>
                <div className="tab-toolbar">
                  <span style={{fontSize:12,color:'var(--ink-3)',fontFamily:'var(--mono)'}}>resume.tex · 12 inserts · 8 removals</span>
                  <div className="right">
                    <button className="btn" style={{padding:'6px 12px',fontSize:12}}><Icon name="download" size={12}/>resume.tex</button>
                  </div>
                </div>
                <iframe className="embed" src="resume_diff_preview.html" title="Resume diff"/>
              </Fragment>
            )}
            {tab === 'cover' && (
              <Fragment>
                <div className="tab-toolbar">
                  <span style={{fontSize:12,color:'var(--ink-3)',fontFamily:'var(--mono)'}}>cover_letter.txt · {coverText.trim().split(/\s+/).filter(Boolean).length} words</span>
                  <div className="right">
                    <button className="btn" style={{padding:'6px 12px',fontSize:12}} onClick={() => setEditing(e => !e)}><Icon name={editing ? 'check' : 'edit'} size={12}/>{editing ? 'Done' : 'Edit'}</button>
                    <button className="btn" style={{padding:'6px 12px',fontSize:12}} onClick={() => navigator.clipboard?.writeText(coverText)}><Icon name="copy" size={12}/>Copy</button>
                  </div>
                </div>
                {editing ? (
                  <textarea className="text" style={{margin:24,width:'calc(100% - 48px)',border:'1px solid var(--line)'}} rows="18" value={coverText} onChange={(e) => setCoverText(e.target.value)}/>
                ) : (
                  <div className="cover-letter">
                    {coverText.split('\n\n').map((p, i) => (
                      <p key={i} className={i === 0 ? 'salut' : i === coverText.split('\n\n').length - 1 ? 'sig' : ''}>{p}</p>
                    ))}
                  </div>
                )}
              </Fragment>
            )}
            {tab === 'pdf' && (
              <Fragment>
                <div className="tab-toolbar">
                  <span style={{fontSize:12,color:'var(--ink-3)',fontFamily:'var(--mono)'}}>resume.pdf · 1 page · compiled with pdflatex</span>
                  <div className="right">
                    <button className="btn" style={{padding:'6px 12px',fontSize:12}}><Icon name="download" size={12}/>resume.pdf</button>
                  </div>
                </div>
                <div className="pdf-mock">[ PDF preview rendered here after backend compile ]</div>
              </Fragment>
            )}
          </div>
        </div>
      </div>
    </Fragment>
  );
}

/* ===================== TWEAKS PANEL ===================== */
function Tweaks() {
  const tweaks = window.useTweaks ? null : null; // dummy
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
      <window.TweakSection title="Demo">
        <window.TweakToggle label="Fast generation" value={t.fastGen} onChange={(v) => setT('fastGen', v)}/>
        <window.TweakToggle label="Show 'clear' shortcut on optional fields" value={t.showSkips} onChange={(v) => setT('showSkips', v)}/>
      </window.TweakSection>
    </window.TweaksPanel>
  );
}

/* ===================== MOUNT ===================== */
function Root() {
  return (
    <Fragment>
      <App />
      <Tweaks />
    </Fragment>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<Root />);

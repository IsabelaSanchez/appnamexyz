<script lang="ts">
  import { onMount } from 'svelte';
  import { Dialog } from 'bits-ui';
  import { ArrowRight, Upload, Settings, SlidersHorizontal, Sparkles, Download, Undo2, Redo2, ZoomIn, ZoomOut, Maximize, Check, Layers, Map, CircleHelp, X, Send, FileImage, Code, ArrowUpRight } from 'lucide-svelte';
  import { api, resource, diagnostics, type Branding, type Config, type Engine, type Job, type Project, type Representation, type Status } from '$lib/api';
  import { fallbackBranding } from '$lib/branding';
  import { defaults, loadPreferences, savePreferences } from '$lib/preferences';
  import '../style.css';

  let brand = $state<Branding>(fallbackBranding);
  let preferences = $state({ ...defaults });
  let mode = $state('easy');
  let status = $state<Status>({ enabled: true, ai_available: false, active_jobs: 0, session_hours: 12, max_upload_mb: 12 });
  let engines = $state<Engine[]>([]);
  let project = $state<Project | null>(null);
  let rep = $state<Representation | null>(null);
  let job = $state<Job | null>(null);
  let busy = $state(false);
  let error = $state('');
  let notice = $state('');
  let instruction = $state('');
  let previewVersion = $state(0);
  let zoom = $state(1);
  let compare = $state(true);
  let settingsOpen = $state(false);
  let messages = $state<{ role: string; text: string }[]>([]);
  let fileInput: HTMLInputElement;
  let diagnosticsData = $state('');
  let config = $state<Config>({ engine: 'auto', language: 'eng', map_type: 'automatic', include: ['borders', 'rivers', 'roads', 'regions', 'cities', 'labels', 'landmarks', 'other'], simplification: 0.003, density: 'balanced', preprocess: true, output: { profile: 'digital', page_width_mm: 210, page_height_mm: 297, line_width: 1.2, label_size: 14, symbol_size: 5, minimum_spacing_mm: 3, legend: true, texture: 'none', contrast: 'high' } });
  const categories = ['borders', 'rivers', 'roads', 'regions', 'cities', 'labels', 'landmarks', 'other'];
  const visibleCount = $derived(rep?.elements.filter(e => e.visible).length || 0);
  const previewUrl = $derived(project ? resource(`/api/v1/projects/${project.id}/preview?v=${previewVersion}`) : '');

  onMount(() => {
    preferences = loadPreferences();
    mode = preferences.mode;
    config.engine = preferences.engine;
    config.output.profile = preferences.profile;
    void initialize();
  });

  $effect(() => {
    if (typeof document !== 'undefined') {
      const dark = preferences.theme === 'dark' || preferences.theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches;
      document.documentElement.dataset.theme = dark ? 'dark' : 'light';
      document.documentElement.style.setProperty('--accent', dark ? '#99d8c7' : brand.themeColor);
      document.documentElement.style.fontSize = `${preferences.textSize}%`;
      document.documentElement.dataset.motion = preferences.reducedMotion ? 'reduced' : 'normal';
      savePreferences(preferences);
    }
  });

  async function initialize() {
    try {
      [brand, status, engines] = await Promise.all([api<Branding>('/branding'), api<Status>('/status'), api<Engine[]>('/engines')]);
      const saved = sessionStorage.getItem('project');
      if (saved) {
        try { project = await api<Project>(`/projects/${saved}`); config = project.config; if (project.revision >= 0) await refresh(); }
        catch { sessionStorage.removeItem('project'); }
      }
    } catch (e) { fail(e); }
  }
  function fail(e: unknown) { error = e instanceof Error ? e.message : 'An unexpected error occurred. Please try again.'; }
  async function guard(action: () => Promise<void>) { error = ''; notice = ''; busy = true; try { await action(); } catch (e) { fail(e); } finally { busy = false; } }
  async function upload(file?: File) {
    if (!file) return;
    await guard(async () => {
      if (file.size > status.max_upload_mb * 1024 * 1024) throw new Error(`Choose an image smaller than ${status.max_upload_mb} MB.`);
      const data = new FormData(); data.append('file', file);
      project = await api<Project>('/projects', { method: 'POST', body: data });
      sessionStorage.setItem('project', project.id);
      rep = null; job = null; messages = []; notice = 'Your map is ready to analyze.';
    });
  }
  async function refresh() {
    if (!project) return;
    [rep, project] = await Promise.all([api<Representation>(`/projects/${project.id}/representation`), api<Project>(`/projects/${project.id}`)]);
    previewVersion++; zoom = 1;
    if (preferences.developer) diagnosticsData = JSON.stringify(await api(`/projects/${project.id}/diagnostics`), null, 2);
  }
  async function waitForJob(value: Job) {
    if (!project) return;
    job = value;
    for (let attempt = 0; attempt < 150; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 1500));
      job = await api<Job>(`/projects/${project.id}/jobs/${value.id}`);
      if (job.status === 'failed') throw new Error(job.error || 'Processing failed.');
      if (job.status === 'completed') {
        if (!job.clarification) await refresh();
        notice = job.message || 'Your map is ready.';
        return;
      }
    }
    throw new Error('Processing is taking longer than expected. Reload the page to check the project.');
  }
  async function analyze() {
    await guard(async () => {
      if (!project) return;
      project = await api<Project>(`/projects/${project.id}/configuration`, { method: 'PATCH', body: JSON.stringify(config) });
      await waitForJob(await api<Job>(`/projects/${project.id}/analyze`, { method: 'POST' }));
    });
  }
  async function refine(text = instruction) {
    if (!text.trim() || !project) return;
    instruction = ''; messages.push({ role: 'You', text });
    await guard(async () => {
      if (!project) return;
      await waitForJob(await api<Job>(`/projects/${project.id}/refine`, { method: 'POST', body: JSON.stringify({ instruction: text }) }));
      messages.push({ role: 'Assistant', text: job?.message || 'Changes applied.' });
    });
  }
  async function history(direction: string) { await guard(async () => { if (project) { await api(`/projects/${project.id}/history/${direction}`, { method: 'POST' }); await refresh(); } }); }
  async function editElement(id: string, update: Record<string, unknown>) { await guard(async () => { if (project) { await api(`/projects/${project.id}/elements/${id}`, { method: 'PATCH', body: JSON.stringify(update) }); await refresh(); } }); }
  async function download(format: string) {
    await guard(async () => {
      if (!project) return;
      const result = await api<{ url: string }>(`/projects/${project.id}/exports/${format}`, { method: 'POST' });
      const link = document.createElement('a'); link.href = resource(result.url); link.download = `accessible-map.${format}`; document.body.appendChild(link); link.click(); link.remove(); notice = `${format.toUpperCase()} export generated.`;
    });
  }
  async function toggleProcessing() { await guard(async () => { status = await api<Status>(status.enabled ? '/disable' : '/enable', { method: 'POST' }); }); }
  async function copyDiagnostics() { try { await navigator.clipboard.writeText(diagnosticsData); notice = 'Diagnostics copied.'; } catch { error = 'Clipboard unavailable. Select and copy the JSON below.'; } }
</script>

<svelte:head><title>{brand.name} — {brand.tagline}</title><meta name="description" content={brand.description} /><link rel="icon" href={brand.favicon} /></svelte:head>

<a class="skip-link" href="#main">Skip to main content</a>
<header class="topbar">
  <a href="/" class="brand" aria-label={`${brand.name} home`}><img src={brand.logo} alt="" width="36" height="36" /><span>{brand.name}<span class="brand-caption">ACCESSIBLE LEARNING STUDIO</span></span></a>
  <div class="header-actions"><span class="pilot-badge">Research preview</span><button class="icon-button" onclick={() => settingsOpen = true} aria-label="Open application settings"><Settings size={20} /></button></div>
</header>

<main id="main">
  <div class="intro"><div><div class="eyebrow"><span class="small-dot"></span> LESS BARRIERS. MORE POSSIBILITIES.</div><h1>{rep ? 'A new way to read your map.' : brand.tagline}</h1><p>{rep ? 'Review, refine, and shape your learning material together.' : brand.description}</p></div><div class="intro-note"><Layers size={20}/><span>Built for different ways<br/>of seeing and learning.</span></div></div>
  <nav class="workflow" aria-label="Transformation progress">{#each ['Upload', 'Analyze', 'Refine', 'Export'] as step, index}<div class:active={rep ? index >= 2 : project ? index === 1 : index === 0}><span>{(project && index === 0) || (rep && index === 1) ? '✓' : String(index + 1).padStart(2, '0')}</span>{step}</div>{#if index < 3}<div class="step-line"></div>{/if}{/each}</nav>
  <div class="notifications"><div role="alert">{#if error}<p class="error">{error}</p>{/if}</div><div role="status" aria-live="polite">{#if notice}<p class="notice">{notice}</p>{/if}</div></div>
  {#if !status.enabled}<p class="warning">Processing is paused. You can still preview and download existing results.</p>{/if}
  <div class="workspace">
    <aside class="sidebar">
      <div class="mode-tabs" aria-label="Application mode"><button class:chosen={mode === 'easy'} aria-pressed={mode === 'easy'} onclick={() => mode = 'easy'}><Sparkles size={15}/>Easy Mode</button><button class:chosen={mode === 'advanced'} aria-pressed={mode === 'advanced'} onclick={() => mode = 'advanced'}><SlidersHorizontal size={15}/>Advanced Mode</button></div>
      <section class="panel upload-panel"><div class="section-heading"><span class="section-number">01</span><h2>Your source material</h2></div><p class="muted">Start with a classroom map, a scan, or a hand-drawn idea.</p>
        <label class="dropzone" class:has-file={!!project} ondragover={(event) => event.preventDefault()} ondrop={(event) => { event.preventDefault(); if (!busy) void upload(event.dataTransfer?.files[0]); }}>
          <span class="upload-icon"><Upload size={23}/></span><strong>{project ? project.source.filename : 'Choose a map image'}</strong><span>{project ? 'Choose another image to start a new project' : 'or drag and drop it here'}</span><span class="file-hint">PNG, JPG, WebP · up to {status.max_upload_mb} MB</span><input bind:this={fileInput} type="file" accept="image/png,image/jpeg,image/webp" disabled={busy} aria-label="Upload a map image" onchange={() => upload(fileInput.files?.[0])}/>
        </label><div class="privacy-note"><Check size={15}/><span>Temporary by default. Files expire after {status.session_hours} hours.</span></div>
      </section>
      {#if mode === 'advanced'}
        <section class="panel advanced"><div class="section-heading"><SlidersHorizontal size={18}/><h2>Transformation settings</h2></div>
          <fieldset disabled={busy}><legend>Recognition</legend><label>Recognition engine<select bind:value={config.engine}>{#each engines as engine}<option value={engine.id} disabled={!engine.available}>{engine.name}{!engine.available ? ' (not configured)' : ''}</option>{/each}</select></label><label>Document language<select bind:value={config.language}><option value="eng">English</option><option value="fra">French</option><option value="spa">Spanish</option><option value="deu">German</option></select></label><label>Map type<select bind:value={config.map_type}><option value="automatic">Automatic</option><option value="political">Political</option><option value="physical">Physical geography</option><option value="hand-drawn">Hand-drawn</option></select></label><label class="check"><input type="checkbox" bind:checked={config.preprocess}/>Automatic preprocessing</label></fieldset>
          <fieldset disabled={busy}><legend>Content to include</legend><div class="filter-grid">{#each categories as category}<label class="check"><input type="checkbox" value={category} bind:group={config.include}/>{category}</label>{/each}</div><label>Information density<select bind:value={config.density}><option value="low">Low</option><option value="balanced">Balanced</option><option value="high">High</option></select></label><label>Simplification<input type="range" min="0" max="0.03" step="0.001" bind:value={config.simplification}/></label></fieldset>
          <fieldset disabled={busy}><legend>Output</legend><label>Production profile<select bind:value={config.output.profile}><option value="digital">Digital preview</option><option value="print">Printable document</option><option value="swell">Swell paper oriented</option></select></label><div class="field-pair"><label>Page width (mm)<input type="number" min="100" max="420" bind:value={config.output.page_width_mm}/></label><label>Page height (mm)<input type="number" min="100" max="420" bind:value={config.output.page_height_mm}/></label></div><div class="field-pair"><label>Line width (mm)<input type="number" min="0.3" max="5" step="0.1" bind:value={config.output.line_width}/></label><label>Label size<input type="number" min="8" max="40" bind:value={config.output.label_size}/></label></div><div class="field-pair"><label>Spacing target (mm)<input type="number" min="1" max="20" bind:value={config.output.minimum_spacing_mm}/></label><label>Symbol size<input type="number" min="2" max="20" bind:value={config.output.symbol_size}/></label></div><label>Region texture<select bind:value={config.output.texture}><option value="none">None</option><option value="dots">Dots</option><option value="diagonal">Diagonal lines</option></select></label><label class="check"><input type="checkbox" bind:checked={config.output.legend}/>Include legend</label><p class="small muted">High-contrast black-on-white output. Hardware profiles and braille translation are not available in this build.</p></fieldset>
        </section>
      {/if}
      <section class="panel"><div class="section-heading"><span class="section-number">02</span><h2>Make it accessible</h2></div><p class="muted">Identify features and create a simpler, editable representation.</p><div class="engine-note"><Sparkles size={16}/><span>{status.ai_available ? 'AI-assisted analysis is available' : 'Computer vision ready · AI not configured'}</span></div><p class="small muted">{status.ai_available ? 'AI analysis sends this image to OpenAI. Only upload material you are authorized to share.' : 'Outlines are detected locally. Semantic categories require your review or an OpenAI API key.'}</p><button class="primary wide" disabled={!project || busy || !status.enabled} onclick={analyze}>{busy ? 'Processing…' : rep ? 'Analyze again' : 'Analyze & generate'}<ArrowRight size={17}/></button>{#if rep}<p class="small muted">Analyzing again creates a new revision. You can undo it.</p>{/if}
        {#if busy && job}<div class="job-progress"><label for="job-progress">{job.stage}</label><progress id="job-progress" max="100" value={job.progress}></progress><span>{job.progress}%</span></div>{/if}
      </section>
      <div class="guidance"><CircleHelp size={19}/><div><strong>A starting point, shaped by you.</strong><p>Every map needs a human review. Check labels, simplify details, and adapt it with your learner.</p></div></div>
    </aside>
    <div class="main-column">
      <section class="panel preview-panel" aria-labelledby="preview-heading"><div class="preview-header"><div><div class="eyebrow">YOUR WORKSPACE</div><h2 id="preview-heading">{rep ? 'Review your representation' : 'From an image to understanding'}</h2></div>{#if rep}<span class="ready-badge"><Check size={13}/> Ready to review</span>{:else}<span class="small muted">Preview</span>{/if}</div>
        {#if rep && project}
          <div class="preview-toolbar"><label class="check"><input type="checkbox" bind:checked={compare}/>Compare original</label><div class="toolbar-buttons"><button class="icon-button" aria-label="Undo last revision" disabled={busy || project.revision <= 0} onclick={() => history('undo')}><Undo2 size={17}/></button><button class="icon-button" aria-label="Redo revision" disabled={busy || project.revision >= project.latest_revision} onclick={() => history('redo')}><Redo2 size={17}/></button><span class="divider"></span><button class="icon-button" aria-label="Zoom out" onclick={() => zoom = Math.max(0.5, zoom - 0.25)}><ZoomOut size={17}/></button><span class="small">{Math.round(zoom * 100)}%</span><button class="icon-button" aria-label="Zoom in" onclick={() => zoom = Math.min(3, zoom + 0.25)}><ZoomIn size={17}/></button><button class="icon-button" aria-label="Fit map to screen" onclick={() => zoom = 1}><Maximize size={17}/></button></div></div>
          <div class="comparison" class:single={!compare}>{#if compare}<div class="preview-side"><span class="preview-label">ORIGINAL SOURCE</span><div class="image-scroll" tabindex="0" role="group" aria-label="Original map, scroll to pan"><img style:width={`${zoom * 100}%`} src={resource(`/api/v1/projects/${project.id}/source`)} alt="Original uploaded educational map"/></div></div>{/if}<div class="preview-side"><span class="preview-label">ACCESSIBLE REPRESENTATION</span><div class="image-scroll" tabindex="0" role="group" aria-label="Generated map, scroll to pan"><img style:width={`${zoom * 100}%`} src={previewUrl} alt={rep.description}/></div></div></div>
          <div class="description"><div><Map size={18}/><strong>{rep.map_type}</strong><span class="small muted">{visibleCount} visible features</span></div><p>{rep.description}</p></div>
        {:else if project}
          <div class="source-ready"><img src={resource(`/api/v1/projects/${project.id}/source`)} alt="Original uploaded map ready for analysis"/><p>Source uploaded. Select <strong>Analyze & generate</strong> to begin.</p></div>
        {:else}
          <div class="empty-preview"><div class="sample-map" aria-hidden="true"><svg viewBox="0 0 400 270"><defs><pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="#dde5de" stroke-width="0.6"/></pattern></defs><rect width="400" height="270" fill="url(#grid)"/><path d="M85 85 140 47 196 65 241 44 310 92 301 155 330 188 264 218 200 198 152 227 88 188 65 130Z" fill="#e4eadd" stroke="#637e68" stroke-width="2" stroke-linejoin="round"/><path d="m140 47 13 81-65 60m65-60 90 22 21 68m-21-68-2-106m2 106 58 5" fill="none" stroke="#8fa48c" stroke-width="1.5"/><path d="M198 66c-35 42 46 48 5 87s22 35-3 45" fill="none" stroke="#488b95" stroke-width="3"/><circle cx="132" cy="145" r="5" fill="#16665b"/><circle cx="263" cy="108" r="5" fill="#16665b"/><path d="M338 41v26m-5-18 5-8 5 8" stroke="#637e68" fill="none" stroke-width="1.5"/></svg><span class="map-caption">ILLUSTRATIVE MAP</span></div><h3>Every learner deserves a way in.</h3><p>Upload a map to create a clear, customizable<br/>starting point for accessible learning.</p><div class="preview-tags"><span>Editable features</span><span>High contrast</span><span>Tactile-oriented</span></div></div>
        {/if}
        <div class="preview-footer"><span class="small-dot"></span><span>{rep ? 'Review required · no tactile hardware validation' : 'Your original stays unchanged throughout the process'}</span></div>
      </section>
      {#if rep}
        {#if rep.warnings.length}<details class="panel warnings"><summary>{rep.warnings.length} review notes and uncertainties</summary><ul>{#each rep.warnings as warning}<li>{warning}</li>{/each}</ul></details>{/if}
        <section class="panel feedback"><div class="section-heading"><span class="chat-icon"><Sparkles size={19}/></span><div><h2>What do you think?</h2><p class="muted">Tell us what to change. Your map stays editable.</p></div></div><div class="chat-history" role="log" aria-label="Map refinement conversation" aria-live="polite">{#each messages as message}<div class:from-user={message.role === 'You'}><strong>{message.role}</strong><p>{message.text}</p></div>{/each}</div><div class="suggestions">{#each ['Remove the rivers', 'Simplify the map', 'Make labels larger'] as suggestion}<button disabled={busy || !status.enabled} onclick={() => refine(suggestion)}>{suggestion}<ArrowUpRight size={13}/></button>{/each}</div><form onsubmit={(event) => { event.preventDefault(); void refine(); }}><label class="sr-only" for="refinement">Describe a change to your map</label><input id="refinement" bind:value={instruction} placeholder="For example, keep only country borders…" maxlength="1500" disabled={busy || !status.enabled}/><button class="primary" type="submit" disabled={busy || !instruction.trim() || !status.enabled} aria-label="Apply map refinement"><Send size={18}/></button></form><p class="small muted">{status.ai_available ? 'AI proposes validated, reversible edits to your map data.' : 'Common editing commands work locally. Open-ended AI chat requires server configuration.'}</p></section>
        <details class="panel element-editor"><summary>Map elements <span class="small muted">{visibleCount} of {rep.elements.length} visible</span></summary><p class="small muted">Correct categories, edit labels, or hide features. Changes create reversible revisions.</p><div class="element-list">{#each rep.elements as element, index}<div class="element-row"><label class="check"><input type="checkbox" checked={element.visible} disabled={busy} onchange={(event) => editElement(element.id, { visible: event.currentTarget.checked })}/><span class="sr-only">Show element {index + 1}</span></label><input aria-label={`Label for element ${index + 1}`} value={element.label} placeholder={`Feature ${index + 1}`} disabled={busy} onchange={(event) => editElement(element.id, { label: event.currentTarget.value })}/><select aria-label={`Category for element ${index + 1}`} value={element.category} disabled={busy} onchange={(event) => editElement(element.id, { category: event.currentTarget.value })}>{#each categories as category}<option value={category}>{category}</option>{/each}</select><span class="small muted" title={`Provenance: ${element.provenance}`}>{Math.round(element.confidence * 100)}%</span></div>{/each}</div></details>
        <section class="panel export-panel"><div><div class="eyebrow">TAKE IT WITH YOU</div><h2>Ready for the next step.</h2><p class="muted">Download your latest representation.</p></div><div class="export-buttons">{#each ['svg', 'pdf', 'png'] as format}<button class="secondary" disabled={busy} onclick={() => download(format)}><Download size={16}/>{format.toUpperCase()}</button>{/each}</div><p class="small muted full-width">PDF and PNG are visual exports. SVG includes a text description. These files are not certified braille or embosser formats.</p></section>
      {/if}
      {#if preferences.developer}<section class="panel developer"><div class="section-heading"><Code size={19}/><h2>Developer diagnostics</h2></div><p>Processing: <strong>{status.enabled ? 'Enabled' : 'Disabled'}</strong> · OpenAI: {status.ai_available ? 'Configured' : 'Unavailable'}</p><button class="secondary" disabled={busy} onclick={toggleProcessing}>{status.enabled ? 'Disable new processing' : 'Enable processing'}</button><p class="small muted">This public switch affects every visitor. Existing exports remain available.</p>{#if rep}<button class="secondary" onclick={() => guard(async () => { await refresh(); })}>Refresh diagnostics</button><button class="secondary" onclick={copyDiagnostics}>Copy JSON</button><textarea class="diagnostics-json" readonly aria-label="Project diagnostics JSON" value={diagnosticsData || JSON.stringify(rep, null, 2)}></textarea>{/if}<details><summary>Recent API requests</summary><textarea class="diagnostics-json" readonly aria-label="API request log" value={JSON.stringify(diagnostics, null, 2)}></textarea></details></section>{/if}
    </div>
  </div>
  <footer><span>{brand.name} <span class="muted">/ Learning, made more accessible.</span></span><span>Designed for human review. Built for possibility.</span></footer>
</main>

<Dialog.Root bind:open={settingsOpen}><Dialog.Portal><Dialog.Overlay class="dialog-overlay"/><Dialog.Content class="settings-dialog"><div class="dialog-heading"><Dialog.Title class="dialog-title">Application settings</Dialog.Title><Dialog.Close class="icon-button" aria-label="Close settings"><X size={21}/></Dialog.Close></div><Dialog.Description class="muted">Make this workspace work for you. Preferences stay in this browser.</Dialog.Description><div class="settings-fields"><label>Theme<select bind:value={preferences.theme}><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></label><label>Text size: {preferences.textSize}%<input type="range" min="100" max="150" step="10" bind:value={preferences.textSize}/></label><label class="check"><input type="checkbox" bind:checked={preferences.reducedMotion}/>Reduce motion</label><label>Default mode<select bind:value={preferences.mode}><option value="easy">Easy Mode</option><option value="advanced">Advanced Mode</option></select></label><label>Default recognition engine<select bind:value={preferences.engine}>{#each engines as engine}<option value={engine.id} disabled={!engine.available}>{engine.name}</option>{/each}</select></label><label>Default output profile<select bind:value={preferences.profile}><option value="digital">Digital preview</option><option value="print">Printable document</option><option value="swell">Swell paper oriented</option></select></label><label class="check"><input type="checkbox" bind:checked={preferences.developer} onchange={() => { if (rep) void guard(refresh); }}/>Developer Mode</label><p class="small muted">Processing is {status.enabled ? 'enabled' : 'disabled'}. Persistent project storage is not available. Sessions expire after {status.session_hours} hours.</p></div><Dialog.Close class="primary wide">Done</Dialog.Close></Dialog.Content></Dialog.Portal></Dialog.Root>

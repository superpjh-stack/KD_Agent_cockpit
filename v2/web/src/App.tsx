import {useEffect, useRef, useState} from 'react';
import {ArrowUp, BookOpen, Database, History, Mic, Plus, Settings, X, Factory, ArrowUpRight} from 'lucide-react';
import {useRealtimeVoice} from './hooks/useRealtimeVoice';

type Doc = {document_id?: string; filename: string; content: string; status?: string};
type Meta = {demo_data: boolean; source: string; approval_status: string; retrieved_at: string; backend?: string; ai_configured?: boolean};
type Evidence = {tool: string; payload: {result?: unknown}};
type Message = {role: 'user' | 'assistant'; text: string; mode?: string; evidence?: Doc[]; data_evidence?: Evidence[]; meta?: Meta};
type Workspace = {projects: {project_id: string; equipment_type: string; customer: string}[]; tables: {table: string; label: string; count: number}[]; questions: Record<string, string[]>; meta: Meta};
type Past = {question: string; project: string};
function stored<T>(key: string, fallback: T): T {try {return JSON.parse(sessionStorage.getItem(key) || 'null') ?? fallback} catch {return fallback}}
function save(key: string, value: unknown) {try {sessionStorage.setItem(key, JSON.stringify(value))} catch { /* Private browsing may disable storage. */ }}
function Records({value}: {value: unknown}) {
 if (Array.isArray(value) && value.length && typeof value[0] === 'object' && value[0] !== null) {
  const keys = [...new Set(value.flatMap(row => Object.keys(row)))];
  return <div className="table-scroll"><table><thead><tr>{keys.map(key => <th key={key}>{key}</th>)}</tr></thead><tbody>{value.map((row, i) => <tr key={i}>{keys.map(key => <td key={key}>{typeof row[key] === 'object' ? JSON.stringify(row[key]) : String(row[key] ?? '—')}</td>)}</tr>)}</tbody></table></div>;
 }
 if (value && !Array.isArray(value) && typeof value === 'object') return <>{Object.entries(value).map(([key, data]) => <section key={key}><h4>{key}</h4><Records value={data}/></section>)}</>;
 return <p>{Array.isArray(value) ? '조회된 기록이 없습니다.' : String(value ?? '미확인')}</p>;
}
export default function App() {
 const [token, setToken] = useState(() => stored('kgt-access', ''));
 const [workspace, setWorkspace] = useState<Workspace | null>(null), [docs, setDocs] = useState<Doc[]>([]);
 const [project, setProject] = useState(''), [mode, setMode] = useState<'demo'|'ai'>('demo'), [messages, setMessages] = useState<Message[]>([]);
 const [question, setQuestion] = useState(''), [search, setSearch] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState('');
 const [panel, setPanel] = useState(''), [settings, setSettings] = useState(false), [doc, setDoc] = useState<Doc | null>(null);
 const [table, setTable] = useState<{name: string; records: unknown; offset: number} | null>(null), [past, setPast] = useState<Past[]>(() => stored('kgt-history', []));
 const [group, setGroup] = useState('생산·품질');
 const epoch = useRef(0), controller = useRef<AbortController | null>(null), pending = useRef(false), end = useRef<HTMLDivElement>(null), dialog = useRef<HTMLDialogElement>(null);
 const voice = useRealtimeVoice(token, project, turn => setMessages(current => [...current, {...turn, mode: '음성 AI'}]), (name, output) => {
  try {const payload = JSON.parse(output); setMessages(current => [...current, {role: 'assistant', text: '음성 답변에 사용한 조회 근거 · 미승인 샘플', mode: '음성 AI', data_evidence: [{tool: name, payload}]}])} catch { /* Invalid tool output is not evidence. */ }
 });
 async function api(path: string, options: RequestInit = {}) {
  const response = await fetch(path, {...options, headers: {'Content-Type': 'application/json', Authorization: 'Bearer ' + token, ...options.headers}});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '요청을 처리하지 못했습니다.');
  return data;
 }
 useEffect(() => {
  let cancelled = false;
  Promise.all([api('/api/workspace'), api('/api/documents')]).then(([w, d]) => {if (!cancelled) {setWorkspace(w); setDocs(d.documents); setError('')}}).catch(e => {if (!cancelled) setError(e.message)});
  return () => {cancelled = true};
 }, [token]);
 useEffect(() => {end.current?.scrollIntoView({behavior: 'smooth'})}, [messages, busy]);
 useEffect(() => () => {controller.current?.abort(); epoch.current++}, []);
 useEffect(() => {if (doc || table || settings) dialog.current?.showModal(); else dialog.current?.close()}, [doc, table, settings]);
 function closeDialog() {setDoc(null); setTable(null); setSettings(false)}
 function reset(next = project) {
  epoch.current++; controller.current?.abort(); pending.current = false; setBusy(false); setMessages([]); setError(''); setProject(next); voice.stop();
 }
 async function submit(text: string, target = project) {
  if (!text.trim() || pending.current || voice.active) return;
  const history = target === project ? messages.slice(-12).map(({role, text}) => ({role, text: text.slice(0,12000)})) : [];
  if (target !== project) reset(target);
  pending.current = true; setBusy(true); setError(''); setQuestion(''); setPanel('');
  const run = epoch.current, abort = new AbortController(); controller.current = abort;
  setMessages(current => [...current, {role: 'user', text}]);
  const next = [{question: text, project: target}, ...past.filter(item => item.question !== text || item.project !== target)].slice(0,20);
  setPast(next); save('kgt-history', next);
  try {
   const answer = await api('/api/chat', {method: 'POST', signal: abort.signal, body: JSON.stringify({question: text, project_id: target || null, mode, history})});
   if (run === epoch.current) setMessages(current => [...current, {role: 'assistant', ...answer}]);
  } catch (e) {if (run === epoch.current && (e as Error).name !== 'AbortError') setError((e as Error).message)}
  finally {if (run === epoch.current) {pending.current = false; setBusy(false)}}
 }
 async function searchDocs(event: React.FormEvent) {event.preventDefault(); try {setDocs((await api('/api/documents?q=' + encodeURIComponent(search))).documents)} catch (e) {setError((e as Error).message)}}
 async function openTable(name: string, offset = 0) {try {const data = await api(`/api/tables/${name}?offset=${offset}`); setTable({name, records: data.records, offset})} catch (e) {setError((e as Error).message)}}
 const locked = busy || voice.active;
 const voiceStatus: Record<string, string> = {permission: '마이크 권한 확인 중', connecting: '음성 연결 중', listening: '듣고 있습니다', speaking: '질문을 듣고 있습니다', responding: '조회·답변 준비 중', answering: '음성으로 답변 중'};
 return <div className="app">
  <header><div className="brand"><span className="brand-mark"><Factory size={23}/></span><div><strong>경동글로벌텍</strong><small>MANUFACTURING INTELLIGENCE</small></div><span className="version">V2</span></div><div className="header-actions"><span className="demo-tag">검증용 데모</span><button onClick={() => setSettings(true)} aria-label="설정"><Settings size={18}/></button></div></header>
  <nav className="mobile-nav"><button onClick={() => setPanel(panel === 'data' ? '' : 'data')}><BookOpen size={16}/>자료</button><button onClick={() => setPanel(panel === 'questions' ? '' : 'questions')}><History size={16}/>질문</button></nav>
  <div className="layout">
   <aside className={'left panel ' + (panel === 'data' ? 'open' : '')}>
    <div className="panel-heading"><span>WORKSPACE</span><button className="mobile-close" onClick={() => setPanel('')} aria-label="자료 닫기"><X size={18}/></button></div>
    <h2><BookOpen size={18}/>지식베이스</h2><p className="muted">절차와 기준의 근거를 찾아보세요.</p>
    <form onSubmit={searchDocs} className="search"><input aria-label="문서 검색" placeholder="문서 검색" value={search} onChange={e => setSearch(e.target.value)}/><button type="submit">검색</button></form>
    <div className="document-list">{docs.map(item => <button key={item.filename} onClick={() => {setDoc(item); setPanel('')}}><span>{item.document_id || '문서'}</span>{item.filename.replace(/\.md$/, '').replace(/^KGT-KB-\d+_/, '').replaceAll('_', ' ')}<small>샘플 · 미승인</small></button>)}{!docs.length && <p className="muted">검색 결과가 없습니다.</p>}</div>
    <h2 className="data-heading"><Database size={18}/>데이터허브</h2><p className="muted">원본 레코드 · {workspace?.meta.backend || '연결 확인 중'}</p>
    <div className="tables">{workspace?.tables.map(item => <button key={item.table} onClick={() => void openTable(item.table)}>{item.label}<span>{item.count}</span></button>)}</div>
   </aside>
   <main>
    <div className="conversation-top"><div><span className="eyebrow">AGENT CONVERSATION</span><h1>제조 업무 어시스턴트</h1></div><button className="new-chat" onClick={() => reset()}><Plus size={17}/>새 대화</button></div>
    <div className="context-bar"><label>프로젝트<select aria-label="프로젝트" value={project} onChange={e => reset(e.target.value)}><option value="">전체 프로젝트</option>{workspace?.projects.map(item => <option key={item.project_id} value={item.project_id}>{item.project_id} · {item.equipment_type}</option>)}</select></label><span className="context-caption">자재 LOT는 조회 근거에서 확인</span></div>
    <div className="conversation" aria-live="polite">
     {!messages.length && <div className="welcome"><span className="welcome-icon"><Factory size={30}/></span><p className="eyebrow">수주부터 출하까지, 근거와 함께</p><h2>오늘 어떤 업무를<br/>확인할까요?</h2><p>프로젝트 현황, 자재 LOT, 품질 기록을 연결하고<br/>필요한 절차와 원본 근거를 함께 확인하세요.</p><div className="starters">{['납기 지연 공정을 확인해줘', '입고검사 보류 원인을 알려줘', 'FAT 체크리스트를 찾아줘'].map(q => <button key={q} disabled={locked} onClick={() => void submit(q)}>{q}<ArrowUpRight size={16}/></button>)}</div><small>샘플 문서와 가상 데이터로 동작합니다.</small></div>}
     {messages.map((message, i) => <article key={i} className={'message ' + message.role}><div className="message-label">{message.role === 'user' ? '나' : '경동 Agent'}{message.role === 'assistant' && <span>{message.mode === 'demo' ? '정해진 DB·문서 조회' : 'AI 분석'}</span>}</div><div className="answer-text">{message.text}</div>{message.evidence?.map((item, index) => <button className="source" key={index} onClick={() => setDoc(item)}><BookOpen size={14}/>{item.filename}</button>)}{message.data_evidence?.map((item, index) => <details key={index}><summary>원본 데이터 근거 · {item.tool} · 미승인 샘플</summary><Records value={item.payload.result ?? item.payload}/></details>)}{message.meta && <small className="evidence-meta">{message.meta.source} · {message.meta.approval_status} · 조회 {new Date(message.meta.retrieved_at).toLocaleString('ko-KR')}</small>}</article>)}
     {busy && <div className="loading">자료와 근거를 확인하고 있습니다…</div>}<div ref={end}/>
    </div>
    <div className="composer-wrap">
     {(error || voice.error) && <p className="error" role="alert">{error || voice.error}</p>}
     <div className="voice-row"><button disabled={busy || !workspace?.meta.ai_configured} onClick={() => voice.active ? voice.stop() : void voice.start()}><Mic size={16}/>{voice.active ? '음성 종료' : '실시간 음성'}</button>{voice.active && <><button onClick={voice.toggleMute}>{voice.muted ? '음소거 해제' : '음소거'}</button><span role="status" aria-live="polite">{voiceStatus[voice.state] || '음성 연결 중'}</span></>}{voice.needsPlay && <button onClick={() => void voice.play()}>음성 재생</button>}<span className="ai-voice-note">AI 생성 음성</span></div>
     <form className="composer" onSubmit={e => {e.preventDefault(); void submit(question)}}><textarea aria-label="질문 입력" placeholder="프로젝트, 자재, 품질에 대해 질문하세요…" rows={2} maxLength={3000} value={question} onChange={e => setQuestion(e.target.value)} onKeyDown={e => {if(e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {e.preventDefault(); void submit(question)}}}/><div className="composer-bottom"><div className="mode"><button type="button" disabled={locked} className={mode === 'demo' ? 'selected' : ''} onClick={() => {reset(); setMode('demo')}}>데모 조회</button><button type="button" disabled={locked || !workspace?.meta.ai_configured} className={mode === 'ai' ? 'selected' : ''} onClick={() => {reset(); setMode('ai')}}>AI 분석</button></div><button className="send" aria-label="질문 보내기" disabled={locked || !question.trim() || !workspace}><ArrowUp size={19}/></button></div></form><p className="footer-note">미확인 값은 추정하지 않습니다. 승인과 변경은 담당자의 검토가 필요합니다.</p>
    </div>
   </main>
   <aside className={'right panel ' + (panel === 'questions' ? 'open' : '')}><div className="panel-heading"><span>YOUR NEXT QUESTION</span><button className="mobile-close" onClick={() => setPanel('')} aria-label="질문 닫기"><X size={18}/></button></div><h2>추천질문</h2><div className="question-tabs">{['생산·품질', '문서·규칙'].map(item => <button key={item} className={group === item ? 'active' : ''} onClick={() => setGroup(item)}>{item}</button>)}</div><div className="question-list">{workspace?.questions[group]?.map((q, i) => <button key={q} disabled={locked} onClick={() => void submit(q)}><span>{String(i + 1).padStart(2, '0')}</span>{q}</button>)}</div><div className="history-heading"><h2><History size={17}/>질의이력</h2><button onClick={() => {setPast([]); save('kgt-history', [])}}>지우기</button></div>{past.length ? past.map((item, i) => <button className="past" key={i} disabled={locked} onClick={() => void submit(item.question, item.project)}>{item.question}<small>{item.project || '전체 프로젝트'}</small></button>) : <p className="muted">질문을 시작하면 여기에 기록됩니다.</p>}</aside>
  </div>
  <dialog ref={dialog} onCancel={closeDialog}><div className="modal-heading"><h2>{settings ? '연결 설정' : doc ? '지식문서' : '원본 데이터'}</h2><button onClick={closeDialog} aria-label="닫기"><X size={20}/></button></div>{settings ? <><p>API 키는 서버에서 관리합니다. 외부 접속에는 관리자가 발급한 접근 코드를 입력하세요.</p><label>접근 코드<input type="password" aria-label="접근 코드" defaultValue={token} onBlur={e => {const value = e.target.value; reset(); setToken(value); save('kgt-access', value)}}/></label><p className="muted">코드는 현재 브라우저 탭의 세션에 저장됩니다. 입력 후 아래 버튼을 누르면 적용됩니다.</p><button onClick={closeDialog}>적용하고 닫기</button><p>AI 상태: {workspace?.meta.ai_configured ? '서버 키 설정됨 · 호출 검증 전' : '서버 키 설정 필요'}</p></> : doc ? <><h3>{doc.filename}</h3><p className="demo-tag">샘플 문서 · 제조 승인값 아님</p><pre className="document-content">{doc.content || '본문이 제공되지 않았습니다.'}</pre></> : table ? <><h3>{workspace?.tables.find(item => item.table === table.name)?.label}</h3><p className="muted">검증용 가상 데이터 · 원본 단위 그대로 표시</p><Records value={table.records}/><div className="pagination"><button disabled={!table.offset} onClick={() => void openTable(table.name, table.offset - 10)}>이전</button><span>{table.offset + 1}부터 최대 10개</span><button disabled={!Array.isArray(table.records) || table.records.length < 10} onClick={() => void openTable(table.name, table.offset + 10)}>다음</button></div></> : null}</dialog>
 </div>;
}

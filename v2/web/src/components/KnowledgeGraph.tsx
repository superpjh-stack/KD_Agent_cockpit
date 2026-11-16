import {useEffect,useMemo,useRef,useState} from 'react';
import cytoscape,{type Core} from 'cytoscape';
import {request} from '../types';
import './knowledgeGraph.css';
type Node={id:string;kind:string;label:string;table:string;record:Record<string,unknown>};
type Edge={id:string;source:string;target:string;label:string;evidence:{field:string;value:unknown}};
type Graph={project_id:string;nodes:Node[];edges:Edge[];warnings:string[];meta:{source:string;approval_status:string;retrieved_at:string}};
const colors:Record<string,string>={'프로젝트':'#193f50','고객':'#657486','설계·변경':'#7669a8','자재 LOT':'#23897e','공정':'#4386ac','FAT':'#c1873c','구매':'#8a7556','설비 측정':'#527e68','클레임':'#b56168','입고검사':'#b48839'};
export default function KnowledgeGraph({token,workspace,initialProject='',initialKind='',recommendedQuestion='',onProjectChange}:{token:string;initialProject?:string;initialKind?:string;recommendedQuestion?:string;onProjectChange?:(id:string)=>void;workspace:{projects:{project_id:string;customer?:string;equipment_type:string}[]}}){
 const [pid,setPid]=useState(initialProject),[data,setData]=useState<Graph|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [query,setQuery]=useState(''),[kind,setKind]=useState(initialKind),[selected,setSelected]=useState<Node|Edge|null>(null),[reload,setReload]=useState(0);
 const host=useRef<HTMLDivElement>(null),cy=useRef<Core|null>(null);
 useEffect(()=>{setData(null);setSelected(null);setError('');setKind(initialKind);setQuery('');if(!pid){setBusy(false);return}const controller=new AbortController();let active=true;setBusy(true);
 const timer=setTimeout(()=>controller.abort(),20000);
 request<Graph>(token,'/knowledge-graph?project_id='+encodeURIComponent(pid),{signal:controller.signal}).then(d=>{if(active)setData(d)}).catch(e=>{if(active)setError(e.name==='AbortError'?'조회 시간이 초과되었습니다. 다시 시도하세요.':e.message)}).finally(()=>{clearTimeout(timer);if(active)setBusy(false)});
 return()=>{active=false;clearTimeout(timer);controller.abort()};},[pid,token,reload,initialKind]);
 const visible=useMemo(()=>{
 if(!data)return {nodes:[],edges:[]};
 if(!kind)return {nodes:data.nodes,edges:data.edges};
 const ids=new Set(data.nodes.filter(n=>n.kind===kind).map(n=>n.id));
 // Include ancestor paths so inspection filters still show project → LOT → inspection.
 let changed=true;while(changed){changed=false;for(const e of data.edges)if(ids.has(e.target)&&!ids.has(e.source)){ids.add(e.source);changed=true}}
 return {nodes:data.nodes.filter(n=>ids.has(n.id)),edges:data.edges.filter(e=>ids.has(e.source)&&ids.has(e.target))};
 },[data,kind]);
 const matches=visible.nodes.filter(n=>(n.label+' '+n.kind+' '+JSON.stringify(n.record)).toLowerCase().includes(query.toLowerCase()));
 useEffect(()=>{if(!host.current||!data)return;setSelected(null);
 const instance=cytoscape({container:host.current,elements:[...visible.nodes.map(n=>({data:{...n,color:colors[n.kind]||'#657486'}})),...visible.edges.map(e=>({data:e}))],layout:{name:'concentric',padding:40,minNodeSpacing:45,nodeDimensionsIncludeLabels:true,concentric:n=>n.data('kind')==='프로젝트'?2:1,levelWidth:()=>1},minZoom:.15,maxZoom:3,style:[
 {selector:'node',style:{'background-color':'data(color)',label:'data(label)',color:'#203b46','font-size':12,'text-valign':'bottom','text-margin-y':8,'text-wrap':'wrap','text-max-width':'110px',width:32,height:32}},
 {selector:'node[kind = "프로젝트"]',style:{width:48,height:48}},
 {selector:'edge',style:{width:1.5,'line-color':'#bbcbd0','target-arrow-color':'#bbcbd0','target-arrow-shape':'triangle','curve-style':'bezier',label:'','font-size':11,color:'#536d76','text-background-color':'#f8fbfb','text-background-opacity':1,'text-background-padding':'2px'}},
 {selector:'edge:selected',style:{label:'data(label)'}},
 {selector:':selected',style:{'border-width':4,'border-color':'#e6b354','line-color':'#b58736','target-arrow-color':'#b58736'}},
 {selector:'.dimmed',style:{opacity:.17}}, {selector:'.matched',style:{'border-width':4,'border-color':'#e6b354'}}]});
 cy.current=instance;instance.on('tap','node, edge',e=>setSelected(e.target.data() as Node|Edge));
 const observer=new ResizeObserver(()=>{instance.resize();instance.fit(undefined,35)});observer.observe(host.current);
 return()=>{observer.disconnect();instance.destroy();cy.current=null};},[data,visible]);
 useEffect(()=>{const instance=cy.current;if(!instance)return;instance.elements().removeClass('dimmed matched');if(query.trim()){const ids=new Set(matches.map(n=>n.id));instance.nodes().forEach(n=>{n.addClass(ids.has(n.id())?'matched':'dimmed')});instance.edges().addClass('dimmed')}},[query,visible]);
 function focus(n:Node){setSelected(n);const el=cy.current?.getElementById(n.id);if(el){cy.current?.elements().unselect();el.select();cy.current?.center(el)}}
 return <section className="knowledge-graph"><div className="kg-heading"><small>KYUNGDONG / KNOWLEDGE GRAPH V4</small><h1>기록을 연결해, 관계를 읽다.</h1><p>프로젝트와 자재·공정·검사의 연결 근거를 확인하세요.</p></div>
 {recommendedQuestion&&<div className="kg-recommended" role="status"><strong>선택한 추천질문</strong><p>{recommendedQuestion}</p><small>{pid?'관계도와 노드의 원본 기록에서 확인하세요.':'아래에서 확인할 프로젝트를 선택하세요.'}</small></div>}
 <div className="kg-controls"><label>관계도 프로젝트<select value={pid} onChange={e=>{setData(null);setSelected(null);setPid(e.target.value);onProjectChange?.(e.target.value)}}><option value="">프로젝트를 선택하세요</option>{workspace.projects.map(p=><option key={p.project_id} value={p.project_id}>{p.project_id} · {p.customer} · {p.equipment_type}</option>)}</select></label><label>노드 검색<input value={query} onChange={e=>setQuery(e.target.value)} placeholder="LOT, 공정, 검사 결과 검색" disabled={!data}/></label><label>관계 필터<select value={kind} onChange={e=>setKind(e.target.value)} disabled={!data}><option value="">전체 관계</option>{Object.keys(colors).map(k=><option key={k}>{k}</option>)}</select></label></div>
 {busy&&<p role="status">관계와 원본 근거를 조회하고 있습니다…</p>}{error&&<div role="alert">{error} <button onClick={()=>setReload(n=>n+1)}>다시 조회</button></div>}{!pid&&<p className="kg-empty">프로젝트를 선택하면 관계도가 표시됩니다.</p>}
 {data&&<><div className="kg-toolbar"><span role="status">{visible.nodes.length}개 노드 · {visible.edges.length}개 관계</span><div><button onClick={()=>cy.current?.zoom(Math.min(3,(cy.current?.zoom()||1)*1.25))} aria-label="관계도 확대">＋</button><button onClick={()=>cy.current?.zoom(Math.max(.15,(cy.current?.zoom()||1)/1.25))} aria-label="관계도 축소">−</button><button onClick={()=>cy.current?.fit(undefined,35)}>전체 보기</button></div></div>
 <div className="kg-layout"><div><div className="kg-canvas" ref={host} aria-label="프로젝트 지식그래프 관계도"/><div className="kg-legend">{Object.entries(colors).filter(([k])=>visible.nodes.some(n=>n.kind===k)).map(([k,c])=><span key={k}><i style={{background:c}}/>{k}</span>)}</div></div><aside className="kg-detail"><h2>연결 근거</h2>{!selected?<p>노드 또는 연결선을 선택하세요.<br/>아래 목록에서도 선택할 수 있습니다.</p>:<><h3>{selected.label}</h3>{'record' in selected?<><p>{selected.kind} · 원본 {selected.table}</p><dl>{Object.entries(selected.record).map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v===null||v===undefined?'미확인':String(v)}</dd></div>)}</dl></>:<><p>{data.nodes.find(n=>n.id===selected.source)?.label} → {data.nodes.find(n=>n.id===selected.target)?.label}</p><p>연결 필드: {selected.evidence.field}</p><p>일치 값: {String(selected.evidence.value)}</p></>}</>}</aside></div>
 <details className="kg-list" open={!!query}><summary>노드 목록 · 검색 결과 {matches.length}건</summary><div>{matches.map(n=><button key={n.id} onClick={()=>focus(n)}>{n.kind} · {n.label}</button>)}{!matches.length&&<p>일치하는 노드가 없습니다.</p>}</div></details>
 {data.warnings.map(w=><p role="status" key={w}>{w}</p>)}<details className="kg-source"><summary>출처와 연결 기준</summary><p>{data.meta.source} · {data.meta.approval_status}<br/>조회: {new Date(data.meta.retrieved_at).toLocaleString('ko-KR')}</p><p>프로젝트 ID와 자재 LOT의 실제 일치 관계를 표시합니다. 고객은 프로젝트의 고객 필드 기준이며 별도 고객 마스터가 아닙니다. 관계는 원인·공정 순서·승인을 뜻하지 않습니다. 문서의 의미 기반 연결과 자동 추론은 포함하지 않습니다.</p></details></>}
 </section>
}

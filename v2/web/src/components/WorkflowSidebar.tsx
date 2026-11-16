import {useMemo,useState} from 'react';
import {graphQuestions} from '../graphQuestions';
import {reportTitles,type ReportKind} from './ReportPanel';
type Action={question:string;mode:'chat'|'graph';kind?:string};
const groups=['프로젝트 현황','자재·구매 확인','생산·공정 확인','품질·문제 확인','문서·규칙 찾기'];
function category(q:string,source:string){if(source==='지식베이스')return groups[4];if(/FAT|클레임|품질|검사|불합격|불량/.test(q))return groups[3];if(/자재|구매|공급사|발주|LOT/.test(q))return groups[1];if(/공정|공수|설비 측정|작업|용접|레이저/.test(q))return groups[2];return groups[0]}
function readFavorites():Action[]{try{const x=JSON.parse(sessionStorage.getItem('kgt-favorites')||'[]');return Array.isArray(x)?x.filter(a=>typeof a?.question==='string'&&['chat','graph'].includes(a.mode)):[]}catch{return []}}
export default function WorkflowSidebar({questions,locked,onAction,onReport,past,onPast,onClear}:{questions:Record<string,string[]>;locked:boolean;onAction:(action:Action)=>void;onReport:(kind:ReportKind)=>void;past:{question:string;project:string;mode?:'chat'|'graph';kind?:string}[];onPast:(item:{question:string;project:string;mode?:'chat'|'graph';kind?:string})=>void;onClear:()=>void}){
 const [search,setSearch]=useState(''),[opened,setOpened]=useState<string|null>(groups[0]),[favorites,setFavorites]=useState<Action[]>(readFavorites);
 const items=useMemo(()=>[...Object.entries(questions).flatMap(([source,qs])=>qs.map(question=>({question,mode:'chat' as const,group:category(question,source)}))),...graphQuestions.map(a=>({...a,mode:'graph' as const,group:category(a.question,'graph')}))], [questions]);
 const id=(a:Action)=>a.mode+':'+a.question;
 function favorite(a:Action){const next=favorites.some(f=>id(f)===id(a))?favorites.filter(f=>id(f)!==id(a)):[...favorites,a];setFavorites(next);try{sessionStorage.setItem('kgt-favorites',JSON.stringify(next))}catch{/* Private browsing */}}
 function row(a:Action,i:number){const saved=favorites.some(f=>id(f)===id(a));return <div className="workflow-question" key={id(a)}><button className="workflow-ask" disabled={locked} onClick={()=>onAction(a)}><small>{String(i+1).padStart(2,'0')} · {a.mode==='graph'?'관계도':'AI 질문'}</small><span>{a.question}</span></button><button className="favorite-toggle" aria-label={(saved?'즐겨찾기 해제: ':'즐겨찾기 추가: ')+a.question} aria-pressed={saved} onClick={()=>favorite(a)}>{saved?'★':'☆'}</button></div>}
 const filtered=items.filter(a=>a.question.toLowerCase().includes(search.trim().toLowerCase()));
 return <><h2>무엇을 확인할까요?</h2><p className="muted">업무를 선택하고 질문을 눌러보세요.</p><input className="panel-filter" aria-label="추천질문 검색" placeholder="자재, 납기, 검사 검색" value={search} onChange={e=>setSearch(e.target.value)}/>
 {groups.map(g=>{const rows=filtered.filter(a=>a.group===g);return <section className="workflow-group" key={g}><button className="workflow-heading" aria-expanded={!!search||opened===g} onClick={()=>setOpened(opened===g?null:g)}>{g}<span>{rows.length} {search||opened===g?'−':'＋'}</span></button>{(search||opened===g)&&<div>{rows.map(row)}{!rows.length&&<p className="muted">이 업무에 일치하는 질문이 없습니다.</p>}</div>}</section>})}
 <details className="workflow-extra"><summary>보고서 바로 만들기</summary>{(Object.entries(reportTitles) as [ReportKind,string][]).map(([k,title])=><button className="past" disabled={locked} key={k} onClick={()=>onReport(k)}>{title}</button>)}</details>
 <details className="workflow-extra"><summary>즐겨찾기 <span>{favorites.length}</span></summary><p className="muted">현재 브라우저 탭에 저장됩니다.</p>{favorites.map(row)}{!favorites.length&&<p className="muted">질문 옆 ☆을 눌러 저장하세요.</p>}</details>
 <details className="workflow-extra"><summary>최근 질문 <span>{past.length}</span></summary><button onClick={onClear}>이력 지우기</button>{past.map((item,i)=><button className="past" key={i} disabled={locked} onClick={()=>onPast(item)}>{item.question}<small>{item.mode==='graph'?'관계도 · ':''}{item.project||'전체 / 미선택'}</small></button>)}{!past.length&&<p className="muted">아직 질문 이력이 없습니다.</p>}</details></>;
}

export type WakePolicy = {agent_name:string;wake_aliases:string[];require_wake_name:boolean};
export const KGT_WAKE_POLICY:WakePolicy = {agent_name:'경동아',wake_aliases:['경동아'],require_wake_name:false};

export const KGT_VOICE_WAKE_POLICY:WakePolicy = {...KGT_WAKE_POLICY,require_wake_name:true};
export const KGT_VOICE_INTRO = '안녕하세요. 저는 경동에이전트 경동이입니다. 저는 경동글로벌텍 MES 데이터와 지식베이스를 학습해서 경동만의 챗지피티입니다.';

export function callsAgent(text:string, policy:WakePolicy):boolean {
 if(!policy.require_wake_name)return true;
 const normalize=(value:string)=>value.trim().replace(/\s+/gu,' ');
 const aliases=[...new Set([policy.agent_name,...policy.wake_aliases].map(normalize).filter(Boolean))];
 const names=aliases.sort((a,b)=>b.length-a.length).map(value=>value.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|');
 if(!names)return false;
 return new RegExp(`^[\\s"'“‘]*(?:${names})(?=$|[\\s,，.!?。！？:：~～])`,'u').test(normalize(text));
}

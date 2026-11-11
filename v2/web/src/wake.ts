export type WakePolicy = {agent_name:string;wake_aliases:string[];require_wake_name:boolean};
export const KGT_WAKE_POLICY:WakePolicy = {agent_name:'경동아',wake_aliases:['경동아'],require_wake_name:false};

export function callsAgent(text:string, policy:WakePolicy):boolean {
 if(!policy.require_wake_name)return true;
 const normalize=(value:string)=>value.trim().replace(/\s+/gu,' ');
 const aliases=[...new Set([policy.agent_name,...policy.wake_aliases].map(normalize).filter(Boolean))];
 const names=aliases.sort((a,b)=>b.length-a.length).map(value=>value.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|');
 if(!names)return false;
 return new RegExp(`^[\\s"'“‘]*(?:${names})(?=$|[\\s,，.!?。！？:：~～])`,'u').test(normalize(text));
}

const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
if(process.env.KGT_LIVE!=='1')throw new Error('실제 유료 음성 검증은 KGT_LIVE=1로 실행하세요.');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream','--autoplay-policy=no-user-gesture-required']});
 try{
 const context=await browser.newContext({permissions:['microphone']});
 const page=await context.newPage();
 await page.addInitScript(()=>{
  window.voiceEvents=[];window.voiceSent=[];
  const Native=window.RTCPeerConnection;
  window.RTCPeerConnection=class extends Native{
   constructor(...args){super(...args);window.voicePeer=this}
   createDataChannel(...args){const dc=super.createDataChannel(...args);window.voiceChannel=dc;
    const send=dc.send.bind(dc);dc.send=message=>{window.voiceSent.push(JSON.parse(message));send(message)};
    dc.addEventListener('message',e=>{const data=JSON.parse(e.data);if(['response.created','response.done','response.output_audio_transcript.done','output_audio_buffer.stopped','error'].includes(data.type))window.voiceEvents.push(data)});
    return dc;
   }
  };
 });
 if(process.env.KGT_ACCESS)await page.addInitScript(t=>sessionStorage.setItem('kgt-access',JSON.stringify(t)),process.env.KGT_ACCESS);
 await page.goto(process.env.KGT_URL||'http://127.0.0.1:8514');
 await page.getByRole('button',{name:'실시간 음성',exact:true}).click();
 await page.getByText('“경동아”로 불러 질문하세요',{exact:true}).waitFor({timeout:60000});
 const result=await page.evaluate(async()=>{
  const transcripts=window.voiceEvents.filter(e=>e.type==='response.output_audio_transcript.done').map(e=>e.transcript);
  const stats=await window.voicePeer.getStats();let bytes=0,packets=0;stats.forEach(s=>{if(s.type==='inbound-rtp'&&s.kind==='audio'){bytes+=s.bytesReceived||0;packets+=s.packetsReceived||0}});
  return {transcripts,bytes,packets,creates:window.voiceSent.filter(e=>e.type==='response.create').length,errors:window.voiceEvents.filter(e=>e.type==='error').map(e=>e.error?.code)};
 });
 const normalized=x=>x.replace(/[\s.,!?]/g,'');
 const expected='안녕하세요. 저는 경동에이전트 경동이입니다. 저는 경동글로벌텍 MES 데이터와 지식베이스를 학습해서 경동만의 챗지피티입니다.';
 assert.equal(normalized(result.transcripts.join(' ')),normalized(expected));
 assert.equal(result.creates,1);assert(result.bytes>0);assert.deepEqual(result.errors,[]);
 await page.getByRole('button',{name:'음성 종료',exact:true}).click();
 console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e.message);process.exit(1)});

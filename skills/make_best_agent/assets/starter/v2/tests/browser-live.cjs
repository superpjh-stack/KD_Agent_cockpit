// Opt-in: makes real paid AI calls. Uses a supplied synthetic WAV, never a physical microphone.
const fs = require('node:fs');
if (process.env.KGT_LIVE !== '1' || !process.env.KGT_TEST_WAV || !process.env.KGT_URL) {
 console.error('Set KGT_LIVE=1, KGT_URL, and KGT_TEST_WAV to explicitly enable paid verification.');
 process.exit(1);
}
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
if (fs.statSync(process.env.KGT_TEST_WAV).size <= 44) throw Error('Test WAV is empty');
const output = process.env.KGT_LIVE_REPORT || '/tmp/kgt-live-report.json';
(async()=>{
 const report={started_at:new Date().toISOString(),text:[],voice:{},errors:[]};
 let browser, page;
 try {
  browser=await chromium.launch({headless:true,args:['--autoplay-policy=no-user-gesture-required','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',`--use-file-for-fake-audio-capture=${process.env.KGT_TEST_WAV}%noloop`]});
  page=await browser.newPage({viewport:{width:1440,height:1000}});
  await page.addInitScript(()=>{
   const live=window.live={events:[],peers:[],tracks:[],audioContext:null,source:null};
   const NativePeer=window.RTCPeerConnection;
   window.RTCPeerConnection=class extends NativePeer {
    constructor(...args){super(...args);live.peers.push(this)}
    createDataChannel(...args){const dc=super.createDataChannel(...args);dc.addEventListener('message',message=>{
     const e=JSON.parse(message.data);
     // Do not retain credentials, SDP, or raw provider session objects.
     if(!e.type.endsWith('.delta')) console.log('Realtime event',e.type);
     if(!e.type.endsWith('.delta')) live.events.push({type:e.type,name:e.name,transcript:e.transcript,status:e.response?.status,usage:e.response?.usage,error:e.error?.code});
    });return dc}
   };
   const nativeMedia=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
   navigator.mediaDevices.getUserMedia=async constraints=>{
    const stream=await nativeMedia(constraints);live.tracks.push(...stream.getTracks());return stream;
   };
   live.speak=async()=>{};

  });
  page.on('console',msg=>{if(msg.text().startsWith('Realtime event'))console.log(msg.text())});
  page.on('pageerror',e=>report.errors.push(e.message));
  await page.goto(process.env.KGT_URL);
  await page.getByRole('button',{name:'01 프로젝트 공정 진행 현황을 알려줘'}).waitFor();
  const workspace=await page.evaluate(()=>fetch('/api/workspace').then(r=>r.json()));
  if(!workspace.meta.ai_configured)throw Error('Server API key is not configured');
  report.text_model=workspace.meta.model;
  await page.getByLabel('프로젝트',{exact:true}).selectOption('KGT-26001');
  await page.getByRole('button',{name:'AI 분석',exact:true}).click();
  for(const question of (process.env.KGT_SKIP_TEXT === '1' ? [] : ['선택한 프로젝트의 자재 LOT와 부족 재고를 조회하고 원본 수량·단위와 근거를 간단히 알려줘.', 'FAT 체크리스트 문서를 찾아 문서 ID와 확인 항목 두 개만 알려줘.'])) {
   const began=Date.now();
   const answerPromise=page.waitForResponse(r=>r.url().endsWith('/api/chat')&&r.request().method()==='POST',{timeout:180000});
   await page.getByLabel('질문 입력').fill(question);await page.getByLabel('질문 보내기').click();
   const response=await answerPromise;const body=await response.json();
   console.log('Paid text response:', response.status());
   report.text.push({question,http_status:response.status(),elapsed_ms:Date.now()-began,text:body.text,tools:body.data_tools,evidence:body.evidence,data_evidence:body.data_evidence,meta:body.meta,detail:body.detail});
   if(!response.ok()||!body.text||!(body.evidence?.length||body.data_evidence?.length))throw Error('Paid text response missing successful answer/evidence');
   await page.waitForFunction(()=>!document.querySelector('.loading'));
  }
  await page.getByRole('button',{name:'새 대화',exact:true}).click();
  const sessionPromise=page.waitForResponse(r=>r.url().includes('/api/realtime/session'),{timeout:60000});
  await page.getByRole('button',{name:'실시간 음성',exact:true}).click();
  const session=await sessionPromise;report.voice.http_status=session.status();
  if(!session.ok()){report.voice.detail=await session.json();throw Error('Paid Realtime session failed')}
  await page.getByText('듣고 있습니다',{exact:true}).waitFor({timeout:45000});
  report.voice.connected=true;console.log('Real WebRTC connected');
  await page.getByRole('button',{name:'음소거',exact:true}).click();
  report.voice.muted=await page.evaluate(()=>window.live.tracks.every(t=>!t.enabled));
  await page.getByRole('button',{name:'음소거 해제',exact:true}).click();
  report.voice.unmuted=await page.evaluate(()=>window.live.tracks.every(t=>t.enabled));
  await page.evaluate(()=>window.live.speak());console.log('Synthetic Korean audio sent');
  await page.waitForFunction(()=>window.live.events.some(e=>e.type==='conversation.item.input_audio_transcription.completed'),{},{timeout:45000});
  await page.waitForFunction(()=>window.live.events.some(e=>e.type==='response.output_audio_transcript.done'),{},{timeout:60000});
  await page.waitForFunction(()=>window.live.events.some(e=>e.type==='response.function_call_arguments.done'),{},{timeout:30000});
  await page.waitForFunction(()=>document.querySelector('.message details'),{},{timeout:30000});
  await page.waitForFunction(()=>{const events=window.live.events;const tool=events.findIndex(e=>e.type==='response.function_call_arguments.done');const answer=events.findIndex((e,i)=>i>tool&&e.type==='response.output_audio_transcript.done');return tool>=0&&answer>tool&&events.some((e,i)=>i>answer&&e.type==='output_audio_buffer.stopped')},{},{timeout:60000});
  report.voice.events=await page.evaluate(()=>window.live.events);
  report.voice.audio=await page.evaluate(async()=>{
   const stats=await window.live.peers.at(-1).getStats();const rows=[];
   stats.forEach(s=>{if(s.type==='inbound-rtp'&&s.kind==='audio')rows.push({bytesReceived:s.bytesReceived,packetsReceived:s.packetsReceived,totalAudioEnergy:s.totalAudioEnergy})});return rows;
  });
  report.voice.messages=await page.locator('.message').allTextContents();
  await page.screenshot({path:'/tmp/kgt-live-voice.png',fullPage:true});
  await page.getByRole('button',{name:'음성 종료',exact:true}).click();
  report.voice.cleaned_up=await page.evaluate(()=>window.live.tracks.every(t=>t.readyState==='ended')&&window.live.peers.every(p=>p.connectionState==='closed'));
  await page.evaluate(()=>window.live.audioContext?.close());
  if(!report.voice.cleaned_up||!report.voice.muted||!report.voice.unmuted||!report.voice.audio.some(s=>s.bytesReceived>0&&s.totalAudioEnergy>0))throw Error('Voice transport or cleanup check failed');
  report.passed=report.errors.length===0;
 }catch(e){report.passed=false;report.errors.push(e.message);if(page){report.voice.events=await page.evaluate(()=>window.live?.events).catch(()=>[]);report.voice.ui_errors=await page.locator('[role=alert]').allTextContents().catch(()=>[])}}
 finally{if(browser)await browser.close();report.finished_at=new Date().toISOString();fs.writeFileSync(output,JSON.stringify(report,null,2));}
 console.log(JSON.stringify({passed:report.passed,text:report.text.map(t=>({status:t.http_status,elapsed_ms:t.elapsed_ms,tools:t.tools})),voice:{http_status:report.voice.http_status,connected:report.voice.connected,cleaned_up:report.voice.cleaned_up,audio:report.voice.audio},errors:report.errors,report:output}));
 if(!report.passed)process.exitCode=1;
})();

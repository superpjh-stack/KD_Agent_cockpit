const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||undefined});
 try{
 const page=await browser.newPage();
 await page.addInitScript(()=>{
  window.mockState={stopped:0,closed:0,track:null,dc:null,sent:[]};
  Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:async()=>{
   const track={enabled:true,stop(){window.mockState.stopped++}};window.mockState.track=track;
   return {getTracks:()=>[track],getAudioTracks:()=>[track]};
  }});
  window.RTCPeerConnection=class{
   addTrack(){}createDataChannel(){const dc={readyState:'open',send(message){window.mockState.sent.push(JSON.parse(message))},close(){}};window.mockState.dc=dc;return dc}
   async createOffer(){return {type:'offer',sdp:'v=0'}}async setLocalDescription(){}async setRemoteDescription(){window.mockState.dc.onopen()}
   close(){window.mockState.closed++}
  };
 });
 await page.route('**/api/workspace',async route=>{const response=await route.fetch();const data=await response.json();data.meta.ai_configured=true;await route.fulfill({json:data})});
 await page.route('**/api/realtime/session*',route=>route.fulfill({status:502,json:{detail:'테스트 연결 실패'}}));
 await page.goto(process.env.KGT_URL||'http://127.0.0.1:8514');
 await page.getByRole('button',{name:'실시간 음성',exact:true}).click();
 await page.getByText('테스트 연결 실패',{exact:true}).waitFor();
 assert.equal(await page.evaluate(()=>window.mockState.stopped),1);
 await page.unroute('**/api/realtime/session*');
 await page.route('**/api/realtime/session*',route=>route.fulfill({body:'v=0',contentType:'application/sdp'}));
 const emit=async(...events)=>page.evaluate(events=>events.forEach(e=>window.mockState.dc.onmessage({data:JSON.stringify(e)})),events);
 const creates=()=>page.evaluate(()=>window.mockState.sent.filter(e=>e.type==='response.create').length);
 const say=(text,id)=>emit({type:'input_audio_buffer.speech_started',item_id:id},{type:'input_audio_buffer.speech_stopped',item_id:id},{type:'conversation.item.input_audio_transcription.completed',transcript:text,item_id:id});
 await page.getByRole('button',{name:'실시간 음성',exact:true}).click();
 await page.getByText('경동이가 자기소개 중입니다',{exact:true}).waitFor();
 assert.equal(await creates(),1);
 const intro=await page.evaluate(()=>window.mockState.sent.find(e=>e.type==='response.create').response);
 assert.match(intro.instructions,/안녕하세요\. 저는 경동에이전트 경동이입니다\. 저는 경동글로벌텍 MES 데이터와 지식베이스를 학습해서 경동만의 챗지피티입니다\./);
 assert.equal(intro.tool_choice,'none');
 assert.equal(await page.evaluate(()=>window.mockState.track.enabled),false);
 await page.evaluate(()=>window.mockState.dc.onopen());
 assert.equal(await creates(),1,'Introduction repeated');
 await say('경동아, 소개 중 질문','during-intro');
 assert.equal(await creates(),1);
 await emit({type:'response.created',response:{id:'intro'}},{type:'response.output_audio_transcript.done',response_id:'intro',transcript:'안녕하세요. 저는 경동에이전트 경동이입니다.'},{type:'response.done',response:{id:'intro',status:'completed'}});
 assert.equal(await page.evaluate(()=>window.mockState.track.enabled),false,'Mic enabled before playback ended');
 await emit({type:'output_audio_buffer.stopped',response_id:'intro'});
 await page.getByText('“경동아”로 불러 질문하세요',{exact:true}).waitFor();
 assert.equal(await page.evaluate(()=>window.mockState.track.enabled),true);
 for(const [i,text] of ['자재 현황을 알려줘','그럼 납기는?','오늘 경동아라고 불렀어','경동아니야'].entries())await say(text,'ignored-'+i);
 assert.equal(await creates(),1,'Unaddressed speech triggered answer');
 assert.equal(await page.locator('.message.user').count(),0);
 await say('경동아, 자재 현황을 알려줘','accepted-1');
 assert.equal(await creates(),2);
 await emit({type:'conversation.item.input_audio_transcription.completed',transcript:'경동아, 자재 현황을 알려줘',item_id:'accepted-1'});
 assert.equal(await creates(),2,'Duplicate transcript triggered reply');
 await emit({type:'response.created',response:{id:'reply-1'}});
 const cancels=await page.evaluate(()=>window.mockState.sent.filter(e=>e.type==='response.cancel').length);
 await say('주변 사람의 대화','background');
 assert.equal(await creates(),2);
 assert.equal(await page.evaluate(()=>window.mockState.sent.filter(e=>e.type==='response.cancel').length),cancels,'Background speech interrupted answer');
 // An addressed interruption queues until cancellation completes; old events remain isolated.
 await say('경동아, 납기부터 알려줘','accepted-2');
 assert.equal(await creates(),2);
 await emit({type:'response.output_audio_transcript.done',response_id:'reply-1',transcript:'STALE_SPOKEN_ANSWER'},{type:'response.done',response:{id:'reply-1',status:'cancelled'}});
 assert.equal(await creates(),3,'Cancelled response blocked new turn');
 await emit({type:'response.created',response:{id:'reply-2'}});
 let releaseTool;const toolGate=new Promise(r=>releaseTool=r);
 let toolStarted;const started=new Promise(r=>toolStarted=r);
 await page.route('**/api/realtime/tool',async route=>{toolStarted();await toolGate;await route.fulfill({json:{output:JSON.stringify({text:'STALE_TOOL_ANSWER'})}}).catch(()=>{})});
 await emit({type:'response.function_call_arguments.done',response_id:'reply-2',name:'analyze_manufacturing_question',call_id:'slow-call',arguments:'{"question":"경동아, 납기부터 알려줘"}'},{type:'response.done',response:{id:'reply-2',status:'completed'}});
 await started;
 await say('경동아, FAT를 알려줘','accepted-3');
 await emit({type:'response.created',response:{id:'reply-3'}},{type:'response.output_audio_transcript.done',response_id:'reply-3',transcript:'새 질문의 답변입니다.'},{type:'response.done',response:{id:'reply-3',status:'completed'}});
 releaseTool();await page.waitForTimeout(100);
 assert.equal(await page.getByText(/STALE_TOOL_ANSWER|STALE_SPOKEN_ANSWER/).count(),0);
 await page.getByText('새 질문의 답변입니다.',{exact:true}).waitFor();
 await page.getByRole('button',{name:'음소거',exact:true}).click();
 assert.equal(await page.evaluate(()=>window.mockState.track.enabled),false);
 await page.getByRole('button',{name:'음소거 해제',exact:true}).click();
 assert.equal(await page.evaluate(()=>window.mockState.track.enabled),true);
 await page.getByRole('button',{name:'음성 종료',exact:true}).click();
 assert.equal(await page.evaluate(()=>window.mockState.stopped),2);
 const countBefore=await creates();
 await page.getByRole('button',{name:'실시간 음성',exact:true}).click();
 await page.getByText('경동이가 자기소개 중입니다',{exact:true}).waitFor();
 assert.equal(await creates(),countBefore+1);
 await page.evaluate(()=>{window.previousChannel=window.mockState.dc});
 await page.getByLabel('작업 프로젝트',{exact:true}).selectOption('KGT-26001');
 await page.evaluate(()=>window.previousChannel.onmessage({data:JSON.stringify({type:'conversation.item.input_audio_transcription.completed',transcript:'경동아 STALE_VOICE',item_id:'old'})}));
 assert.equal(await page.getByText(/STALE_VOICE/).count(),0);
 assert.equal(await page.evaluate(()=>window.mockState.stopped),3);
 // Text mode still accepts questions without the wake name.
 await page.route('**/api/chat',route=>route.fulfill({json:{text:'호출명 없는 글 질문 응답',mode:'demo'}}));
 await page.getByLabel('질문 입력').fill('자재 현황을 알려줘');
 await page.getByLabel('질문 보내기').click();
 await page.getByText('호출명 없는 글 질문 응답',{exact:true}).waitFor();
 console.log('PASS: intro once/session, playback microphone gate, required wake every voice turn, no background interruption, stale tool/audio isolation, reconnect/project cleanup, text unchanged');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});

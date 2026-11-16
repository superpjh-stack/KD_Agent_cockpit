// Each question maps to relationships supported by the read-only graph API.
export const graphQuestions = [
 {question:'프로젝트에 연결된 고객·자재·공정·검사를 한눈에 보여줘',kind:''},
 {question:'이 프로젝트의 고객은 누구이고 어떤 설비를 제작하나요?',kind:'고객'},
 {question:'프로젝트에 연결된 도면 리비전과 설계변경 기록을 보여줘',kind:'설계·변경'},
 {question:'프로젝트에서 사용하는 자재 LOT와 공급사를 보여줘',kind:'자재 LOT'},
 {question:'자재 LOT별로 연결된 입고검사와 판정 결과를 보여줘',kind:'입고검사'},
 {question:'프로젝트에 연결된 공정과 진행 상태를 보여줘',kind:'공정'},
 {question:'프로젝트의 FAT 검사 항목과 결과·조치 기록을 보여줘',kind:'FAT'},
 {question:'프로젝트에 연결된 구매·발주와 공급사·납기를 보여줘',kind:'구매'},
 {question:'프로젝트의 설비 측정 기록과 측정값·단위를 보여줘',kind:'설비 측정'},
 {question:'프로젝트에 연결된 클레임과 등록된 원인·조치 내용을 보여줘',kind:'클레임'},
] as const;

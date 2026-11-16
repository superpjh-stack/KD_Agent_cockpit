import {apiPath} from './apiPath';
export async function request<T>(token:string,path:string,options:RequestInit={}):Promise<T>{
 const response=await fetch(apiPath('/api'+path),{...options,headers:{'Content-Type':'application/json',Authorization:'Bearer '+token,...options.headers}});
 const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'입력값과 연결 상태를 확인하세요.');return data;
}

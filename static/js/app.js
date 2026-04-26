async function api(url, method='GET', body=null){
  const opts={method,headers:{}}
  if(body){opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(body)}
  const r=await fetch(url,opts)
  if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||r.statusText)}
  return r.json()
}

function fmtDate(iso){
  if(!iso)return '—'
  const d=new Date(iso)
  if(isNaN(d))return '—'
  return ('0'+d.getDate()).slice(-2)+'.'+('0'+(d.getMonth()+1)).slice(-2)+'.'+d.getFullYear()
}
function fmtDateTime(iso){
  if(!iso)return '—'
  const d=new Date(iso)
  if(isNaN(d))return '—'
  return ('0'+d.getDate()).slice(-2)+'.'+('0'+(d.getMonth()+1)).slice(-2)+'.'+d.getFullYear()+' '+
         ('0'+d.getHours()).slice(-2)+':'+('0'+d.getMinutes()).slice(-2)
}
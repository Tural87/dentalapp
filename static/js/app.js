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
  return d.toLocaleDateString('az-AZ',{day:'2-digit',month:'2-digit',year:'numeric'})
}

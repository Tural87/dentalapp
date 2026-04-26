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
function dmyToIso(s){if(!s)return '';const p=s.split('.');return p.length===3&&p[2].length===4?p[2]+'-'+p[1].padStart(2,'0')+'-'+p[0].padStart(2,'0'):s}
function isoToDmy(s){if(!s||s.length<10)return '';return s.slice(8,10)+'.'+s.slice(5,7)+'.'+s.slice(0,4)}
function setDateVal(id,iso){const el=document.getElementById(id);if(el)el.value=isoToDmy(iso)}
function getDateVal(id){return dmyToIso((document.getElementById(id)||{}).value||'')}
function initDateMasks(){
  document.querySelectorAll('input[type=date]').forEach(function(el){
    el.type='text';el.placeholder='GG.AA.YYYY';el.setAttribute('maxlength','10')
    el.addEventListener('input',function(){
      let v=this.value.replace(/\D/g,'')
      if(v.length>2)v=v.slice(0,2)+'.'+v.slice(2)
      if(v.length>5)v=v.slice(0,5)+'.'+v.slice(5)
      this.value=v.slice(0,10)
    })
  })
}
document.addEventListener('DOMContentLoaded', initDateMasks)

function fmtDateTime(iso){
  if(!iso)return '—'
  const d=new Date(iso)
  if(isNaN(d))return '—'
  return ('0'+d.getDate()).slice(-2)+'.'+('0'+(d.getMonth()+1)).slice(-2)+'.'+d.getFullYear()+' '+
         ('0'+d.getHours()).slice(-2)+':'+('0'+d.getMinutes()).slice(-2)
}
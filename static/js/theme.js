// DentalApp Theme JS - toast, theme, mobile, shortcuts

// ── TOAST ────────────────────────────────────────────────────────────────────
(function(){
  if(document.getElementById('toast-container'))return
  const c=document.createElement('div');c.id='toast-container';document.body.appendChild(c)
})()
window.toast=function(msg,type){
  type=type||'info'
  const c=document.getElementById('toast-container');if(!c)return
  const el=document.createElement('div');el.className='toast '+type
  const icons={success:'✓',error:'✕',warning:'⚠',info:'ℹ'}
  el.innerHTML=`<span style="font-size:1.1rem">${icons[type]||'•'}</span><span>${msg}</span>`
  c.appendChild(el)
  setTimeout(()=>{el.classList.add('out');setTimeout(()=>el.remove(),200)},type==='error'?4500:2800)
}
// alert'i toast'a yönləndir (lazımı yerlərdə)
window.toastSuccess=m=>toast(m,'success')
window.toastError=m=>toast(m,'error')

// ── THEME (light/dark) ───────────────────────────────────────────────────────
(function(){
  const saved=localStorage.getItem('theme')
  if(saved==='light')document.body.classList.add('light')
})()
window.toggleTheme=function(){
  document.body.classList.toggle('light')
  const isLight=document.body.classList.contains('light')
  localStorage.setItem('theme',isLight?'light':'dark')
  const btn=document.getElementById('theme-toggle-btn')
  if(btn)btn.textContent=isLight?'🌙':'☀️'
}

// ── MOBILE SIDEBAR ───────────────────────────────────────────────────────────
window.toggleSidebar=function(){
  const sb=document.querySelector('.sidebar')
  if(sb)sb.classList.toggle('open')
}
// Sidebar kənarına klikləyəndə bağla
document.addEventListener('click',function(e){
  const sb=document.querySelector('.sidebar')
  if(!sb||!sb.classList.contains('open'))return
  if(window.innerWidth>768)return
  if(!sb.contains(e.target)&&!e.target.closest('.mobile-toggle')){
    sb.classList.remove('open')
  }
})

// ── KEYBOARD SHORTCUTS ───────────────────────────────────────────────────────
document.addEventListener('keydown',function(e){
  // Esc - aktiv modal'ı bağla
  if(e.key==='Escape'){
    const modals=document.querySelectorAll('.modal-overlay,#newPatientModal,#modal,#stepModal,#userModal,#svcModal,#apModal,#invModal,#addModal,#expModal')
    for(const m of modals){
      if(m.style.display&&m.style.display!=='none'){m.style.display='none';e.preventDefault();return}
    }
  }
  // Ctrl/Cmd+K - axtarış (varsa)
  if((e.ctrlKey||e.metaKey)&&e.key==='k'){
    const s=document.querySelector('#searchInput,#gs-input')
    if(s){e.preventDefault();s.focus();s.select&&s.select()}
  }
})

// ── DOM HAZIR — tema düyməsi və mobil hamburger inject ──────────────────────
document.addEventListener('DOMContentLoaded',function(){
  // Hamburger
  if(!document.querySelector('.mobile-toggle')){
    const b=document.createElement('button')
    b.className='mobile-toggle'
    b.innerHTML='☰'
    b.onclick=toggleSidebar
    document.body.appendChild(b)
  }
  // Theme toggle düyməsini topbar'a əlavə et
  const topbar=document.querySelector('.topbar > div:last-child')
  if(topbar&&!document.getElementById('theme-toggle-btn')){
    const btn=document.createElement('button')
    btn.id='theme-toggle-btn'
    btn.className='theme-toggle'
    btn.title='Tema dəyiş'
    btn.textContent=document.body.classList.contains('light')?'🌙':'☀️'
    btn.onclick=toggleTheme
    topbar.insertBefore(btn,topbar.firstChild)
  }
})

// Köhnə alert'i pərdə şəkildə toast'a çevir (opsional - kommentlə icad edirəm)
// const _alert=window.alert;window.alert=m=>toast(String(m),'info')

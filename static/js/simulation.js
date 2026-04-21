function initSim(){
  const wrap=document.getElementById('sim-wrap')
  const afterDiv=document.getElementById('sim-after-div')
  const handle=document.getElementById('sim-handle')
  if(!wrap||!afterDiv||!handle)return

  let dragging=false
  let pct=50

  function setPos(p){
    pct=Math.max(5,Math.min(95,p))
    afterDiv.style.width=pct+'%'
    handle.style.left=pct+'%'
  }

  setPos(50)

  function onMove(clientX){
    const rect=wrap.getBoundingClientRect()
    setPos((clientX-rect.left)/rect.width*100)
  }

  handle.addEventListener('mousedown',e=>{dragging=true;e.preventDefault()})
  window.addEventListener('mousemove',e=>{if(dragging)onMove(e.clientX)})
  window.addEventListener('mouseup',()=>{dragging=false})

  handle.addEventListener('touchstart',e=>{dragging=true;e.preventDefault()},{passive:false})
  window.addEventListener('touchmove',e=>{if(dragging)onMove(e.touches[0].clientX)},{passive:false})
  window.addEventListener('touchend',()=>{dragging=false})
}

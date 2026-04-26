function initSim(){
  const wrap=document.getElementById('sim-wrap')
  const handle=document.getElementById('sim-handle')
  const afterImg=document.getElementById('sim-after')
  if(!wrap||!handle||!afterImg)return

  function setPos(p){
    p=Math.max(2,Math.min(98,p))
    afterImg.style.clipPath=`inset(0 ${100-p}% 0 0)`
    handle.style.left=p+'%'
  }

  setPos(50)

  function getPos(clientX){
    return (clientX-wrap.getBoundingClientRect().left)/wrap.getBoundingClientRect().width*100
  }

  let drag=false
  wrap.addEventListener('mousedown',e=>{drag=true;setPos(getPos(e.clientX));e.preventDefault()})
  window.addEventListener('mousemove',e=>{if(drag)setPos(getPos(e.clientX))})
  window.addEventListener('mouseup',()=>{drag=false})
  wrap.addEventListener('touchstart',e=>{drag=true;setPos(getPos(e.touches[0].clientX));e.preventDefault()},{passive:false})
  window.addEventListener('touchmove',e=>{if(drag)setPos(getPos(e.touches[0].clientX))},{passive:false})
  window.addEventListener('touchend',()=>{drag=false})
}

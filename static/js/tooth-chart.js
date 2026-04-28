/* Dental chart — occlusal arch, dark bg, inline info panels */
var BASE='/static/img/teeth/'
var TYPE_IMG={molar:BASE+'molar.svg',premolar:BASE+'premolar.svg',canine:BASE+'canine.svg',incisor:BASE+'incisor.svg'}

var STATUS_FILTER={
  healthy:'',
  caries:'sepia(1) hue-rotate(310deg) saturate(5) brightness(1.1)',
  treated:'sepia(1) hue-rotate(185deg) saturate(6) brightness(1.05)',
  implant:'sepia(1) hue-rotate(230deg) saturate(5)',
  crown:'sepia(1) hue-rotate(15deg) saturate(4) brightness(1.15)',
  root_canal:'sepia(1) hue-rotate(290deg) saturate(5) brightness(1.1)',
  missing:'grayscale(1) opacity(0.25)',
  extraction:'grayscale(1) opacity(0.2)'
}
var STATUS_COLOR={healthy:'#60a5fa',caries:'#ff6b6b',treated:'#34d399',implant:'#c084fc',crown:'#fbbf24',root_canal:'#f472b6',missing:'#94a3b8',extraction:'#64748b'}
var LEGEND_COL={healthy:'#60a5fa',caries:'#ff6b6b',treated:'#34d399',implant:'#c084fc',crown:'#fbbf24',root_canal:'#f472b6',missing:'#94a3b8',extraction:'#64748b'}
var LABELS={healthy:'Sağlam',caries:'Karies',treated:'Müalicə edilmiş',implant:'İmplant',crown:'Tac',root_canal:'Kanal müalicəsi',missing:'Çatışmayan',extraction:'Çıxarılmış'}

var UPPER=[28,27,26,25,24,23,22,21,11,12,13,14,15,16,17,18]
var LOWER=[38,37,36,35,34,33,32,31,41,42,43,44,45,46,47,48]

function toothType(n){var d=n%10;if(d>=6)return'molar';if(d===5||d===4)return'premolar';if(d===3)return'canine';return'incisor'}
var TSZ={molar:{w:28,h:26},premolar:{w:23,h:22},canine:{w:20,h:26},incisor:{w:17,h:22}}
var W=420,H=600

function calcPos(nums,isUpper){
  var n=nums.length,cx=210
  var cy=isUpper?5:595,rx=isUpper?185:168,ry=isUpper?245:228
  var a0=isUpper?15:345,a1=isUpper?165:195
  return nums.map(function(num,i){
    var deg=a0+(i/(n-1))*(a1-a0)
    var rad=deg*Math.PI/180
    var x=cx+rx*Math.cos(rad),y=cy+ry*Math.sin(rad)
    var rot=isUpper?deg-90:deg+90
    return{num:num,x:parseFloat(x.toFixed(1)),y:parseFloat(y.toFixed(1)),rot:parseFloat(rot.toFixed(1)),deg:deg}
  })
}

function mkTooth(p,isUpper,td){
  var d=td[p.num]||{},st=d.status||'healthy'
  var t=toothType(p.num),sz=TSZ[t],iw=sz.w,ih=sz.h
  var filt=STATUS_FILTER[st]
  var flip=isUpper?'':'scale(1,-1)'
  var isLeft=p.x<210
  var xmark=''
  if(st==='missing'||st==='extraction')
    xmark='<line x1="-5" y1="-5" x2="5" y2="5" stroke="#9ca3af" stroke-width="2" stroke-linecap="round"/><line x1="5" y1="-5" x2="-5" y2="5" stroke="#9ca3af" stroke-width="2" stroke-linecap="round"/>'

  // Tooth element
  var toothG='<g transform="translate('+p.x+','+p.y+') rotate('+p.rot+')" '
    +'onclick="tcClick('+p.num+')" style="cursor:pointer">'
    +'<g transform="'+flip+'">'
    +'<image href="'+TYPE_IMG[t]+'" x="'+(-(iw/2))+'" y="'+(-(ih/2))+'" width="'+iw+'" height="'+ih+'" '
    +(filt?'style="filter:'+filt+'"':'')+' preserveAspectRatio="xMidYMid meet"/>'
    +(xmark?'<g>'+xmark+'</g>':'')
    +(d.notes?'<circle cx="'+(iw/2-2)+'" cy="'+(-(ih/2)+2)+'" r="2.5" fill="#3b82f6"/>':'')
    +'</g></g>'

  // Number label outside arch
  var numDist=ih*0.5+10
  var numAngleRad=((isUpper?p.deg:p.deg+180)*Math.PI/180)
  var nx=(p.x+numDist*Math.cos(numAngleRad)).toFixed(1)
  var ny=(p.y+numDist*Math.sin(numAngleRad)).toFixed(1)
  var numG='<g transform="translate('+nx+','+ny+')">'
    +'<rect x="-9" y="-6" width="18" height="11" rx="3" fill="rgba(15,30,55,0.75)"/>'
    +'<text x="0" y="4" text-anchor="middle" font-size="7.5" font-weight="800" fill="#e2eaf5" font-family="Inter,system-ui,sans-serif">'+p.num+'</text>'
    +'</g>'

  return toothG+numG
}

// Info panel SVG markup (empty, filled by JS)
function infoPanel(side){
  var x=side==='L'?12:238,y=248,pw=168,ph=114
  return'<g id="tc-info-'+side+'" opacity="0" style="pointer-events:none;transition:opacity .2s">'
    +'<rect x="'+x+'" y="'+y+'" width="'+pw+'" height="'+ph+'" rx="10" fill="rgba(15,30,55,0.92)" stroke="rgba(96,165,250,0.4)" stroke-width="1"/>'
    +'<circle id="tc-dot-'+side+'" cx="'+(x+16)+'" cy="'+(y+20)+'" r="6" fill="#60a5fa"/>'
    +'<text id="tc-num-'+side+'" x="'+(x+28)+'" y="'+(y+25)+'" font-size="13" font-weight="900" fill="#fff" font-family="Inter,system-ui,sans-serif">Diş —</text>'
    +'<text id="tc-st-'+side+'" x="'+(x+10)+'" y="'+(y+50)+'" font-size="10" font-weight="700" fill="#94b8d8" font-family="Inter,system-ui,sans-serif">—</text>'
    +'<text id="tc-nt-'+side+'" x="'+(x+10)+'" y="'+(y+70)+'" font-size="9" fill="#6b8caa" font-family="Inter,system-ui,sans-serif">—</text>'
    +'<rect id="tc-btn-'+side+'" x="'+(x+10)+'" y="'+(y+86)+'" width="'+(pw-20)+'" height="20" rx="6" fill="rgba(59,130,246,0.25)" style="cursor:pointer;pointer-events:all"/>'
    +'<text id="tc-btxt-'+side+'" x="'+(x+pw/2)+'" y="'+(y+100)+'" text-anchor="middle" font-size="9.5" font-weight="700" fill="#93c5fd" font-family="Inter,system-ui,sans-serif" style="cursor:pointer;pointer-events:all">✏️  Redaktə Et</text>'
    +'</g>'
}

function buildChart(teethData){
  var td=teethData||{}
  var upperPos=calcPos(UPPER,true)
  var lowerPos=calcPos(LOWER,false)
  var teeth=upperPos.map(function(p){return mkTooth(p,true,td)}).join('')
    +lowerPos.map(function(p){return mkTooth(p,false,td)}).join('')

  var svg='<svg id="archSVG" viewBox="0 0 '+W+' '+H+'" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-height:calc(100vh - 120px);height:auto;display:block">'
    +'<defs><radialGradient id="bg" cx="50%" cy="50%" r="65%"><stop offset="0%" stop-color="#1e3252"/><stop offset="100%" stop-color="#0b1828"/></radialGradient></defs>'
    +'<rect width="'+W+'" height="'+H+'" fill="url(#bg)"/>'
    +teeth
    +'</svg>'

  var legend='<div style="display:flex;flex-wrap:wrap;gap:5px;padding:8px 12px;justify-content:center;background:#0d1e33;border-top:1px solid rgba(255,255,255,.08)">'
    +Object.keys(LABELS).map(function(k){
      return'<div style="display:inline-flex;align-items:center;gap:4px;font-size:.71rem;font-weight:600;color:#b8d0e8;padding:3px 9px;border-radius:20px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1)">'
        +'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:'+LEGEND_COL[k]+'"></span>'
        +LABELS[k]+'</div>'
    }).join('')
    +'</div>'

  return'<div style="border-radius:14px;overflow:hidden;border:1px solid #1e3a5c;box-shadow:0 4px 24px rgba(0,0,0,.4)">'
    +svg+legend+'</div>'
}

var _tcLastNum=null

window.tcClick=function(num){
  // Second click on same tooth → close
  if(_tcLastNum===num){
    _tcLastNum=null
    var p=document.getElementById('tc-panel')
    if(p)p.style.display='none'
    return
  }
  _tcLastNum=num
  window._tcSelNum=num

  var td=window._tcTeeth||{}
  var d=td[num]||{}
  var st=d.status||'healthy'
  var col=STATUS_COLOR[st]||'#60a5fa'
  var lbl=LABELS[st]||st

  var dot=document.getElementById('tc-dot')
  var numEl=document.getElementById('tc-num')
  var stEl=document.getElementById('tc-st')
  var ntEl=document.getElementById('tc-nt')
  if(dot)dot.style.background=col
  if(numEl)numEl.textContent='Diş '+num
  if(stEl)stEl.textContent=lbl
  if(ntEl)ntEl.textContent=d.notes||'—'

  var panel=document.getElementById('tc-panel')
  if(panel)panel.style.display='block'
}

window.closeTcPanel=function(){
  _tcLastNum=null
  var p=document.getElementById('tc-panel')
  if(p)p.style.display='none'
}

# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""The page a browser gets from `displaydev.remotedisplay`.

It paints RGB565 rectangles from a WebSocket onto a canvas and sends the
pointer, wheel and keys back as small JSON arrays.

Rectangles arrive as binary messages: records of a 16-byte little-endian
header (x, y, w, h, encoding, 0 as six u16, then the data length as a u32)
followed by the data, padded to an even length. Encoding 0 is raw pixels;
1 is runs of (count, pixel); 2 is a JPEG; 3 is a palette (u16 count, u16 0,
the colours) and a 4-bit index per pixel, high nibble first.
Text messages are JSON: ``{"w":..,"h":..,"swap":..}`` starts a session,
``{"auth":1}`` asks for the password (the page answers ``["p", password]``),
``{"bye":"password"}`` says it was wrong, and ``{"bye":"taken"}`` says another
browser took the display.
"""

PAGE = b"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Display</title>
<style>
html,body{margin:0;height:100%;background:#111;color:#bbb;font:15px system-ui,sans-serif;overflow:hidden}
#c{position:absolute;inset:0;margin:auto;max-width:100vw;max-height:100vh;touch-action:none;outline:none;image-rendering:pixelated}
#m{position:fixed;left:0;right:0;top:45%;text-align:center;padding:0 1em}
#f{position:fixed;left:0;right:0;top:35%;text-align:center;display:none}
#f input{font:inherit;padding:.4em;margin:.3em;border-radius:4px;border:1px solid #555;background:#222;color:#eee}
</style></head>
<body><canvas id="c" tabindex="0" width="1" height="1"></canvas><div id="m">Connecting\xe2\x80\xa6</div>
<form id="f"><div>This display needs its password.</div><input id="p" type="password" autocomplete="current-password" placeholder="Password"><input type="submit" value="Show"></form>
<script>
"use strict";
const c=document.getElementById("c"),m=document.getElementById("m"),g=c.getContext("2d");
let img=null,px=null,lut=null,ws=null,taken=false,motion=null,chain=Promise.resolve(),oc=null,pw=null;
const f=document.getElementById("f"),pin=document.getElementById("p");
f.onsubmit=e=>{e.preventDefault();pw=pin.value;f.style.display="none";m.textContent="Connecting\xe2\x80\xa6";
  if(ws&&ws.readyState===1)ws.send(JSON.stringify(["p",pw]));else connect();};
function makeLut(swap){
  lut=new Uint32Array(65536);
  for(let v=0;v<65536;v++){
    const p=swap?((v&255)<<8)|(v>>8):v;
    const r=(p>>11)&31,gr=(p>>5)&63,b=p&31;
    lut[v]=(0xff000000|(((b*527+23)>>6)<<16)|(((gr*259+33)>>6)<<8)|((r*527+23)>>6))>>>0;
  }
}
function start(h){
  c.width=h.w;c.height=h.h;img=g.createImageData(h.w,h.h);
  px=new Uint32Array(img.data.buffer);makeLut(h.swap);
  m.textContent="";c.focus();
}
async function jpeg(buf,o,n,x,y,w,h){
  const bmp=await createImageBitmap(new Blob([new Uint8Array(buf,o,n)],{type:"image/jpeg"}));
  if(!oc)oc=document.createElement("canvas");
  oc.width=w;oc.height=h;const og=oc.getContext("2d",{willReadFrequently:true});og.drawImage(bmp,0,0);
  const s=new Uint32Array(og.getImageData(0,0,w,h).data.buffer),W=c.width;
  for(let r=0;r<h;r++)px.set(s.subarray(r*w,r*w+w),(y+r)*W+x);
}
async function paint(buf){
  if(!px)return;
  const dv=new DataView(buf),W=c.width;
  let o=0,x0=W,y0=c.height,x1=0,y1=0;
  while(o+16<=buf.byteLength){
    const x=dv.getUint16(o,true),y=dv.getUint16(o+2,true),w=dv.getUint16(o+4,true),
          h=dv.getUint16(o+6,true),e=dv.getUint16(o+8,true),n=dv.getUint32(o+12,true);
    const at=o+16;o+=16+((n+1)&~1);
    if(e===2){await jpeg(buf,at,n,x,y,w,h);}
    else if(e===3){
      const b=new Uint8Array(buf,at,n),k=b[0]|(b[1]<<8),pal=new Uint16Array(buf,at+4,k),q=4+2*k;
      let i=0;
      for(let r=0;r<h;r++){let p=(y+r)*W+x;for(let j=0;j<w;j++,i++){const v=b[q+(i>>1)];px[p++]=lut[pal[i&1?v&15:v>>4]];}}
    }
    const d=new Uint16Array(buf,at,(e<2?n:0)>>1);
    if(e===0){
      let i=0;
      for(let r=0;r<h;r++){let p=(y+r)*W+x;for(let q=0;q<w;q++)px[p++]=lut[d[i++]];}
    }else if(e===1){
      let r=0,q=0,p=y*W+x;
      for(let i=0;i<d.length;i+=2){
        let k=d[i];const v=lut[d[i+1]];
        while(k--){px[p++]=v;if(++q===w){q=0;r++;p=(y+r)*W+x;}}
      }
    }
    if(x<x0)x0=x;if(y<y0)y0=y;if(x+w>x1)x1=x+w;if(y+h>y1)y1=y+h;
  }
  if(x1>x0)g.putImageData(img,0,0,x0,y0,x1-x0,y1-y0);
}
function send(a){if(ws&&ws.readyState===1)ws.send(JSON.stringify(a));}
function pos(e){
  const r=c.getBoundingClientRect();
  const x=Math.floor((e.clientX-r.left)*c.width/r.width),y=Math.floor((e.clientY-r.top)*c.height/r.height);
  return [Math.max(0,Math.min(c.width-1,x)),Math.max(0,Math.min(c.height-1,y))];
}
function touch(e){return e.pointerType==="mouse"?0:1;}
c.addEventListener("pointerdown",e=>{
  c.focus();try{c.setPointerCapture(e.pointerId);}catch(_){}
  const p=pos(e);motion=null;send(["d",p[0],p[1],e.button+1,touch(e),e.pointerId]);e.preventDefault();
});
c.addEventListener("pointerup",e=>{
  const p=pos(e);if(motion){send(motion);motion=null;}send(["u",p[0],p[1],e.button+1,touch(e),e.pointerId]);
});
c.addEventListener("pointermove",e=>{
  if(touch(e)&&!e.buttons)return;
  const p=pos(e);motion=["m",p[0],p[1],e.buttons,touch(e),e.pointerId];
});
c.addEventListener("wheel",e=>{
  e.preventDefault();send(["w",Math.sign(e.deltaX),-Math.sign(e.deltaY)]);
},{passive:false});
c.addEventListener("contextmenu",e=>e.preventDefault());
const scrolls=new Set(["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"," ","Tab","Backspace","PageUp","PageDown","Home","End"]);
function key(e,down){
  if(scrolls.has(e.key))e.preventDefault();
  if(down&&e.repeat)return;
  send(["k",down,e.key,e.location,e.ctrlKey?1:0,e.shiftKey?1:0,e.altKey?1:0,e.metaKey?1:0]);
}
c.addEventListener("keydown",e=>key(e,1));
c.addEventListener("keyup",e=>key(e,0));
function tick(){if(motion){send(motion);motion=null;}requestAnimationFrame(tick);}
requestAnimationFrame(tick);
function connect(){
  taken=false;
  ws=new WebSocket((location.protocol==="https:"?"wss://":"ws://")+location.host+"/ws");
  ws.binaryType="arraybuffer";
  ws.onmessage=ev=>{
    if(typeof ev.data!=="string"){const b=ev.data;chain=chain.then(()=>paint(b));return;}
    const msg=JSON.parse(ev.data);
    if(msg.w){f.style.display="none";start(msg);}
    else if(msg.auth){
      // A password this page already gave goes again after a reconnect.
      if(pw!==null)ws.send(JSON.stringify(["p",pw]));
      else{m.textContent="";f.style.display="block";pin.focus();}
    }
    else if(msg.bye==="password"){taken=true;pw=null;m.textContent="That password is wrong.";f.style.display="block";pin.value="";pin.focus();}
    else if(msg.bye){taken=true;m.textContent="Another browser is showing this display now. Reload to take it back.";}
  };
  ws.onclose=()=>{
    if(taken)return;
    m.textContent="Not connected. Trying again\xe2\x80\xa6";setTimeout(connect,2000);
  };
}
connect();
</script></body></html>
"""

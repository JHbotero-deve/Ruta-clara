(function(){
'use strict';
if(typeof window==='undefined')return;
window.barcodeDetector=null;
try{barcodeDetector=null;}catch(error){}
window.onBarcodeDetected=function(){showToast('Los QR y códigos de barras se ignoran. Enfoca únicamente la dirección de entrega.','⚠️');};
window.startBarcodeDetectionLoop=function(){};
let reviewMap=null,reviewMarker=null,reviewResolve=null,reviewReject=null,reviewPointSelected=false,reviewOfflineMap=false;
function el(tag,attrs,text){const node=document.createElement(tag);Object.keys(attrs||{}).forEach(k=>node.setAttribute(k,attrs[k]));if(text!==undefined)node.textContent=text;return node;}
function distanceMeters(a,b){const r=6371000,p=Math.PI/180,dLat=(b[0]-a[0])*p,dLon=(b[1]-a[1])*p,x=Math.sin(dLat/2)**2+Math.cos(a[0]*p)*Math.cos(b[0]*p)*Math.sin(dLon/2)**2;return 2*r*Math.atan2(Math.sqrt(x),Math.sqrt(1-x));}
async function openEntranceReview(parsed,candidates){
return new Promise(async function(resolve,reject){
reviewResolve=resolve;reviewReject=reject;reviewPointSelected=false;reviewMarker=null;
const old=document.getElementById('rcEntranceReview');if(old)old.remove();
const style=el('style');style.id='rcEntranceStyle';style.textContent='#rcEntranceReview{position:fixed;inset:0;z-index:30000;background:#0b1220eF;display:flex;align-items:center;justify-content:center;padding:12px}#rcEntrancePanel{width:min(100%,760px);max-height:96dvh;overflow:auto;background:#fff;color:#172033;border-radius:16px;padding:16px;box-shadow:0 20px 70px #0008}#rcEntrancePanel h2{font-size:19px;margin:0 0 6px}#rcEntrancePanel p{font-size:12px;color:#526078;margin:5px 0 10px}#rcEntrancePanel label{display:block;font-size:12px;font-weight:700;margin:9px 0 4px}#rcEntrancePanel input,#rcEntrancePanel select{width:100%;box-sizing:border-box;padding:10px;border:1px solid #cbd5e1;border-radius:8px;background:white;color:#172033}#rcEntranceMap{height:310px;border-radius:10px;border:1px solid #cbd5e1;margin-top:8px}#rcEntranceWarning{padding:10px;border-radius:8px;background:#fff7ed;color:#9a3412;font-size:12px;margin:9px 0}#rcEntranceActions{display:flex;gap:8px;margin-top:12px}#rcEntranceActions button{flex:1;padding:12px;border:0;border-radius:9px;font-weight:700;cursor:pointer}#rcEntranceConfirm{background:#2563eb;color:white}#rcEntranceCancel{background:#e2e8f0;color:#172033}#rcEntranceCheck{display:flex;gap:8px;align-items:flex-start;font-size:12px;margin-top:10px}#rcEntranceCheck input{width:auto;margin-top:2px}';
document.head.appendChild(style);
const overlay=el('div',{id:'rcEntranceReview'}),panel=el('section',{id:'rcEntrancePanel'});
panel.appendChild(el('h2',{},'Confirmar portería de entrega'));
panel.appendChild(el('p',{},'No se guardará la parada hasta que confirmes el nombre de la unidad, la portería y el punto exacto en el mapa.'));
const address=el('p',{},'Dirección: '+parsed.direccion+' · '+parsed.municipio+(parsed.distrito?' · '+parsed.distrito:''));panel.appendChild(address);
const unitLabel=el('label',{},'Nombre de la unidad, conjunto o establecimiento *');panel.appendChild(unitLabel);
const unitInput=el('input',{id:'rcEntranceUnit',required:'required',maxlength:'150',placeholder:'Ej. Unidad Vizcaya Real 2 o Casa'});unitInput.value=parsed.unidad||'';panel.appendChild(unitInput);
panel.appendChild(el('label',{},'Portería o acceso obligatorio *'));
const gateInput=el('input',{id:'rcEntranceGate',required:'required',maxlength:'150',placeholder:'Ej. Portería principal, acceso por Carrera 32'});panel.appendChild(gateInput);
panel.appendChild(el('label',{},'Coincidencia de dirección (elige una y revisa el pin)'));
const select=el('select',{id:'rcEntranceCandidate'});select.appendChild(el('option',{value:''},'Selecciona una coincidencia o marca el punto en el mapa'));
candidates.forEach(function(item,index){select.appendChild(el('option',{value:String(index)},item.display_name+' · '+(item.type||'ubicación')));});panel.appendChild(select);
panel.appendChild(el('div',{id:'rcEntranceMap','aria-label':'Mapa para marcar la portería'}));
panel.appendChild(el('div',{id:'rcEntranceWarning'},'El geocodificador puede señalar una dirección cercana y no la portería. Mueve el marcador hasta el acceso correcto y confirma visualmente. El límite de 50 metros no se puede certificar solo con GPS o geocodificación.'));
const checkWrap=el('label',{id:'rcEntranceCheck'}),check=el('input',{type:'checkbox',id:'rcEntranceConfirmed'});checkWrap.appendChild(check);checkWrap.appendChild(document.createTextNode('Confirmo que el marcador está en la portería o acceso físico de esta unidad.'));panel.appendChild(checkWrap);
const actions=el('div',{id:'rcEntranceActions'}),cancel=el('button',{id:'rcEntranceCancel',type:'button'},'Cancelar'),confirm=el('button',{id:'rcEntranceConfirm',type:'button'},'Confirmar y guardar');actions.appendChild(cancel);actions.appendChild(confirm);panel.appendChild(actions);overlay.appendChild(panel);document.body.appendChild(overlay);
function close(){if(reviewMap){reviewMap.remove();reviewMap=null;}overlay.remove();const st=document.getElementById('rcEntranceStyle');if(st)st.remove();}
cancel.onclick=function(){close();reject(new Error('Registro cancelado: la ubicación no fue confirmada.'));};
try{
let status={installed:false};try{const res=await fetch('/offline-map/status');if(res.ok)status=await res.json();}catch(e){}
reviewOfflineMap=!!status.installed;
if(!navigator.onLine&&!reviewOfflineMap){document.getElementById('rcEntranceWarning').textContent='Sin conexión: solo podrás confirmar si el mapa de esta zona ya fue cargado y quedó guardado en este dispositivo. Si el mapa no muestra calles y edificios, no guardes la parada.';confirm.disabled=true;confirm.style.opacity='.45';}
reviewMap=L.map('rcEntranceMap',{zoomControl:true,scrollWheelZoom:true}).setView([6.2442,-75.5812],13);
if(reviewOfflineMap)L.tileLayer('/tiles/{z}/{x}/{y}.png',{minZoom:9,maxZoom:19,attribution:'Mapa offline Ruta Clara'}).addTo(reviewMap);
else {const layer=L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'});layer.on('tileload',function(){if(!navigator.onLine){confirm.disabled=false;confirm.style.opacity='1';}});layer.addTo(reviewMap);}
function setPoint(lat,lng){if(reviewMarker){reviewMarker.setLatLng([lat,lng]);}else{reviewMarker=L.marker([lat,lng],{draggable:true}).addTo(reviewMap);reviewMarker.on('dragend',function(){reviewPointSelected=true;});}reviewPointSelected=true;}
select.addEventListener('change',function(){const index=select.value;if(index==='')return;const item=candidates[Number(index)];if(!item)return;setPoint(Number(item.latitude),Number(item.longitude));reviewMap.setView([Number(item.latitude),Number(item.longitude)],18);});
reviewMap.on('click',function(event){setPoint(event.latlng.lat,event.latlng.lng);select.value='';});
if(candidates.length===1){reviewMap.setView([candidates[0].latitude,candidates[0].longitude],17);}
setTimeout(function(){reviewMap.invalidateSize();},250);
confirm.onclick=async function(){
const unit=unitInput.value.trim(),gate=gateInput.value.trim();
if(!unit||!gate){alert('Debes indicar el nombre de la unidad y la portería.');return;}
if(!reviewMarker||!reviewPointSelected){alert('Selecciona una coincidencia o marca manualmente la portería en el mapa.');return;}
if(!check.checked){alert('Confirma que el punto corresponde a la portería.');return;}
const point=reviewMarker.getLatLng();
confirm.disabled=true;confirm.textContent='Guardando...';
try{
await saveLocationAutomatically({name:unit,address:parsed.direccion,latitude:point.lat,longitude:point.lng,neighborhood:parsed.distrito,unit_number:parsed.referencia||null,entrance_name:gate,entrance_confirmed:true,location_source:'manual_porteria',municipality:parsed.municipio,route_id:activeRouteId});
close();resolve(true);
}catch(error){confirm.disabled=false;confirm.textContent='Confirmar y guardar';alert(error.message||'No se pudo guardar la parada.');}
};
}catch(error){close();reject(error);}
});
}
async function lookupCandidates(parsed){
const query=[parsed.direccion,parsed.distrito,parsed.municipio,'Antioquia','Colombia'].filter(Boolean).join(', ');
try{const response=await fetch('/geocode?query='+encodeURIComponent(query));if(!response.ok)return[];const data=await response.json();return Array.isArray(data)?data:[];}catch(error){return[];}
}
window.processParsedGuide=async function(parsed){
if(!parsed||!parsed.direccion)throw new Error('No se reconoció una dirección física. QR, códigos de barras y números de seguimiento no se usan como dirección.');
if(!parsed.municipio)throw new Error('La guía no indica municipio. Completa el municipio antes de ubicar la entrega.');
document.getElementById('guideAddress').value=parsed.direccion;
document.getElementById('guideMunicipality').value=parsed.municipio||'';
document.getElementById('guideDistrict').value=parsed.distrito||'';
document.getElementById('guideReference').value=parsed.referencia||'';
document.getElementById('guideRecipient').value=parsed.unidad||'';
const candidates=await lookupCandidates(parsed);
if(!candidates.length&&!navigator.onLine){const status=await fetch('/offline-map/status').then(r=>r.ok?r.json():{installed:false}).catch(()=>({installed:false}));if(!status.installed)throw new Error('Sin internet no hay mapa offline instalado para ubicar la portería. La guía no se guardó.');}
showToast('Revisa la dirección y marca la portería exacta.','📍');
await openEntranceReview(parsed,candidates);
};
window.handleGuideFormSubmit=async function(event){
event.preventDefault();
const parsed={direccion:document.getElementById('guideAddress').value.trim(),municipio:document.getElementById('guideMunicipality').value.trim(),distrito:document.getElementById('guideDistrict').value.trim(),referencia:document.getElementById('guideReference').value.trim(),unidad:document.getElementById('guideRecipient').value.trim(),tipo:'Residencial'};
if(!parsed.direccion||!parsed.municipio){alert('La dirección y el municipio son obligatorios.');return;}
try{await window.processParsedGuide(parsed);document.getElementById('deliveryGuideForm').reset();showToast('Portería confirmada y parada guardada.','✅');}catch(error){alert(error.message);}
};
const originalSaveLocation=window.saveLocationAutomatically;
if(typeof originalSaveLocation==='function'){
window.saveLocationAutomatically=async function(data){
if(!data||data.entrance_confirmed!==true||!String(data.entrance_name||'').trim())throw new Error('No se puede guardar: debes confirmar el nombre de la portería y el punto exacto en el mapa.');
return originalSaveLocation(data);
};
}
window.captureContinuousStop=function(){
showToast('La ubicación GPS sola no registra entregas. Ingresa la dirección y confirma la portería en el mapa.','⚠️');
const field=document.getElementById('guideAddress');if(field)field.focus();
};
async function syncOfflineLocations(){
if(!navigator.onLine||!sessionStorage.getItem('ruta_clara_token'))return;
let queue;try{queue=JSON.parse(localStorage.getItem('rc_offline_locations')||'[]');}catch(error){queue=[];}
if(!queue.length)return;
const remaining=[];
for(const item of queue){
try{
const payload=Object.assign({},item);delete payload.id;
if(!payload.client_id)payload.client_id=window.crypto?.randomUUID?crypto.randomUUID():'rc-'+Date.now()+'-'+Math.random().toString(36).slice(2);
const response=await window.fetch('/locations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
if(!response.ok)remaining.push(payload);
}catch(error){remaining.push(item);}
}
localStorage.setItem('rc_offline_locations',JSON.stringify(remaining));
}
window.addEventListener('online',syncOfflineLocations);
if(typeof window.loadRouteData==='function'){
const originalLoadRouteData=window.loadRouteData;
window.loadRouteData=async function(){await syncOfflineLocations();return originalLoadRouteData.apply(this,arguments);};
}
const nativeFetch=window.fetch.bind(window);
window.__rcOfflineRouteUsed=false;
window.fetch=async function(input,init){
const url=typeof input==='string'?input:(input&&input.url)||'';
if(url.indexOf('/road_route?')!==-1){
const parsedUrl=new URL(url,location.origin),routeId=parsedUrl.searchParams.get('route_id'),lat=Number(parsedUrl.searchParams.get('start_lat')),lon=Number(parsedUrl.searchParams.get('start_lon')),key='rc_road_route_'+routeId;
try{
const response=await nativeFetch(input,init);
if(response.ok){const data=await response.clone().json();if(data&&data.geometry&&data.origin_included){localStorage.setItem(key,JSON.stringify({data:data,lat:lat,lon:lon,savedAt:Date.now()}));}window.__rcOfflineRouteUsed=false;return response;}
const cached=JSON.parse(localStorage.getItem(key)||'null');
if(cached&&distanceMeters([lat,lon],[cached.lat,cached.lon])<=50){window.__rcOfflineRouteUsed=true;return new Response(JSON.stringify(Object.assign({},cached.data,{offline_cached:true,offline_saved_at:cached.savedAt})),{status:200,headers:{'Content-Type':'application/json'}});}
return response;
}catch(error){
const cached=JSON.parse(localStorage.getItem(key)||'null');
if(cached&&distanceMeters([lat,lon],[cached.lat,cached.lon])<=50){window.__rcOfflineRouteUsed=true;return new Response(JSON.stringify(Object.assign({},cached.data,{offline_cached:true,offline_saved_at:cached.savedAt})),{status:200,headers:{'Content-Type':'application/json'}});}
throw error;
}
}
return nativeFetch(input,init);
};
const status=document.getElementById('routeStatus');
if(status){new MutationObserver(function(){if(window.__rcOfflineRouteUsed&&!status.dataset.offline){status.dataset.offline='1';status.textContent+=' · Ruta vial guardada offline (origen debe coincidir en 50 m)';}else if(!window.__rcOfflineRouteUsed&&status.dataset.offline){delete status.dataset.offline;}}).observe(status,{childList:true,characterData:true,subtree:true});}
document.addEventListener('DOMContentLoaded',function(){const file=document.getElementById('guideImageFile');if(file)file.setAttribute('capture','environment');});
})();
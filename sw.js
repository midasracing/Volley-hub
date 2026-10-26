const CACHE="volley-hub-v40";
const FILES=["./","./index.html","./styles.css","./app.js","./matches-ios.css","./matches-ios.js","./data/tauron.json","./data/tauron1liga.json","./data/pomorska3liga.json","./data/2liga.json","./manifest.webmanifest"];
self.addEventListener("install",event=>{
  event.waitUntil((async()=>{
    const cache=await caches.open(CACHE);
    await Promise.all(FILES.map(async path=>{
      try { await cache.add(path); } catch(error) { console.warn("Precache skipped:",path,error); }
    }));
    await self.skipWaiting();
  })());
});
self.addEventListener("activate",event=>{
  event.waitUntil((async()=>{
    const keys=await caches.keys();
    await Promise.all(keys.filter(key=>key.startsWith("volley-hub-")&&key!==CACHE).map(key=>caches.delete(key)));
    await self.clients.claim();
  })());
});
self.addEventListener("fetch",event=>{
  const request=event.request;
  if(request.method!=="GET") return;
  const url=new URL(request.url);
  if(url.origin!==self.location.origin) return;
  const isData=url.pathname.includes("/data/")&&url.pathname.endsWith(".json");
  // Always ask the network for JSON first. Never return index.html as a fake JSON response.
  if(isData){
    event.respondWith((async()=>{
      try{
        const response=await fetch(request,{cache:"no-store"});
        if(response.ok){
          const cache=await caches.open(CACHE);
          cache.put(request,response.clone()).catch(()=>{});
        }
        return response;
      }catch(error){
        const cached=await caches.match(request,{ignoreSearch:true});
        if(cached) return cached;
        return new Response(JSON.stringify({error:true,error_message:"Brak połączenia z bazą danych."}),{status:503,headers:{"Content-Type":"application/json; charset=utf-8"}});
      }
    })());
    return;
  }
  event.respondWith((async()=>{
    const cached=await caches.match(request);
    if(cached) return cached;
    try{
      const response=await fetch(request);
      if(response.ok){const cache=await caches.open(CACHE);cache.put(request,response.clone()).catch(()=>{});}
      return response;
    }catch(error){
      const fallback=await caches.match("./index.html");
      return fallback||new Response("Offline",{status:503});
    }
  })());
});

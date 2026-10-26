(function(){
  "use strict";
  if(window.__vhHomeIos) return;
  const home=document.getElementById("home");
  if(!home || typeof window.go!=="function") return;
  window.__vhHomeIos=true;
  const originalGo=window.go;
  function sync(target){
    document.body.classList.toggle("ios-home",target==="home");
  }
  window.go=function(target){
    const result=originalGo.apply(this,arguments);
    sync(target);
    return result;
  };
  const observer=new MutationObserver(function(){
    sync(home.classList.contains("active") && !document.body.classList.contains("ios-matches") ? "home" : "");
  });
  observer.observe(home,{attributes:true,attributeFilter:["class"]});
  sync(home.classList.contains("active") ? "home" : "");
})();
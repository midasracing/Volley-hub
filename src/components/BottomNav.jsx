import { memo, useLayoutEffect, useMemo, useRef, useState } from 'react';
import useFluidGlass from '../hooks/useFluidGlass.js';
import { NAV } from '../navigation.js';
import { calculateNavLayout } from './navLayout.js';
import './BottomNav.css';

const CENTER=[0.5,0.5];
// The WebGL image never follows the user's finger or rerenders during tab changes.
// A single DOM layer carries it to the next destination with the same easing as icons.
const StaticGlass=memo(function StaticGlass({width}){
  const Glass=useFluidGlass();
  return Glass?<Glass
    text="" shape="pill" shapes={['pill']} size={width} position={CENTER}
    interaction="static" morphOnClick={false} idle={false} spin={0} wobble={0}
    refraction={1.08} dispersion={0} reflection={0.7} tint={0.08} shadow={0.12}
    color="#ffffff" intro={false} maxDevicePixelRatio={2}
  />:null;
});

function BottomNav({active,onNavigate}){
  const trackRef=useRef(null);
  const [dimensions,setDimensions]=useState(null);
  const activeIndex=Math.max(0,NAV.findIndex(item=>item.id===active));

  useLayoutEffect(()=>{
    const track=trackRef.current;
    if(!track)return undefined;
    const measure=()=>{
      const style=getComputedStyle(track);
      const width=track.clientWidth;
      const padding=parseFloat(style.paddingLeft)||0;
      const gap=parseFloat(style.getPropertyValue('--vh-nav-gap'))||0;
      setDimensions(previous=>
        previous&&Math.abs(previous.width-width)<0.5&&previous.padding===padding&&previous.gap===gap
        ?previous:{width,padding,gap}
      );
    };
    measure();
    const observer=new ResizeObserver(measure);
    observer.observe(track);
    return ()=>observer.disconnect();
  },[]);

  const layout=useMemo(()=>dimensions?calculateNavLayout({
    ...dimensions,activeIndex,count:NAV.length
  }):null,[dimensions,activeIndex]);

  return <nav className="vh-bottom" aria-label="Główna nawigacja">
    <div ref={trackRef} className={'vh-nav-items'+(layout?' is-ready':'')} data-active={active}>
      {layout&&<div className="vh-nav-lens" aria-hidden="true"
        style={{transform:`translate3d(${layout.lens.left}px,0,0)`,width:layout.lens.width}}>
        <StaticGlass width={layout.lens.width}/>
      </div>}
      {NAV.map(({id,label,Icon},index)=>{
        const selected=active===id;
        const slot=layout?.items[index];
        return <button key={id} type="button" aria-label={label}
          aria-current={selected?'page':undefined}
          onClick={()=>onNavigate(id)}
          className={'vh-nav-item'+(selected?' active':'')}
          style={slot?{transform:`translate3d(${slot.left}px,0,0)`,width:slot.width}:{visibility:'hidden'}}>
          <Icon size={23} strokeWidth={selected?2.3:1.8}
            fill={selected&&id==='favorites'?'currentColor':'none'}/>
          <span>{label}</span>
        </button>;
      })}
    </div>
  </nav>;
}

export default memo(BottomNav);

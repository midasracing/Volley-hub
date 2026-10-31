// One immutable layout calculation for buttons and the sliding glass lens.
export function calculateNavLayout({width,padding=7,gap=3,activeIndex,count=4}){
  if(!Number.isFinite(width)||width<=padding*2||activeIndex<0||activeIndex>=count)return null;
  const available=width-padding*2-gap*(count-1);
  if(available<=0)return null;
  const small=available/(count-1+2.5);
  const big=small*2.5;
  const items=Array.from({length:count},(_,index)=>({
    left:padding+index*(small+gap)+(index>activeIndex?big-small:0),
    width:index===activeIndex?big:small
  }));
  return {items,lens:items[activeIndex]};
}

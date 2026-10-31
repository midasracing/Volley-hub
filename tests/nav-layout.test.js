import test from 'node:test';
import assert from 'node:assert/strict';
import {calculateNavLayout} from '../src/components/navLayout.js';

test('dock pills share a stable width and never overlap',()=>{
  for(const width of [286,340,358,390,538,578]){
    for(const gap of [0,3]){
      const widths=[];
      for(let activeIndex=0;activeIndex<4;activeIndex++){
        const layout=calculateNavLayout({width,gap,activeIndex});
        assert.ok(layout);
        widths.push(layout.lens.width);
        assert.equal(layout.lens,layout.items[activeIndex]);
        for(let i=1;i<layout.items.length;i++){
          const previous=layout.items[i-1];
          assert.ok(Math.abs(layout.items[i].left-previous.left-previous.width-gap)<0.00001);
        }
        const last=layout.items.at(-1);
        assert.ok(Math.abs(last.left+last.width-(width-7))<0.00001);
      }
      assert.ok(widths.every(w=>w===widths[0]));
    }
  }
});
test('impossible viewport widths return no layout',()=>{
  assert.equal(calculateNavLayout({width:0,activeIndex:0}),null);
  assert.equal(calculateNavLayout({width:300,activeIndex:9}),null);
});

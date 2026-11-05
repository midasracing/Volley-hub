#!/usr/bin/env python3
"""Generate four genuine Rive RML scenes: a bottom-right to upper-left type serpent.
The source is self-contained, reproducible, and raster/font-free at runtime.
"""
from pathlib import Path
import math
from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.qu2cuPen import Qu2CuPen

W, H, ROWS, STEP, TOP = 390, 844, 24, 48, -154
TITLES = {'home':'DZISIAJ','matches':'KALENDARZ','competitions':'ROZGRYWKI','favorites':'ULUBIONE'}
ROOT = Path(__file__).resolve().parents[1]

def num(value):
    return ('%.2f' % value).rstrip('0').rstrip('.') or '0'

def edge(i,x):
    return TOP+i*STEP + .36*(x-W/2) + 11.5*math.sin(x/W*2.6*math.pi+i*.38)

def polygon(points):
    return '<PointsPath isClosed="true">'+''.join(
        '<StraightVertex x="'+num(x)+'" y="'+num(y)+'"/>' for x,y in points
    )+'</PointsPath>'

def glyph(font, char):
    name=font.getBestCmap()[ord(char)]
    glyph=font.getGlyphSet()[name]
    rec=RecordingPen()
    glyph.draw(Qu2CuPen(rec,max_err=1.5,all_cubic=True))
    curves=[]; points=[]; point=None
    for operation,coords in rec.value:
        if operation=='moveTo':
            if points: curves.append(points)
            points=[coords[0]];point=coords[0]
        elif operation=='lineTo':
            points.append(coords[0]);point=coords[0]
        elif operation=='curveTo':
            for k in range(0,len(coords),3):
                a,b,c=coords[k:k+3];p=point
                for j in range(1,9):
                    t=j/8;u=1-t
                    points.append((u**3*p[0]+3*u*u*t*a[0]+3*u*t*t*b[0]+t**3*c[0],
                                   u**3*p[1]+3*u*u*t*a[1]+3*u*t*t*b[1]+t**3*c[1]))
                point=c
        elif operation in ('closePath','endPath'):
            if len(points)>2: curves.append(points)
            points=[];point=None
    if len(points)>2: curves.append(points)
    return curves

def word(font, title, row):
    units=font['head'].unitsPerEm
    advances=[font['hmtx'][font.getBestCmap()[ord(c)]][0]/units*21 for c in title]
    x=-sum(advances)/2 + .5*(len(title)-1)/2
    paths=[]
    for char,advance in zip(title,advances):
        for contour in glyph(font,char):
            p=[]
            for a,b in contour:
                px=x+a/units*21
                dy=4.5*(math.sin((px+W/2)*2.6*math.pi/W+row*.38)-math.sin(row*.38+1.3*math.pi))
                p.append((px,21*.36-b/units*21+dy))
            paths.append(polygon(p))
        x+=advance-.5
    return ''.join(paths)

def property_keys(name,frames):
    return '<KeyedProperty property="'+name+'">'+''.join(
        '<KeyFrameDouble value="'+num(value)+'" frame="'+str(frame)+
        '" interpolationType="'+('cubic' if ease else 'linear')+'"'+
        (' interpolatorId="0:30"' if ease else '')+'/>' for value,frame,ease in frames
    )+'</KeyedProperty>'

def keyed(id,properties):
    return '<KeyedObject objectId="0:'+str(id)+'">'+''.join(
        property_keys(name,frames) for name,frames in properties.items()
    )+'</KeyedObject>'

def scene(font,title):
    out=['<Rive version="1" kind="fragment">',
        '<Artboard defaultStateMachineId="0:7" styleId="0:5" width="390" height="844" name="Serpent" id="0:2">',
        '<LayoutComponentStyle name="Artboard Style" id="0:5"/>',
        '<CubicEaseInterpolator id="0:30" x1="0.75" y1="0" x2="0.18" y2="1"/>']
    timeline=[]
    for i in range(ROWS):
        node,red,ink=100+i*4,101+i*4,102+i*4
        center=(edge(i,W/2)+edge(i+1,W/2))/2
        top=[(x,edge(i,x)) for x in range(-30,W+60,18)]
        bottom=[(x,edge(i+1,x)) for x in range(W+30,-60,-18)]
        # Text is declared first because the first child is frontmost in Rive.
        out.extend([
          '<Node id="0:'+str(node)+'" name="Wavy row '+str(i)+'">',
          '<Shape id="0:'+str(ink)+'" name="Deforming '+title+'" x="195" y="'+num(center)+'">',
          word(font,title,i),'<Fill><SolidColor colorValue="FF080808"/></Fill></Shape>',
          '<Shape id="0:'+str(red)+'" name="Red wave">',
          polygon(top+bottom),'<Fill><SolidColor colorValue="FFFC0001"/></Fill></Shape>',
          '</Node>'])
        # Each pair launches one Rive frame later. The lower right goes first.
        delay=(ROWS-1-i)//2
        side=1 if i%2 else -1
        pressure=math.sin((i+1)/ROWS*math.pi)
        timeline.append(keyed(node,{
          'x':[(0,0,False),(0,delay+8,False),(side*660,delay+18,True)],
          'y':[(0,0,False),(0,delay+8,False),(-50+side*17,delay+18,True)]
        }))
        timeline.append(keyed(ink,{
          'scaleX':[(1,0,False),(1,delay,False),(2.5+2*pressure,delay+5,False),(1.55,delay+10,False),(1.12,delay+17,False)],
          'scaleY':[(1,0,False),(1,delay,False),(.16,delay+5,False),(1.55,delay+10,False),(.90,delay+17,False)]
        }))
    out+=['<StateMachine name="Serpent" id="0:7"><StateMachineLayer name="Snake" id="0:8">',
         '<AnyState x="0" y="-150"/><ExitState x="400" y="-150"/>',
         '<EntryState x="0" y="0"><StateTransition stateToId="0:12"/></EntryState>',
         '<AnimationState x="220" y="0" animationId="0:6" id="0:12"/>',
         '</StateMachineLayer></StateMachine>',
         '<LinearAnimation duration="30" name="Diagonal snake" id="0:6">',
         *timeline,'</LinearAnimation></Artboard></Rive>']
    return '\n'.join(out)

def main():
    font=TTFont('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
    for slug,title in TITLES.items():
        path=ROOT/'motion'/'route'/slug
        path.mkdir(parents=True,exist_ok=True)
        (path/'rive.yaml').write_text('name: '+slug+'\n',encoding='utf-8')
        content=scene(font,title)
        (path/'scene.rml').write_text(content,encoding='utf-8')
        print(slug, len(content),'bytes, 24 curved Rive ribbons')
if __name__=='__main__':
    main()

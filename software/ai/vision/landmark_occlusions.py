"""Controlled synthetic occlusion labels; geometry-only, not camera confidence."""
import copy
from PIL import ImageDraw
from vision.landmark_renderer import render_landmarks


def render_controlled(seed,catalog,condition,style='rectangle'):
    if condition not in ('standard','appearance_shift','partial','full'):raise ValueError('unknown condition')
    if style not in ('rectangle','ellipse'):raise ValueError('unknown style')
    image,label,mask=render_landmarks(seed,catalog,domain='appearance_shift' if condition=='appearance_shift' else 'standard')
    label=copy.deepcopy(label);label['condition']=condition;label['occluder_style']=style
    if condition in ('partial','full'):
        corner=label['landmarks'][seed%4];x,y=round(corner['x_px']),round(corner['y_px'])
        if condition=='full':box=(x-6,y-6,x+6,y+6)
        elif style=='rectangle':box=(x,y-6,x+8,y+6)
        else:box=(x-1,y-5,x+9,y+5)
        for target,fill in [(image,(35,38,42)),(mask,255)]:
            draw=ImageDraw.Draw(target);getattr(draw,style)(box,fill=fill)
        label['controlled_corner']=seed%4
        for point in label['landmarks']:
            u,v=round(point['x_px']),round(point['y_px'])
            samples=[(u+dx,v+dy) for dy in range(-2,3) for dx in range(-2,3) if dx*dx+dy*dy<=4]
            point['unoccluded_fraction']=sum(0<=a<256 and 0<=b<192 and mask.getpixel((a,b))==0 for a,b in samples)/len(samples)
    return image,label,mask

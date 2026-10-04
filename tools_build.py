# -*- coding: utf-8 -*-
# 为 BigLC 生成素材：白底人物照片 -> 512 透明贴图(png+webp) + parts.js + blur.js
# 主体最长边占画布 FILL（同学要求 <=0.80）
import os, base64, io, json, math
import numpy as np
from PIL import Image, ImageFilter
from collections import deque

SRC = "src"; OUT = os.path.join("assets", "fruits")
SIZE = 512; FILL = 0.78
TIERS = ["grape","cherry","orange","lemon","kiwi","tomato","peach","pineapple","coconut","halfmelon","watermelon"]

def flood_bg(rgb):
    h, w, _ = rgb.shape
    bg = np.zeros((h, w), bool)
    mx = rgb.max(-1); mn = rgb.min(-1)
    cand = ((mx - mn) < 40) & (mn > 170)
    q = deque()
    for x in range(w):
        for y in (0, h-1):
            if cand[y,x] and not bg[y,x]: bg[y,x]=True; q.append((y,x))
    for y in range(h):
        for x in (0, w-1):
            if cand[y,x] and not bg[y,x]: bg[y,x]=True; q.append((y,x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
            ny, nx = y+dy, x+dx
            if 0<=ny<h and 0<=nx<w and not bg[ny,nx] and cand[ny,nx]:
                if np.abs(rgb[ny,nx].astype(int)-rgb[y,x].astype(int)).sum() < 42:
                    bg[ny,nx]=True; q.append((ny,nx))
    return bg

def largest_component(mask):
    h, w = mask.shape
    lab = np.zeros((h,w), np.int32); cur=0; best,bestn=0,0
    for y in range(h):
        for x in range(w):
            if mask[y,x] and lab[y,x]==0:
                cur+=1; n=0; q=deque([(y,x)]); lab[y,x]=cur
                while q:
                    cy,cx=q.popleft(); n+=1
                    for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
                        ny,nx=cy+dy,cx+dx
                        if 0<=ny<h and 0<=nx<w and mask[ny,nx] and lab[ny,nx]==0:
                            lab[ny,nx]=cur; q.append((ny,nx))
                if n>bestn: bestn,best=n,cur
    return lab==best

def fill_holes(mask):
    h,w = mask.shape
    outside = np.zeros((h,w), bool); q=deque()
    for x in range(w):
        for y in (0,h-1):
            if not mask[y,x] and not outside[y,x]: outside[y,x]=True; q.append((y,x))
    for y in range(h):
        for x in (0,w-1):
            if not mask[y,x] and not outside[y,x]: outside[y,x]=True; q.append((y,x))
    while q:
        y,x = q.popleft()
        for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
            ny,nx=y+dy,x+dx
            if 0<=ny<h and 0<=nx<w and not mask[ny,nx] and not outside[ny,nx]:
                outside[ny,nx]=True; q.append((ny,nx))
    return mask | ~outside

def dist_transform(m):
    INF=1e9; h,w=m.shape
    d = np.where(m, INF, 0.0)
    for y in range(h):
        for x in range(w):
            if d[y,x]>0:
                d[y,x]=min(d[y,x], d[y-1,x]+1 if y>0 else INF, d[y,x-1]+1 if x>0 else INF,
                           d[y-1,x-1]+1.414 if y>0 and x>0 else INF, d[y-1,x+1]+1.414 if y>0 and x<w-1 else INF)
    for y in range(h-1,-1,-1):
        for x in range(w-1,-1,-1):
            if d[y,x]>0:
                d[y,x]=min(d[y,x], d[y+1,x]+1 if y<h-1 else INF, d[y,x+1]+1 if x<w-1 else INF,
                           d[y+1,x-1]+1.414 if y<h-1 and x>0 else INF, d[y+1,x+1]+1.414 if y<h-1 and x<w-1 else INF)
    return d

def cover(mask, px_per_unit):
    small = np.array(Image.fromarray((mask*255).astype(np.uint8)).resize((128,128), Image.NEAREST))>127
    d = dist_transform(small)
    covered = np.zeros_like(small); total = small.sum(); parts=[]
    u = (128.0/SIZE*SIZE/512.0)*512/128  # 1 small-px = 4 canvas-px
    u = (4.0/512) * (SIZE*FILL/2) / 1.0  # canvas px -> r 单位：r = SIZE*FILL/2 px
    u = 4.0 / (SIZE*FILL/2)
    while len(parts) < 120:
        cand = np.where(small & ~covered, d, -1)
        y,x = np.unravel_index(np.argmax(cand), cand.shape)
        if cand[y,x] <= 0: break
        rad = d[y,x]
        if rad < 0.6: break
        cy,cx = y+0.5, x+0.5
        parts.append([float((cx-64)*u), float((cy-64)*u), float(rad*u)])
        r2 = (rad+1.0)**2
        for yy in range(max(0,y-int(rad)-2), min(128,y+int(rad)+3)):
            for xx in range(max(0,x-int(rad)-2), min(128,x+int(rad)+3)):
                if small[yy,xx] and (yy+0.5-cy)**2+(xx+0.5-cx)**2 <= r2: covered[yy,xx]=True
        if (small & covered).sum() / total >= 0.995: break
    rb = round(float(max(math.hypot(px,py)+pr for px,py,pr in parts)), 3)
    return {"parts": [[round(v,3) for v in p] for p in parts], "rb": rb}

shapes=[]; mats=[]
for i, tier in enumerate(TIERS, 1):
    im = Image.open(os.path.join(SRC, f"{i}.png")).convert("RGB")
    rgb = np.array(im)
    bg = flood_bg(rgb)
    subj = fill_holes(largest_component(~bg))
    m = Image.fromarray((subj*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5))
    alpha = np.array(m)
    out = np.dstack([rgb, alpha])
    ys, xs = np.where(alpha > 128)
    crop = out[ys.min():ys.max()+1, xs.min():xs.max()+1]
    ch, cw = crop.shape[:2]
    scale = SIZE*FILL/max(ch, cw)
    nh, nw = max(1,round(ch*scale)), max(1,round(cw*scale))
    im2 = Image.fromarray(crop, "RGBA").resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (0,0,0,0))
    canvas.paste(im2, ((SIZE-nw)//2, (SIZE-nh)//2), im2)
    canvas.save(os.path.join(OUT, f"{i:02d}-{tier}.png"), optimize=True)
    canvas.save(os.path.join(OUT, f"{i:02d}-{tier}.webp"), quality=90, method=6)
    mats.append(canvas)
    mask = np.array(canvas)[...,3] > 32
    s = cover(mask, None)
    shapes.append(s)
    print(i, tier, f"主体 {cw}x{ch} -> 画布内 {nw}x{nh}", "circles:", len(s["parts"]), "rb:", s["rb"])

with open(os.path.join(OUT,"parts.js"),"w") as f:
    f.write("window.SUIKA_PARTS = " + json.dumps(shapes, separators=(",",":")) + ";")

strip = Image.new("RGBA", (32*11, 32), (0,0,0,0))
for i in range(11):
    im = mats[i].resize((32,32), Image.LANCZOS)
    strip.paste(im, (i*32, 0), im)
strip = strip.filter(ImageFilter.GaussianBlur(2))
buf = io.BytesIO(); strip.save(buf, "WEBP", quality=40)
b64 = base64.b64encode(buf.getvalue()).decode()
with open(os.path.join(OUT,"blur.js"),"w") as f:
    f.write("window.FRUIT_BLUR = {\n  src: 'data:image/webp;base64,%s',\n  cell: 32,\n  cols: 11\n};\n" % b64)
print("完成")

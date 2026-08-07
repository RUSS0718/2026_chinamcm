def audit_layout(instance, layout, outline=None):
    placed={}; boxes={}; polygons={}
    for n,b in instance.blocks.items():
        x,y,r=layout[n]
        def turn(px,py):
            if r%360==0: return px,py
            if r%360==90: return -py,px
            if r%360==180: return -px,-py
            if r%360==270: return py,-px
            raise ValueError('rotation must be a multiple of 90')
        raw=[turn(px,py) for px,py in b.polygon]; low_x=min(px for px,py in raw); low_y=min(py for px,py in raw)
        polygons[n]=[(x+px-low_x,y+py-low_y) for px,py in raw]
        w=max(px for px,py in polygons[n])-x; h=max(py for px,py in polygons[n])-y
        placed[n]=(x,y,w,h); boxes[n]=(x,y,x+w,y+h)
    def overlap(first,second):
        ys=sorted({y for p in (first,second) for x,y in p})
        total=0
        def intervals(poly,mid):
            cross=[]
            for (x1,y1),(x2,y2) in zip(poly,poly[1:]+poly[:1]):
                if x1==x2 and min(y1,y2)<mid<max(y1,y2): cross.append(x1)
            cross.sort(); return zip(cross[::2],cross[1::2])
        for lo,hi in zip(ys,ys[1:]):
            for a,b in intervals(first,(lo+hi)/2):
                for c,d in intervals(second,(lo+hi)/2): total += max(0,min(b,d)-max(a,c))*(hi-lo)
        return total
    legal=True; names=list(boxes)
    for i,a in enumerate(names):
        for c in names[i+1:]:
            legal &= overlap(polygons[a],polygons[c]) == 0
    if outline:
        ox,oy,ow,oh=outline; W,H=ow,oh; legal &= all(x>=ox and y>=oy and x+w<=ox+ow and y+h<=oy+oh for x,y,w,h in placed.values())
    else:
        W=max(x+w for x,y,w,h in placed.values())-min(x for x,y,w,h in placed.values()); H=max(y+h for x,y,w,h in placed.values())-min(y for x,y,w,h in placed.values())
    def area(poly): return abs(sum(x1*y2-x2*y1 for (x1,y1),(x2,y2) in zip(poly,poly[1:]+poly[:1])))/2
    area=sum(area(poly) for poly in polygons.values()); dead=W*H-area
    hpwl=0
    for net in instance.nets:
        pts=[]
        for pin in net.pins:
            if pin in placed:
                x,y,w,h=placed[pin]; pts.append((x+w/2,y+h/2))
            elif pin in instance.terminals: pts.append(instance.terminals[pin])
        if pts: hpwl += max(x for x,y in pts)-min(x for x,y in pts)+max(y for x,y in pts)-min(y for x,y in pts)
    return {'legal':bool(legal),'W':W,'H':H,'area':area,'aspect_ratio':max(W,H)/min(W,H) if min(W,H) else float('inf'),'rho':dead/(W*H) if W*H else 0,'deadspace':dead,'HPWL':hpwl,'square_side':max(W,H)}

def rotate_polygon(poly, angle, origin=(0,0)):
    if angle % 360 == 0: return list(poly)
    ox, oy = origin; a = angle % 360
    if a == 90: return [(ox-(y-oy), oy+(x-ox)) for x,y in poly]
    if a == 180: return [(2*ox-x, 2*oy-y) for x,y in poly]
    if a == 270: return [(ox+(y-oy), oy-(x-ox)) for x,y in poly]
    raise ValueError('angle must be a multiple of 90')

def normalized_rotation(poly, angle):
    """Rotate an orthogonal block, then restore its lower-left anchor to (0, 0)."""
    rotated = rotate_polygon(poly, angle)
    min_x = min(x for x, y in rotated); min_y = min(y for x, y in rotated)
    return [(x-min_x, y-min_y) for x, y in rotated]

def polygon_area(poly):
    return abs(sum(x1*y2-x2*y1 for (x1,y1),(x2,y2) in zip(poly,poly[1:]+poly[:1])))/2

def _rect(poly):
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)

def polygon_overlap_area(a, b):
    ys=sorted(set([y for x,y in a]+[y for x,y in b])); total=0
    def spans(poly,y):
        xs=[]
        for (x1,y1),(x2,y2) in zip(poly,poly[1:]+poly[:1]):
            if y1==y2: continue
            if min(y1,y2) < y < max(y1,y2): xs.append(x1+(y-y1)*(x2-x1)/(y2-y1))
        xs.sort(); return list(zip(xs[::2],xs[1::2]))
    for y1,y2 in zip(ys,ys[1:]):
        if y2<=y1: continue
        sa,sb=spans(a,(y1+y2)/2),spans(b,(y1+y2)/2)
        for l1,r1 in sa:
            for l2,r2 in sb: total += max(0,min(r1,r2)-max(l1,l2))*(y2-y1)
    return total

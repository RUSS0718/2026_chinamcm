from dataclasses import dataclass
from .geometry import normalized_rotation, polygon_overlap_area, polygon_area

@dataclass
class Positioned:
    x: float; y: float; width: float; height: float; center: tuple

@dataclass
class Evaluation:
    legal: bool; width: float; height: float; area: float; module_area: float; dead_space_ratio: float; aspect_ratio: float; rho: float; deadspace: float; hpwl: float; square_side: float; blocks: dict
    def as_dict(self): return {'legal':self.legal,'W':self.width,'H':self.height,'area':self.area,'module_area':self.module_area,'dead_space_ratio':self.dead_space_ratio,'aspect_ratio':self.aspect_ratio,'rho':self.rho,'deadspace':self.deadspace,'HPWL':self.hpwl,'square_side':self.square_side}

def evaluate(instance, layout, outline=None):
    placed = {}; polys = {}
    for name, block in instance.blocks.items():
        x,y,r = layout[name]; local = normalized_rotation(list(block.polygon), r)
        w=max(px for px,py in local); h=max(py for px,py in local)
        placed[name] = Positioned(x,y,w,h,(x+w/2,y+h/2)); polys[name] = [(x+px,y+py) for px,py in local]
    legal = True
    names = list(polys)
    for i,a in enumerate(names):
        for b in names[i+1:]: legal &= polygon_overlap_area(polys[a],polys[b]) == 0
    minx=min(p.x for p in placed.values()); miny=min(p.y for p in placed.values()); maxx=max(p.x+p.width for p in placed.values()); maxy=max(p.y+p.height for p in placed.values())
    if outline:
        ox,oy,ow,oh=outline; legal &= all(p.x >= ox and p.y >= oy and p.x+p.width <= ox+ow and p.y+p.height <= oy+oh for p in placed.values()); W,H=ow,oh
    else: W,H=maxx-minx,maxy-miny
    area=W*H; module_area=sum(polygon_area(poly) for poly in polys.values()); deadspace=area-module_area
    dead_space_ratio=deadspace/module_area if module_area else 0; rho=deadspace/area if area else 0
    hpwl=0
    for net in instance.nets:
        pts=[]
        for pin in net.pins:
            if pin in placed: pts.append(placed[pin].center)
            elif pin in instance.terminals: pts.append(instance.terminals[pin])
        if pts: hpwl += max(x for x,y in pts)-min(x for x,y in pts)+max(y for x,y in pts)-min(y for x,y in pts)
    aspect_ratio=max(W,H)/min(W,H) if min(W,H) else float('inf')
    return Evaluation(bool(legal),W,H,area,module_area,dead_space_ratio,aspect_ratio,rho,deadspace,hpwl,max(W,H),placed)

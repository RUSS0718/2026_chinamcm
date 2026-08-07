from dataclasses import dataclass
import re

@dataclass(frozen=True)
class Block:
    name: str
    width: float
    height: float
    polygon: tuple
    center_pin: tuple = (0.0, 0.0)

@dataclass(frozen=True)
class Net:
    name: str
    pins: tuple

@dataclass(frozen=True)
class Instance:
    blocks: dict
    terminals: dict
    declared_terminal_names: tuple
    nets: tuple
    declared_blocks: int
    declared_terminals: int
    declared_nets: int
    declared_pins: int

def _num(s):
    return float(s) if any(c in s for c in '.eE') else int(s)

def parse_instance_text(blocks_text, nets_text, pl_text):
    bl = {}; terminal_names = []; declared_b = declared_t = 0
    for line in blocks_text.splitlines():
        m = re.match(r'NumHardBlocks\s*:\s*(\d+)', line); declared_b = int(m.group(1)) if m else declared_b
        m = re.match(r'NumTerminals\s*:\s*(\d+)', line); declared_t = int(m.group(1)) if m else declared_t
        m = re.match(r'(\S+)\s+block\s+\d+\s+(.+)', line)
        if m:
            vals = re.findall(r'\((-?[\d.]+),\s*(-?[\d.]+)\)', m.group(2))
            poly = tuple((_num(x), _num(y)) for x,y in vals)
            xs, ys = zip(*poly)
            bl[m.group(1)] = Block(m.group(1), max(xs)-min(xs), max(ys)-min(ys), poly)
        m = re.match(r'(\S+)\s+terminal\s*$', line)
        if m:
            terminal_names.append(m.group(1))
    terms = {}
    for line in pl_text.splitlines():
        p = line.split()
        if len(p) >= 3:
            name, x, y = p[:3]
            if name not in bl: terms[name] = (_num(x), _num(y))
    declared_n = declared_p = 0; nets = []; lines = iter(nets_text.splitlines())
    for line in lines:
        m = re.match(r'NumNets\s*:\s*(\d+)', line); declared_n = int(m.group(1)) if m else declared_n
        m = re.match(r'NumPins\s*:\s*(\d+)', line); declared_p = int(m.group(1)) if m else declared_p
        m = re.match(r'NetDegree\s*:\s*(\d+)', line)
        if m:
            degree = int(m.group(1)); name = f'net_{len(nets)+1:06d}'
            pins=[]
            while len(pins) < degree:
                p = next(lines).strip()
                if p: pins.append(p)
            nets.append(Net(name, tuple(pins)))
    return Instance(bl, terms, tuple(terminal_names), tuple(nets), declared_b, declared_t, declared_n, declared_p)

def parse_instance_files(blocks_path, nets_path, pl_path):
    return parse_instance_text(*[p.read_text(encoding='utf-8') for p in (blocks_path,nets_path,pl_path)])

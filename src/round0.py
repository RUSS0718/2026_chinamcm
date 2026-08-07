"""第0轮：解析、共享指标评价和独立审计。"""
import argparse, hashlib, json
from pathlib import Path
from ._internal.parser import parse_instance_files

def audit_files(raw_dir, processed_dir):
    raw_dir, processed_dir = Path(raw_dir), Path(processed_dir); processed_dir.mkdir(parents=True, exist_ok=True)
    all_files=[]
    for path in sorted(raw_dir.parent.rglob('*')):
        if path.is_file():
            all_files.append({'file':path.relative_to(raw_dir.parent.parent).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    rows=[]
    for stem in ('n100','n200','n300'):
        paths=[raw_dir/f'{stem}{ext}' for ext in ('.blocks','.nets','.pl')]
        inst=parse_instance_files(*paths)
        hashes=[]
        for p in paths:
            h=hashlib.sha256(p.read_bytes()).hexdigest(); hashes.append({'file':p.relative_to(raw_dir.parent.parent).as_posix(),'bytes':p.stat().st_size,'sha256':h})
        block_refs={p for n in inst.nets for p in n.pins if p in inst.blocks}; term_refs={p for n in inst.nets for p in n.pins if p in inst.terminals}
        missing=sorted({p for n in inst.nets for p in n.pins if p not in inst.blocks and p not in inst.terminals})
        missing_terminal_positions=sorted(set(inst.declared_terminal_names)-set(inst.terminals))
        extra_terminal_positions=sorted(set(inst.terminals)-set(inst.declared_terminal_names))
        degree_sum=sum(len(n.pins) for n in inst.nets)
        rows.append({'instance':stem,'declared_blocks':inst.declared_blocks,'actual_blocks':len(inst.blocks),'declared_terminals':inst.declared_terminals,'actual_terminals':len(inst.terminals),'missing_terminal_positions':missing_terminal_positions,'extra_terminal_positions':extra_terminal_positions,'terminal_sets_match':not missing_terminal_positions and not extra_terminal_positions,'declared_nets':inst.declared_nets,'actual_nets':len(inst.nets),'degree_count':len(inst.nets),'declared_pins':inst.declared_pins,'degree_sum':degree_sum,'pin_reference_count':sum(len(n.pins) for n in inst.nets),'reference_count':len(block_refs)+len(term_refs),'referenced_blocks':len(block_refs),'referenced_terminals':len(term_refs),'missing_references':missing,'references_complete':not missing and degree_sum == inst.declared_pins,'files':hashes})
    out=processed_dir/'round0_audit.json'; out.write_text(json.dumps({'raw_files':all_files,'instances':rows},indent=2),encoding='utf-8'); return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--raw',default='data/raw/附件'); ap.add_argument('--processed',default='data/processed'); args=ap.parse_args(); out=audit_files(args.raw,args.processed); print(out)
if __name__=='__main__': main()

import math
import unittest

from src._internal.audit import audit_layout
from src._internal.evaluator import evaluate
from src._internal.geometry import normalized_rotation, polygon_overlap_area
from src._internal.parser import parse_instance_text

RECT_BLOCKS = '''NumHardBlocks : 2
NumTerminals : 1
a block 4 (0, 0) (0, 2) (3, 2) (3, 0)
b block 4 (0, 0) (0, 1) (2, 1) (2, 0)
p1 terminal
'''
NETS = '''NumNets : 1
NumPins : 3
NetDegree : 3
a
b
p1
'''
PL = '''a 0 0
b 3 0
p1 10 10
'''
L_BLOCKS = '''NumHardBlocks : 2
NumTerminals : 0
l block 6 (0,0) (3,0) (3,1) (1,1) (1,3) (0,3)
s block 4 (0,0) (1,0) (1,1) (0,1)
'''

class Round0Tests(unittest.TestCase):
    def setUp(self):
        self.rect = parse_instance_text(RECT_BLOCKS, NETS, PL)

    def test_nets_have_synthetic_names_and_all_degree_pins(self):
        self.assertEqual(self.rect.declared_terminal_names, ('p1',))
        self.assertEqual(set(self.rect.terminals), set(self.rect.declared_terminal_names))
        self.assertEqual(self.rect.declared_pins, 3)
        self.assertEqual(self.rect.nets[0].name, 'net_000001')
        self.assertEqual(self.rect.nets[0].pins, ('a', 'b', 'p1'))

    def test_rotation_center_terminal_and_hpwl(self):
        out = evaluate(self.rect, {'a': (0, 0, 90), 'b': (2, 0, 0)})
        self.assertEqual((out.width, out.height), (4, 3))
        self.assertEqual(out.blocks['a'].center, (1.0, 1.5))
        self.assertEqual(out.hpwl, 18.5)  # centers (1,1.5),(3,0.5), terminal (10,10)

    def test_bbox_and_fixed_outline_metrics(self):
        layout = {'a': (0, 0, 0), 'b': (3, 0, 0)}
        bare = evaluate(self.rect, layout)
        fixed = evaluate(self.rect, layout, (0, 0, 6, 4))
        self.assertEqual((bare.width, bare.height), (5, 2))
        self.assertEqual((bare.area, bare.module_area), (10, 8))
        self.assertEqual(bare.aspect_ratio, 2.5)
        self.assertEqual((fixed.width, fixed.height), (6, 4))
        self.assertEqual(fixed.aspect_ratio, 1.5)
        self.assertEqual((fixed.area, fixed.module_area, fixed.deadspace, fixed.square_side), (24, 8, 16, 6))
        self.assertEqual(fixed.dead_space_ratio, 2)
        self.assertTrue(math.isclose(fixed.rho, 16 / 24))
        spread = evaluate(self.rect, {'a': (0, 0, 0), 'b': (8, 0, 0)})
        self.assertEqual(spread.module_area, bare.module_area)
        self.assertNotEqual(spread.area, bare.area)

    def test_touch_overlap_outline_edge_and_outside(self):
        self.assertTrue(evaluate(self.rect, {'a': (0, 0, 0), 'b': (3, 0, 0)}).legal)
        self.assertFalse(evaluate(self.rect, {'a': (0, 0, 0), 'b': (2, 0, 0)}).legal)
        self.assertTrue(evaluate(self.rect, {'a': (0, 0, 0), 'b': (4, 0, 0)}, (0, 0, 6, 2)).legal)
        self.assertFalse(evaluate(self.rect, {'a': (0, 0, 0), 'b': (5, 0, 0)}, (0, 0, 6, 2)).legal)

    def test_l_shape_all_rotations_are_normalized(self):
        base = [(0,0),(3,0),(3,1),(1,1),(1,3),(0,3)]
        expected = {0: (3,3), 90: (3,3), 180: (3,3), 270: (3,3)}
        for angle, extent in expected.items():
            poly = normalized_rotation(base, angle)
            self.assertEqual((max(x for x,y in poly), max(y for x,y in poly)), extent)
            self.assertEqual((min(x for x,y in poly), min(y for x,y in poly)), (0,0))

    def test_concave_nesting_collision_and_independent_audit(self):
        inst = parse_instance_text(L_BLOCKS, 'NumNets : 0\nNumPins : 0\n', '')
        nested = {'l': (0, 0, 0), 's': (1, 1, 0)}
        overlap = {'l': (0, 0, 0), 's': (0, 0, 0)}
        self.assertTrue(evaluate(inst, nested).legal)
        self.assertFalse(evaluate(inst, overlap).legal)
        for angle in (0, 90, 180, 270):
            layout = {'l': (0, 0, angle), 's': (1, 1, 0)}
            self.assertEqual(evaluate(inst, layout).as_dict(), audit_layout(inst, layout))
        self.assertEqual(polygon_overlap_area([(0,0),(3,0),(3,1),(1,1),(1,3),(0,3)], [(1,1),(2,1),(2,2),(1,2)]), 0)

if __name__ == '__main__':
    unittest.main()

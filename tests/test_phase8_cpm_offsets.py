import unittest
from core.projects.precedence_model import calculate_precedence


class CpmOffsetsTests(unittest.TestCase):
    def test_branching_network_backward_pass_and_free_float(self):
        plan = {'tasks': [
            {'id': 'A', 'duration_days': 2, 'predecessors': []},
            {'id': 'B', 'duration_days': 5, 'predecessors': ['A']},
            {'id': 'C', 'duration_days': 2, 'predecessors': ['A']},
            {'id': 'D', 'duration_days': 1, 'predecessors': ['B', 'C']},
        ]}
        result = calculate_precedence(plan, include_cpm=True)
        rows = {t['id']: t for t in result['tasks']}
        self.assertEqual(result['indicative_total_workdays'], 8)
        self.assertEqual([(rows[k]['latest_start_workday_offset'], rows[k]['total_float_workdays'], rows[k]['free_float_workdays']) for k in 'ABCD'], [(0,0,0),(2,0,0),(5,3,3),(7,0,0)])

    def test_relationships_and_lead(self):
        for kind, lag, expected in [('FS', -1, 4), ('SS', 2, 2), ('FF', 0, 2), ('SF', 6, 3)]:
            with self.subTest(kind=kind):
                p={'tasks':[{'id':'A','duration_days':5,'predecessors':[]}, {'id':'B','duration_days':3,'predecessors':['A'],'links':[{'predecessor':'A','type':kind,'lag_days':lag}]}]}
                rows={t['id']:t for t in calculate_precedence(p,include_cpm=True)['tasks']}
                self.assertEqual(rows['B']['start_workday_offset'],expected)
                self.assertGreaterEqual(rows['A']['total_float_workdays'],0)
                self.assertGreaterEqual(rows['B']['total_float_workdays'],0)

    def test_unsupported_constraints_are_rejected(self):
        p={'tasks':[{'id':'A','duration_days':1,'predecessors':[], 'constraint':{'type':'deadline','day':0}}]}
        with self.assertRaises(ValueError): calculate_precedence(p,include_cpm=True)

if __name__ == '__main__': unittest.main()

import json
from pathlib import Path
import tempfile
import unittest
from run import evaluate_result


class ResultTests(unittest.TestCase):
    def test_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'result.json'
            self.assertFalse(evaluate_result(0,p)[0])
            p.write_text('not json')
            self.assertFalse(evaluate_result(0,p)[0])
            for status in ('fail','skip','not tested'):
                p.write_text(json.dumps({'status':status}))
                self.assertFalse(evaluate_result(0,p)[0])
            p.write_text(json.dumps({'status':'pass'}))
            self.assertFalse(evaluate_result(1,p)[0])
            self.assertTrue(evaluate_result(0,p)[0])

    def test_non_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'result.json'
            p.write_text('[]')
            self.assertFalse(evaluate_result(0,p)[0])


if __name__=='__main__':
    unittest.main()

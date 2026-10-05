#!/usr/bin/env python3
# dpath2o: dyntens
# Guard the standalone candidate sampling order.
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CandidateInitialization(unittest.TestCase):
    def test_fsd_ready_before_candidate_and_ic(self):
        source = (ROOT / 'cicecore/drivers/standalone/cice/CICE_InitMod.F90').read_text()
        source = '\n'.join(line.split('!', 1)[0] for line in source.splitlines())
        driver = re.search(r'(?is)subroutine\s+cice_init\b(.*?)end\s+subroutine\s+cice_init', source)
        self.assertIsNotNone(driver)
        calls = re.findall(r'(?i)\bcall\s+(\w+)', driver.group(1))
        self.assertEqual(calls.count('update_dyntens_candidates'), 1)
        self.assertLess(calls.index('init_state'), calls.index('init_restart'))
        self.assertLess(calls.index('init_restart'), calls.index('update_dyntens_candidates'))
        self.assertLess(calls.index('update_dyntens_candidates'), calls.index('accum_hist'))
        restart = re.search(r'(?is)subroutine\s+init_restart\b(.*?)end\s+subroutine\s+init_restart', source)
        self.assertIsNotNone(restart)
        for name in ('init_fsd', 'read_restart_fsd'):
            self.assertRegex(restart.group(1), r'(?i)\bcall\s+' + name + r'\b')


if __name__ == '__main__':
    unittest.main()
# dpath2o: dyntens

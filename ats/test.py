import sys
sys.path.insert(0, "../")

import os
import unittest

def run_tests():
    loader = unittest.TestLoader()
    start_dir = 'tests'
    suite = loader.discover(start_dir, pattern='test_*.py')

    runner = unittest.TextTestRunner()
    result = runner.run(suite)

    if result.wasSuccessful():
        return 0
    else:
        return 1

if __name__ == '__main__':
    exit_code = run_tests()
    exit(exit_code)

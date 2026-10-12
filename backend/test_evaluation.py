import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base
from app.api.eval import run_evaluation


class EvaluationTests(unittest.TestCase):
    def test_all_sample_cases_pass_without_network(self):
        engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        with sessionmaker(bind=engine)() as db:
            from unittest.mock import patch
            with patch('httpx.post', side_effect=AssertionError('Evaluation must stay offline')):
                result = run_evaluation(db)
            self.assertEqual(len(result['results']), 4)
            self.assertTrue(all(case['passed'] for case in result['results']), result)


if __name__ == '__main__':
    unittest.main()

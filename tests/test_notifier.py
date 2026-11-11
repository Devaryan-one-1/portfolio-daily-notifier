import datetime as dt
import unittest
import notifier

class ReviewTests(unittest.TestCase):
    def test_missing_files_recommendations_are_grounded(self):
        tasks = notifier.recommendations({'src/app.py'}, [], 'main')
        self.assertEqual(len(tasks), 3)
        self.assertIn('README', tasks[0][0])
    def test_existing_artifacts_do_not_get_false_missing_claims(self):
        p = {'README.md', 'tests/test_app.py', '.github/workflows/ci.yml', 'examples/sample.json'}
        self.assertEqual(notifier.recommendations(p, ['README.md'], 'main'), [])
    def test_only_owner_commits_within_window(self):
        now = dt.datetime(2026, 11, 11, 9, tzinfo=dt.timezone.utc)
        def commit(login, date):
            return {'author': {'login': login}, 'commit': {'author': {'date': date}}, 'sha': 'a'*40}
        cs = [commit('Devaryan-one-1','2026-11-11T08:00:00Z'), commit('someone','2026-11-11T08:00:00Z'), commit('Devaryan-one-1','2026-11-09T08:00:00Z')]
        self.assertEqual(len(notifier.owner_changes(cs, now)), 1)

if __name__ == '__main__':
    unittest.main()

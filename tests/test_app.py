import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch
import app


class ResearchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = patch.object(app, 'DB', Path(self.tmp.name) / 'test.db')
        self.db.start()
        self.key = patch.dict(os.environ, {'OPENAI_API_KEY': ''})
        self.key.start()

    def tearDown(self):
        self.key.stop(); self.db.stop(); self.tmp.cleanup()

    def project(self):
        return app.new_project({'question': 'How do models help scientific researchers?', 'discovery': False,
            'sources': [{'title': 'Evidence A', 'text': 'Machine learning helps researchers identify patterns in large datasets. Experimental validation remains necessary to evaluate model predictions.'}]})

    def test_extractive_workflow_persistence_and_export(self):
        p = self.project()
        app.run(p['id'])
        p = app.get(p['id'])
        self.assertEqual(p['status'], 'complete')
        self.assertEqual(p['mode'], 'Extractive brief')
        self.assertEqual(len(p['report']['claims']), 1)
        e = p['report']['claims'][0]['evidence'][0]
        self.assertIn(e['quote'], p['sources'][0]['text'])
        self.assertIn('[1]', app.markdown(p))
        self.assertIn('## Sources', app.markdown(p))
        self.assertEqual(app.projects()[0]['id'], p['id'])

    def test_no_sources_fails_actionably(self):
        p = app.new_project({'question': 'What is the evidence for this question?', 'discovery': False})
        app.run(p['id'])
        p = app.get(p['id'])
        self.assertEqual(p['status'], 'failed')
        self.assertIn('Add a source excerpt', p['error'])

    def test_hallucinated_citations_rejected(self):
        s = self.project()['sources']
        for ev in [{'source_id': s[0]['id'], 'quote': 'A completely invented supporting quotation'}, {'source_id': 'unknown', 'quote': s[0]['text']}]:
            with self.assertRaises(ValueError):
                app.validate_report({'claims': [{'text': 'Unsupported claim', 'evidence': [ev]}]}, s)

    def test_valid_claim_and_two_sided_conflict(self):
        s = self.project()['sources']
        s.append(app.source('Evidence B', 'Model predictions can fail when evaluated on data unlike their training set.'))
        ev = [{'source_id': x['id'], 'quote': x['text']} for x in s]
        r = app.validate_report({'claims': [{'text': 'Models have limitations', 'evidence': ev}], 'conflicts': [{'text': 'A difference', 'evidence': ev}, {'text': 'One sided', 'evidence': ev[:1]}]}, s)
        self.assertEqual(len(r['claims']), 1)
        self.assertEqual(len(r['conflicts']), 1)

    def test_network_failure_preserves_uploaded_evidence(self):
        p = self.project(); p['discovery'] = True; app.save(p)
        with patch.object(app, 'fetch', side_effect=urllib.error.URLError('blocked')):
            app.run(p['id'])
        p = app.get(p['id'])
        self.assertEqual(p['status'], 'complete')
        self.assertEqual(len(p['warnings']), 2)

    def test_model_failure_falls_back_transparently(self):
        p = self.project()
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-only'}), patch.object(app, 'synthesize', side_effect=ValueError('Invalid evidence')):
            app.run(p['id'])
        p = app.get(p['id'])
        self.assertEqual(p['status'], 'complete')
        self.assertEqual(p['mode'], 'Extractive brief')
        self.assertIn('AI synthesis unavailable', p['warnings'][0])

    def test_private_url_rejected(self):
        for u in ['file:///etc/passwd', 'http://127.0.0.1/', 'http://169.254.169.254/', 'http://[::1]/', 'https://user:password@example.com/', 'http://example.com:9000/']:
            with self.assertRaises(ValueError): app.public_url(u)

    def test_sample_explicitly_labeled(self):
        p = app.sample()
        self.assertTrue(p['sample'])
        self.assertIn('Illustrative sample', app.markdown(p))
        self.assertTrue(all(not s['verified'] for s in p['sources']))

    def test_question_validation(self):
        for q in ['', 'short', 'a'*2001]:
            with self.assertRaises(ValueError): app.new_project({'question': q})


class APITest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = patch.object(app, 'DB', Path(self.tmp.name) / 'api.db')
        self.db.start()
        self.key = patch.dict(os.environ, {'OPENAI_API_KEY': ''})
        self.key.start()
        self.server = app.http.server.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown(); self.server.server_close()
        self.key.stop(); self.db.stop(); self.tmp.cleanup()

    def request(self, path, data=None, origin=None):
        headers = {'Content-Type': 'application/json'}
        if origin: headers['Origin'] = origin
        return urllib.request.urlopen(urllib.request.Request(self.base + path, data=json.dumps(data).encode() if data is not None else None, headers=headers))

    def test_http_create_run_read_export(self):
        with self.request('/api/projects', {'question': 'How can we verify evidence in research?', 'discovery': False, 'sources': [{'title': 'Test source', 'text': 'Evidence should be traced to its original source and evaluated in the context of the research question.'}]}) as res:
            self.assertEqual(res.status, 201); p = json.load(res)
        with self.request('/api/projects/' + p['id'] + '/run', {}) as res:
            self.assertEqual(res.status, 202)
        for _ in range(100):
            with self.request('/api/projects/' + p['id']) as res: p = json.load(res)
            if p['status'] != 'running': break
            time.sleep(.01)
        self.assertEqual(p['status'], 'complete')
        with self.request('/api/projects/' + p['id'] + '/export') as res:
            self.assertIn('Test source', res.read().decode())

    def test_cross_origin_write_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.request('/api/sample', {}, 'https://evil.example')
        self.assertEqual(cm.exception.code, 403)

    def test_static_traversal_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.request('/../app.py')
        self.assertEqual(cm.exception.code, 404)


if __name__ == '__main__': unittest.main()

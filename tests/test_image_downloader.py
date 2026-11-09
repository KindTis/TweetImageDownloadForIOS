import io
import json
import os
import runpy
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / 'ImageDownloaderPy.py'
POST_URL = 'https://x.com/example/status/123'


def post_html(post_id, media):
    payload = {'data': {'tweet_result_by_rest_id': {'result': {
        'rest_id': post_id, 'media_entities2': media,
    }}}}
    return ('<script data-tsr-stream-part>'
            f'load({json.dumps(json.dumps(payload))});</script>')


class ShareExtensionTests(unittest.TestCase):
    def setUp(self):
        working_directory = tempfile.TemporaryDirectory()
        self.addCleanup(working_directory.cleanup)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(working_directory.name)
        self.saved = []
        self.shared = []
        self.finished = []

    def run_share(self, shared_url, responses):
        album = SimpleNamespace(
            title='Pythonista',
            add_assets=lambda assets: self.saved.extend(assets),
        )

        def create_asset(path):
            photo = Path(path)
            return photo.name, photo.read_bytes()

        modules = {
            'appex': SimpleNamespace(
                is_running_extension=lambda: True,
                get_url=lambda: shared_url,
                finish=lambda: self.finished.append(True),
            ),
            'photos': SimpleNamespace(
                get_albums=lambda: [album],
                create_image_asset=create_asset,
            ),
            'dialogs': SimpleNamespace(share_url=self.shared.append),
        }

        def open_url(request, **kwargs):
            url = request if isinstance(request, str) else request.full_url
            self.assertIn(url, responses)
            return io.BytesIO(responses[url])

        output = io.StringIO()
        with patch.dict(sys.modules, modules), patch('urllib.request.urlopen', open_url):
            with redirect_stdout(output):
                runpy.run_path(str(SCRIPT), run_name='__main__')
        return output.getvalue()

    def test_saves_only_target_post_photos_at_original_size(self):
        other = {'type': 'photo', 'media_url_https': 'https://pbs.twimg.com/media/other.jpg'}
        photos = [
            {'type': 'photo', 'media_url_https': 'https://pbs.twimg.com/media/first.jpg'},
            {'type': 'photo', 'media_url_https': 'https://pbs.twimg.com/media/second.png'},
        ]
        html = post_html('456', [other]) + post_html('123', photos)
        self.run_share('https://twitter.com/example/status/123?s=12', {
            POST_URL: html.encode(),
            'https://pbs.twimg.com/media/first?format=jpg&name=orig': b'first',
            'https://pbs.twimg.com/media/second?format=png&name=orig': b'second',
        })
        self.assertEqual(self.saved, [('first.jpg', b'first'), ('second.png', b'second')])
        self.assertEqual(self.finished, [True])

    def test_shares_highest_bitrate_mp4(self):
        url = 'https://video.twimg.com/video/best.mp4?tag=1'
        video = {'type': 'video', 'video_info': {'variants': [
            {'content_type': 'application/x-mpegURL', 'url': 'https://video.twimg.com/stream.m3u8'},
            {'content_type': 'video/mp4', 'bitrate': 200, 'url': url},
            {'content_type': 'video/mp4', 'bitrate': 100, 'url': 'https://video.twimg.com/video/low.mp4'},
        ]}}
        self.run_share(POST_URL, {POST_URL: post_html('123', [video]).encode(), url: b'video'})
        self.assertEqual(len(self.shared), 1)
        self.assertTrue(self.shared[0].endswith('/best.mp4'))
        self.assertEqual(self.saved, [])

    def test_reports_unavailable_post_data_without_saving(self):
        output = self.run_share(POST_URL, {POST_URL: post_html('456', []).encode()})
        self.assertIn('Could not find the requested post', output)
        self.assertEqual(self.saved, [])
        self.assertEqual(self.finished, [])


if __name__ == '__main__':
    unittest.main()

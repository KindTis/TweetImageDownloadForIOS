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
        self.allow_video_save = True

    def run_share(self, shared_url, responses):
        album = SimpleNamespace(
            title='Pythonista',
            local_id='pythonista-album',
            add_assets=lambda assets: self.saved.extend(assets),
        )

        def create_asset(path):
            media = Path(path)
            return media.name, media.read_bytes()

        def fetch_collections(identifiers, options):
            collection = album if identifiers == [album.local_id] else None
            return SimpleNamespace(firstObject=lambda: collection)

        def create_video_request(path):
            return SimpleNamespace(placeholderForCreatedAsset=lambda: create_asset(path))

        def perform_changes(block, error):
            if not self.allow_video_save:
                return False
            block(None)
            return True

        photokit = {
            'NSURL': SimpleNamespace(fileURLWithPath_=str),
            'PHAssetCollection': SimpleNamespace(
                fetchAssetCollectionsWithLocalIdentifiers_options_=fetch_collections,
            ),
            'PHAssetCollectionChangeRequest': SimpleNamespace(
                changeRequestForAssetCollection_=lambda collection: SimpleNamespace(addAssets_=collection.add_assets),
            ),
            'PHAssetChangeRequest': SimpleNamespace(
                creationRequestForAssetFromVideoAtFileURL_=create_video_request,
            ),
            'PHPhotoLibrary': SimpleNamespace(
                sharedPhotoLibrary=lambda: SimpleNamespace(performChangesAndWait_error_=perform_changes),
            ),
        }

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
            'objc_util': SimpleNamespace(
                load_framework=lambda name: None,
                ObjCClass=photokit.__getitem__,
                ObjCBlock=lambda function, **kwargs: function,
            ),
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

    def test_saves_highest_bitrate_mp4_to_album(self):
        url = 'https://video.twimg.com/video/best.mp4?tag=1'
        video = {'type': 'video', 'video_info': {'variants': [
            {'content_type': 'application/x-mpegURL', 'bitrate': 300, 'url': 'https://video.twimg.com/stream.m3u8'},
            {'content_type': 'video/mp4', 'bitrate': 100, 'url': 'https://video.twimg.com/video/low.mp4'},
            {'content_type': 'video/mp4', 'bitrate': 200, 'url': url},
        ]}}
        self.run_share(POST_URL, {POST_URL: post_html('123', [video]).encode(), url: b'video'})
        self.assertEqual(self.saved, [('best.mp4', b'video')])
        self.assertEqual(self.shared, [])
        self.assertEqual(self.finished, [True])

    def test_reports_video_album_save_failure(self):
        self.allow_video_save = False
        url = 'https://video.twimg.com/video/best.mp4'
        video = {'type': 'video', 'video_info': {'variants': [
            {'content_type': 'video/mp4', 'bitrate': 200, 'url': url},
        ]}}
        output = self.run_share(POST_URL, {POST_URL: post_html('123', [video]).encode(), url: b'video'})
        self.assertIn('Could not save the video', output)
        self.assertEqual(self.saved, [])
        self.assertEqual(self.finished, [])

    def test_saves_zero_bitrate_animations_to_album(self):
        first_url = 'https://video.twimg.com/tweet_video/first.mp4'
        second_url = 'https://video.twimg.com/tweet_video/second.mp4'
        animations = [
            {'type': 'animated_gif', 'video_info': {'variants': [
                {'content_type': 'video/mp4', 'bitrate': 0, 'url': first_url},
            ]}},
            {'type': 'animated_gif', 'video_info': {'variants': [
                {'content_type': 'video/mp4', 'bitrate': 0, 'url': second_url},
            ]}},
        ]
        self.run_share(POST_URL, {
            POST_URL: post_html('123', animations).encode(),
            first_url: b'first animation',
            second_url: b'second animation',
        })
        self.assertEqual(self.saved, [
            ('first.mp4', b'first animation'),
            ('second.mp4', b'second animation'),
        ])
        self.assertEqual(self.finished, [True])

    def test_reports_unavailable_post_data_without_saving(self):
        output = self.run_share(POST_URL, {POST_URL: post_html('456', []).encode()})
        self.assertIn('Could not find the requested post', output)
        self.assertEqual(self.saved, [])
        self.assertEqual(self.finished, [])


if __name__ == '__main__':
    unittest.main()

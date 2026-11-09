import json
import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib import request
from urllib.parse import urlsplit

import appex
import photos


class TweetImageDownloadIOS:
    def __init__(self, tweetUrl):
        mediaURLs = self.getMediaURLs(self.getTweetMedia(tweetUrl))
        if not mediaURLs:
            print('This post has no downloadable photos or videos.')
            return
        self.downLoadMedia(mediaURLs)

    def getTweetMedia(self, tweetUrl):
        url = urlsplit(tweetUrl or '')
        post = re.fullmatch(r'/((?:i/web|[A-Za-z0-9_]+))/status/([0-9]+)(?:/(?:photo|video)/[0-9]+)?/?', url.path)
        if url.scheme not in ('https', 'http') or url.hostname not in (
            'x.com', 'www.x.com', 'mobile.x.com',
            'twitter.com', 'www.twitter.com', 'mobile.twitter.com',
        ) or not post:
            raise ValueError('Share a post URL from X or Twitter.')

        handle, tweetID = post.groups()
        pageRequest = request.Request(
            f'https://x.com/{handle}/status/{tweetID}',
            headers={'User-Agent': 'Mozilla/5.0'},
        )
        with request.urlopen(pageRequest, timeout=15) as response:
            html = response.read().decode('utf-8')

        # X includes the focal post as a JSON string in the public page.
        # Use its post ID so photos in replies and quoted posts are excluded.
        for script in re.findall(
            r'<script\b(?=[^>]*\bdata-tsr-stream-part\b)[^>]*>(.*?)</script\s*>',
            html,
            re.DOTALL,
        ):
            for literal in re.findall(r'"(?:[^"\\]|\\.)*"', script):
                if 'tweet_result_by_rest_id' not in literal:
                    continue
                try:
                    payload = json.loads(json.loads(literal))
                    result = payload['data']['tweet_result_by_rest_id']['result']
                except (ValueError, KeyError, TypeError):
                    continue
                if isinstance(result, dict) and result.get('rest_id') == tweetID:
                    return result.get('media_entities2') or []

        raise ValueError('Could not find the requested post in the public X page.')

    def getMediaURLs(self, media):
        urls = []
        for item in media:
            if item.get('type') == 'photo':
                url = item.get('media_url_https', '')
                photo = urlsplit(url)
                if photo.scheme == 'https' and photo.hostname == 'pbs.twimg.com' and re.fullmatch(
                    r'/media/[A-Za-z0-9_-]+\.(?:jpg|png)', photo.path,
                ):
                    urls.append(url)
            elif item.get('type') == 'video':
                variants = (item.get('video_info') or {}).get('variants', [])
                mp4s = [
                    variant for variant in variants
                    if variant.get('content_type') == 'video/mp4'
                    and urlsplit(variant.get('url', '')).hostname == 'video.twimg.com'
                ]
                if mp4s:
                    best = max(mp4s, key=lambda variant: variant.get('bitrate', 0))
                    urls.append(best['url'])
        return urls

    def changeToOrig(self, link):
        url = urlsplit(link)
        path, imageFormat = url.path.rsplit('.', 1)
        return url._replace(path=path, query=f'format={imageFormat}&name=orig', fragment='').geturl()

    def downLoadMedia(self, mediaURLs):
        with TemporaryDirectory() as temp:
            for url in mediaURLs:
                filename = Path(temp) / Path(urlsplit(url).path).name
                isVideo = filename.suffix == '.mp4'
                downloadURL = url if isVideo else self.changeToOrig(url)

                with request.urlopen(downloadURL, timeout=30) as response, filename.open('wb') as file:
                    shutil.copyfileobj(response, file)

                print('saving...', url)
                self.addToAlbum(filename, 'Pythonista')

    def addToAlbum(self, file_path, album_name):
        try:
            album = [a for a in photos.get_albums() if a.title == album_name][0]
        except IndexError:
            album = photos.create_album(album_name)
        if file_path.suffix == '.mp4':
            self.addVideoToAlbum(file_path, album)
        else:
            asset = photos.create_image_asset(str(file_path))
            album.add_assets([asset])

    def addVideoToAlbum(self, file_path, album):
        from ctypes import c_void_p
        from objc_util import ObjCBlock, ObjCClass, load_framework

        load_framework('Photos')
        collections = ObjCClass('PHAssetCollection').fetchAssetCollectionsWithLocalIdentifiers_options_(
            [album.local_id], None,
        )
        collection = collections.firstObject()
        if collection is None:
            raise OSError('Could not save the video: the album is unavailable.')

        video_url = ObjCClass('NSURL').fileURLWithPath_(str(file_path))
        asset_requests = ObjCClass('PHAssetChangeRequest')
        album_requests = ObjCClass('PHAssetCollectionChangeRequest')
        added = False

        def add_video(_block):
            nonlocal added
            album_change = album_requests.changeRequestForAssetCollection_(collection)
            if album_change is None:
                return
            video_change = asset_requests.creationRequestForAssetFromVideoAtFileURL_(video_url)
            placeholder = video_change.placeholderForCreatedAsset() if video_change is not None else None
            if placeholder is not None:
                album_change.addAssets_([placeholder])
                added = True

        # Wait for Photos to import the file before the temporary directory is removed.
        changes = ObjCBlock(add_video, restype=None, argtypes=[c_void_p])
        library = ObjCClass('PHPhotoLibrary').sharedPhotoLibrary()
        if not library.performChangesAndWait_error_(changes, None) or not added:
            raise OSError('Could not save the video to the Photos album.')


if __name__ == '__main__':
    isExtension = appex.is_running_extension()
    tweetUrl = appex.get_url() if isExtension else 'https://twitter.com/kindtis/status/1562730616915128320'
    print(f'Parsing... {tweetUrl}')

    try:
        TweetImageDownloadIOS(tweetUrl)
    except (OSError, ValueError) as error:
        print(f'Download failed: {error}')
    else:
        print('done.')
        if isExtension:
            appex.finish()

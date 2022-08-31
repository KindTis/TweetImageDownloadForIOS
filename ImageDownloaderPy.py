from PIL import Image
import base64
import requests
import appex
import photos
import os
import shutil
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib import request
from urllib.parse import urlparse
from io import BytesIO


class TweetImageDownloadIOS:
	def __init__(self, tweetID):
		api_key = 'api_key'
		api_secret = 'api_secret'
		
		bearerToken = self.bearer(api_key, api_secret)
		if bearerToken is None:
			print('access denied.')
			return
		#print(bearerToken)
		
		tweetStatus = self.getTweet(bearerToken, tweetID)
		if not tweetStatus:
			print('could not found tweet.')
			return
			
		#print(tweetStatus)
		mediaURLs = self.getMeddiaURL(tweetStatus)
		if mediaURLs is None:
			print('there is no images.')
			return
			
		#print(imgURL)
		self.downLoadMedia(mediaURLs)

	def bearer(self, key, secret):
		credential = base64.b64encode(bytes(f'{key}:{secret}', 'utf-8')).decode()
		url = 'https://api.twitter.com/oauth2/token'
		headers = {
			'Authorization': f'Basic {credential}',
			'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8',
		}
		payload = {'grant_type': 'client_credentials'}

		session = requests.Session()
		retry = Retry(connect=3, backoff_factor=0.5)
		adapter = HTTPAdapter(max_retries=retry)
		session.mount('http://', adapter)
		session.mount('https://', adapter)

		respone = session.post(url, headers=headers, params=payload)
		if respone.status_code == 200:
			return respone.json()['access_token']
		else:
			raise None

	def getTweet(self, bearerToken, id):
		url = f'https://api.twitter.com/2/tweets?ids={id}&tweet.fields=created_at&expansions=attachments.media_keys&media.fields=preview_image_url,url,variants'
		headers = {'Authorization': f'Bearer {bearerToken}'}
		payload = {'tweet_mode': 'extended'}

		session = requests.Session()
		retry = Retry(connect=3, backoff_factor=0.5)
		adapter = HTTPAdapter(max_retries=retry)
		session.mount('http://', adapter)
		session.mount('https://', adapter)

		respone = session.get(url, headers=headers)
		if respone.status_code == 200:
			tweets = respone.json()
			if len(tweets) == 1:
				return []
			else:
				return tweets
		else:
			return []

	def getMeddiaURL(self, tweet):
		if 'media' in tweet['includes']:
			urls = []
			media = tweet['includes']['media']
			for m in media:
				mediaType = m['type']
				if mediaType == 'video':
					variants = m['variants']
					bestBitRate = 0
					bestBitRateURL = ''
					for v in variants:
						if 'bit_rate' not in v:
						   continue
						if bestBitRate < v['bit_rate']:
							bestBitRate = v['bit_rate']
							bestBitRateURL = v['url']
					if len(bestBitRateURL) > 0:
						urls.append(bestBitRateURL)
				elif mediaType == 'photo':
					urls.append(m['url'])
				else:
					return None
			return urls
		else:
			return None

	def changeToOrig(self, link):
		if (link.find('.png') != -1):
			ext = '?format=png&name=orig'
			origLink = link[0:link.find('.png')] + ext
		elif (link.find('.jpg') != -1):
			ext = '?format=jpg&name=orig'
			origLink = link[0:link.find('.jpg')] + ext
		return origLink

	def downLoadMedia(self, imgUrls):
		for url in imgUrls:
			regex = re.compile('\/([a-zA-Z0-9_-]+\.(?:mp4|jpg|png))')
			match = regex.search(url)
			filename = match.group(1)
			filename = f'temp/{filename}'
			#print(filename)
			
			isVideo = False
			if (url.find('.mp4') > -1):
				isVideo = True
​
			if isVideo is True:
				dlURL = url
			else:
				dlURL = self.changeToOrig(url)
				
			with request.urlopen(dlURL) as res:
				with open(filename, "wb") as f:
					f.write(res.read())
					print('saving...', url)
					
					if isVideo is True:
						fileUri = Path(filename).resolve().as_uri()
						dialogs.share_url(fileUri)
					else:
						self.addToAlbum(filename, 'Pythonista')
​
	def addToAlbum(self, image_path, album_name):
		try:
			album = [a for a in photos.get_albums() if a.title == album_name][0]
		except IndexError:
			album = photos.create_album(album_name)
		asset = photos.create_image_asset(image_path)
		album.add_assets([asset])

if __name__ == '__main__':
	regex = re.compile('status\/(\d+)')
	
	if not os.path.isdir('temp'):
		os.mkdir('temp')

	if appex.is_running_extension():
		tweetUrl = appex.get_url()
		print(f'Parsing... {tweetUrl}')
		match = regex.search(appex.get_url())
		tweetId = match.group(1)
	else:
		match = regex.search('https://twitter.com/kindtis/status/1562730616915128320')
		tweetId = match.group(1)
	
	dl = TweetImageDownloadIOS(tweetId)
	shutil.rmtree('temp')
	print('done.')

	if appex.is_running_extension():
		appex.finish()
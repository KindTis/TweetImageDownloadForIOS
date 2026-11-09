# X 미디어 다운로더 for iOS

iOS 공유 시트에서 공개 X(Twitter) 게시물을 공유하면, 첨부 사진과 동영상을 사진 앱의 **Pythonista** 앨범에 저장합니다. X 개발자 계정, API 키, 추가 Python 패키지 없이 사용할 수 있습니다.

[스크립트 보기](ImageDownloaderPy.py) · [Pythonista 3 다운로드](https://apps.apple.com/kr/app/pythonista-3/id1085978097)

## 시작하기

1. Pythonista 3를 설치하고 [ImageDownloaderPy.py](ImageDownloaderPy.py)의 내용을 Pythonista의 새 스크립트에 저장합니다.
2. Pythonista 편집기에서 렌치 아이콘을 누른 뒤 **Shortcuts → Share Extension**에서 스크립트를 등록합니다.
3. X 앱이나 Safari에서 공개 게시물을 열고 **공유 → Run Pythonista Script**에서 등록한 스크립트를 실행합니다.
4. 사진 접근을 요청하면 허용합니다. 저장한 파일은 사진 앱의 **Pythonista** 앨범에서 확인할 수 있습니다. 앨범이 없으면 자동으로 만듭니다.

공유 시트에 **Run Pythonista Script**가 보이지 않으면 **동작 편집(Edit Actions)**에서 활성화합니다. [Pythonista 공유 확장 문서](https://omz-software.com/pythonista/docs-3.4/py3/ios/pythonista_shortcuts.html#share-sheet-extension)

## 저장 형식과 화질

| 유형 | 저장 방식 |
| --- | --- |
| 사진 (JPEG, PNG) | X 이미지 CDN에서 `name=orig` 크기로 받습니다. 사진이 여러 장이면 해당 게시물의 첨부 사진을 모두 저장합니다. |
| 동영상 (MP4) | 게시물에 공개된 직접 다운로드용 MP4 중 비트레이트가 가장 높은 파일을 골라 재인코딩 없이 저장합니다. |

사진과 동영상의 화질은 X가 제공하는 버전에 따릅니다. 동영상은 직접 다운로드할 수 있는 MP4가 공개된 경우에 저장할 수 있습니다.

## 지원 범위

- 로그인 없이 열 수 있는 `x.com`과 `twitter.com`의 게시물 링크를 처리합니다.
- 공유한 게시물에 직접 첨부된 미디어를 저장합니다. 인용 게시물과 답글의 첨부는 범위에서 제외됩니다.
- 공개 게시물 HTML에서 미디어 주소를 읽으므로 X가 페이지 구조를 바꾸면 추출이 실패할 수 있습니다.

## 문제 해결

- **게시물 URL을 인식하지 못함** — Safari에서 게시물 자체를 연 뒤 Safari의 공유 버튼으로 실행합니다.
- **공개 페이지에서 게시물을 찾지 못함** — 로그인하지 않은 상태에서도 해당 게시물이 열리는지 확인합니다.
- **사진이나 동영상 저장 실패** — iOS 설정에서 Pythonista의 사진 접근 권한과 기기의 여유 공간을 확인합니다.

## 개발 테스트

저장소 루트에서 다음 명령을 실행합니다. 테스트는 iOS 모듈과 HTTP 응답을 대역으로 바꿔 공유 URL 처리, 사진 원본 크기 요청, MP4 선택과 앨범 저장 경로를 확인합니다.

```bash
python -B -m unittest discover -s tests -v
```

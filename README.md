# CreatorLens - YouTube 영상 검색 + 채널 분석 도구

유튜브 영상을 검색하고 채널의 성과를 분석하는 Next.js 기반 웹 애플리케이션입니다.

## 🚀 시작하기

로컬 서비스 구동을 위해 다음 단계를 따라주세요.

### 1. 필수 프로그램 설치
- [Node.js](https://nodejs.org/) (v18 이상 권장)가 설치되어 있어야 합니다.

### 2. 패키지 설치
이미 프로젝트에 `node_modules` 폴더가 있다면 이 단계를 건너뛰어도 되지만, 처음 실행하거나 오류가 발생할 경우 실행합니다.
- `파일설치.bat`을 실행하거나 터미널에서 `npm install`을 입력합니다.

### 3. 환경 변수 설정
유튜브 데이터를 가져오기 위해 [Google Cloud Console](https://console.cloud.google.com/apis/credentials)에서 발급받은 **YouTube Data API v3** 키가 필요합니다.
- `.env.local` 파일을 열고 `YOUTUBE_API_KEY` 항목에 본인의 API 키를 입력하세요. (현재는 테스트용 키가 입력되어 있습니다.)

### 4. 개발 서버 실행
- `실행파일.bat`을 실행하거나 터미널에서 `npm run dev`를 입력합니다.
- 브라우저에서 [http://localhost:3000](http://localhost:3000) (이미 3000번 포트를 사용 중이라면 [http://localhost:3001](http://localhost:3001))에 접속합니다.

## 🛠 주요 기능
- **영상 찾기**: 검색어별 유튜브 영상 검색 및 성과 지표 분석
- **채널 찾기**: 채널 검색 및 구독자, 영상 수 통계 확인
- **채널 분석**: 특정 채널의 모든 영상을 분석하여 기여도, 성과도, 노출 확률 계산
- **수집한 영상**: 분석한 영상 중 관심 있는 영상을 따로 보관 및 관리

## 📦 기술 스택
- **Frontend/Backend**: Next.js 15 (App Router), React 19
- **Styling**: TailwindCSS
- **Icons**: Lucide React
- **API**: YouTube Data API v3

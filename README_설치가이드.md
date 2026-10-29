# BJ Intelligence Newsroom · 배포 준비판 (v6)

## 핵심 구분
- 이 패키지는 **실제 외부 호스팅 배포를 할 수 있도록 제작된 소스**입니다. 아직 사용자의 GitHub 계정에 배포하지 않았습니다.
- 배포 후 GitHub Actions가 **매시간 실행을 시도**하고 GitHub Pages의 `newsroom.json`을 갱신하며, 브라우저가 열려 있을 때 **5분마다 최신 데이터를 재조회**합니다. GitHub 스케줄은 부하로 지연되거나 비활성화될 수 있으므로 24시간 SLA나 정확히 정각 갱신을 보장하지 않습니다.
- **자동 수집 기사 ≠ 독립 사실 검증 완료 기사.** RSS 원문 제목·날짜·링크 중심의 자동 색인입니다. KBS 뉴스9 실제 방송 보도는 방송 원문 확인 없이는 0건으로 처리합니다. 각 5건 목표를 달성했다고 허위 표시하지 않습니다.
- ChatGPT의 **07:30 일일 뉴스, 월요일 08:45 투자 브리핑 예약 작업과 이 GitHub Pages는 자동 연동되지 않습니다.** 별도 서비스입니다.

## 준비
GitHub 계정과 신규 저장소 1개가 필요합니다. 무료 계정인 경우 GitHub Pages 및 Actions의 현재 정책·제한을 확인하세요. 공개 저장소는 소스와 뉴스 데이터가 공개되므로 비밀번호·개인 정보를 업로드하지 마세요.

## 설치 (Mac, Windows 동일)
1. 압축 파일을 다운로드하고 압축 해제합니다.
2. GitHub에서 새 **공개(Public)** 저장소를 만듭니다 (예: `bj-intelligence-newsroom`).
3. 압축 해제한 폴더 **안의 전체 내용**을 저장소 최상위에 업로드합니다 (`.github/workflows/publish.yml` 포함). 숨김 폴더가 업로드되었는지 꼭 확인합니다.
4. 저장소 `Settings → Pages → Build and deployment → Source`에서 **GitHub Actions**를 선택합니다.
5. `Actions → Publish BJ Newsroom → Run workflow`를 눌러 첫 발행을 수동 실행합니다.
6. 완료 후 `Settings → Pages`에 표시된 Pages URL을 엽니다. (예: `https://계정명.github.io/저장소명/`)
7. 상단 데이터 생성 시각, 항목 수, 각 기사 링크를 살펴봅니다. 1시간 후 새 갱신 기록이 생기는지 `Actions` 기록으로 점검합니다.

## 검증/진단
- `python3 -m unittest discover -s tests -v`: 자동 테스트
- `python3 scripts/update_feed.py`: 로컬 RSS 수집 실행 (인터넷 필요)
- 브라우저 `file://`로 열면 `fetch('./newsroom.json')`이 보안 정책에 의해 막힐 수 있습니다. GitHub Pages에서 열거나 로컬에서 `python3 -m http.server 8000 --directory site` 후 `http://localhost:8000/` 로 접근하세요.
- 원격 RSS 소스 장애/차단으로 수집이 0건이면 자동 발행은 실패하여 이전 파일을 보존하도록 설정했습니다.
- 공식 교육 행사는 `data/official_events.json`에 원문 대조 후 수동 입력해야 합니다. 자동으로 모집 상태를 확정하지 않습니다.
- 검색 색인용 Google News RSS 링크는 원 발행 언론사가 아니라 집계 주소일 수 있습니다. 필요한 경우 원문을 추가 확인합니다.

## 정식 완성 판정 이전의 필수 검증
1. 실제 브리핑 날짜의 KBS 뉴스9 원문을 방송 편성·기사 링크로 대조하고 원문 데이터 게재
2. 각 8개 섹션별 **검증된** 5건 이상을 독립 확인하는 편집 파이프라인
3. 실제 공식 교육 세미나 신청 링크·모집 상태 확인
4. 사용자가 GitHub에 배포 후 24시간 이상 Actions 실행/실패 기록, 웹 접근성 확인
5. 브리핑 알림의 수신 여부는 사용자의 ChatGPT 앱 알림 설정/기기에서 확인

## 보안
GitHub Personal Access Token, API Key 등을 HTML, JSON, 저장소 소스에 넣지 마세요. 필요하면 GitHub Actions Secrets를 이용해야 합니다. 원격 웹 정보를 그대로 HTML로 주입하지 않도록 화면 출력은 escape 처리합니다.

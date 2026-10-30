# BJ 인텔리전스 뉴스룸

매일 07:30 아침판. 교차검증 등급(A/B/C)과 출처를 붙인 국내·국제·이스라엘·중동·Religion·과학·AI 뉴스, 그리고 분야별 교육·세미나 일정을 한 화면에서 읽는 뉴스룸입니다.

공개 주소: https://joshua7park-cyber.github.io/BJ-NewsRoom/

## 운영본은 하나

| 파일 | 역할 |
|---|---|
| `index.html` | 유일한 운영 페이지. 포털 보기(3단)와 데스크 보기(분야별 보드)를 전환합니다. 기사 내용은 들어 있지 않습니다. |
| `data/edition.json` | 오늘 아침판: 기사, 교육·세미나, 관전 포인트, 검증 보류 |
| `site/newsroom.json` | 매시간 자동 수집하는 실시간 제목 색인 (검증 전, 페이지 하단에 따로 표시) |
| `site/link-report.json` | 배포 때 생성되는 링크 점검 결과 (저장소에는 없음) |
| `EDITOR_GUIDE.md` | 매일 아침 편집 세션이 따르는 지침 |

## 매일 흐름

1. **06:40 KST** Claude 예약 작업이 `EDITOR_GUIDE.md`대로 뉴스를 조사하고 `data/edition.json`을 새로 씁니다.
2. 편집 세션은 `validate_edition.py --require-today`와 테스트를 통과한 경우에만 `main`에 푸시합니다.
3. 푸시하면 **BJ Newsroom Deploy**가 검사를 차례로 실행하고, 하나라도 실패하면 배포를 멈춥니다.
   1. 아침판 데이터 검사 (형식, 등급별 출처 수, 요일, 더미 문구, 오래된 기사)
   2. 회귀 테스트
   3. 페이지 자바스크립트 문법
   4. 모든 출처·신청 링크 열람 (A급 기사는 열리는 출처 2곳 이상 필요)
   5. 배포 후 공개 주소에서 페이지와 JSON 3종 응답 확인
4. **07:41 KST**에 같은 검사를 한 번 더 실행해 공개 페이지를 재확인합니다.
5. 매시간 `refresh-news.yml`이 제목 색인을 갱신합니다. 아침판 기사와는 섞이지 않습니다.

아침판이 발행되지 않은 날에는 전날 판이 "오늘판 발행 전" 표시와 함께 그대로 보입니다. 빈 화면이나 임시 기사는 나오지 않습니다.

## 직접 확인하기

```bash
python scripts/validate_edition.py
```

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

```bash
python scripts/check_links.py --report-only
```

```bash
python -m http.server 8000
```

마지막 명령을 실행한 뒤 브라우저에서 http://localhost:8000 을 엽니다.

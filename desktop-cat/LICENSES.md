# 제3자 구성요소와 라이선스

이 프로그램은 아래 오픈소스와 공개 데이터를 사용합니다. 배포 시 이 파일을 함께 포함해야 합니다.

| 구성요소 | 용도 | 라이선스 |
|---|---|---|
| Python | 실행 환경 | PSF License |
| PySide6 (Qt for Python) | 창, 그림, 트레이 | LGPL v3 (동적 링크, 소스 공개 의무 없음) |
| pynput | 전역 키보드 감지 | MIT |
| psutil | 배터리, CPU 상태 | BSD 3-Clause |
| anthropic (선택) | AI 대화 (API 키가 있을 때만) | MIT |
| PyInstaller | exe 빌드 도구 (배포물에 부트로더 포함) | GPL v2 with bootloader exception (상용 배포 허용) |

## 공개 데이터 출처

| 데이터 | 출처 | 조건 |
|---|---|---|
| 날씨, 미세먼지 | Open-Meteo (open-meteo.com) | CC BY 4.0, **비상업 무료**. 상업적 배포 시 유료 플랜 또는 기상청 공공데이터 API로 교체 필요 |
| 환율 | Frankfurter (frankfurter.app), 유럽중앙은행 고시 | 무료, 출처 표기 |
| 뉴스 헤드라인 | Google 뉴스 RSS | 제목만 표시, 출처 표기 |
| 공휴일 | Nager.Date (date.nager.at) | MIT |

## 개인정보

이 프로그램은 사용자의 입력을 외부로 보내지 않습니다. 예외는 두 가지입니다.

1. 사용자가 직접 API 키를 넣고 대화할 때, 대화 문장이 Anthropic API로 전송됩니다.
2. 날씨, 환율, 뉴스, 공휴일 조회 시 해당 서비스에 요청이 갑니다 (위치 이름 외 개인정보 없음).

키보드 입력 내용은 읽지 않습니다. "키가 눌렸다"는 사실만 사용하며 어떤 키인지는 기록하지 않습니다.

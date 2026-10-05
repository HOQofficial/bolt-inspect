# bolt-inspect 스타터 팩 (데이터 스키마 v1.2)

자세한 설명은 팀 문서 "개발 환경 구축 가이드 + 데이터 스키마 v1.0"을 보세요.

## 폴더
| 폴더 | 내용 | 담당 |
| --- | --- | --- |
| `schema/` | 확정 스키마 (flange, inspection). **바꾸려면 4번 담당과 합의** | 4번 |
| `tools/` | `schema_rules.py`(공용 규칙), `validate.py`(검사), `make_fake_data.py`(가짜 데이터), `seed_firestore.py`(업로드) | 전원 |
| `dashboard/` | Streamlit 앱: `app.py`(메뉴) · `home.py`(검사 현황) · `tapping.py`(타음 검사, 조원 V3 통합) · `vision.py`(비전 검사: 볼트 돌출 · I-마킹 · 플랜지 틈) · `store.py`(저장소) · `ui.py`(화면 부품) | 2·4번 |
| `tools/add_flange.py` | 시편·플랜지를 앱에 등록 (`--id FL101 --nut-height 13.0`) | 3·4번 |
| `tools/sim.py` | 가상 타음 데이터 (조원 V3 의 make_mock) | 2번 |
| `tools/merge_public_data.py` | 공개 데이터 zip + 우리 라벨을 학습 세트로 합침 | 3번 |
| `reference/` | 조원 V3 원본 (참고용) | - |
| `web/` | 태블릿 웹앱 (지금은 환경 테스트 페이지) | 3·4번 |
| `esp32/tap_v1/` | BLE 메시지 v1 송신 테스트 | 1·2번 |
| `data/` | 정답값 CSV 양식 (원본 사진·wav는 공유 드라이브) | 전원 |
| `sample/` | 가짜 데이터 | - |
| `models/` | 학습한 비전 모델 `bolt_yolo.pt` 넣는 곳 | 3번 |
| `data/labels/` | 비전 검사에서 저장할 때 자동으로 쌓이는 YOLO 학습 데이터 | 3번 |

## 자주 쓰는 명령 (프로젝트 폴더에서, 가상환경 켠 상태)
```
python tools/make_fake_data.py
python tools/validate.py inspection sample/fake_inspections.json
streamlit run dashboard/app.py      # key.json 없으면 local_db/ 에 저장, 있으면 Firestore
python tools/seed_firestore.py
firebase deploy --only hosting
```

## 절대 하지 말 것
- `key.json` 을 GitHub·카톡·메일에 올리기 (`.gitignore` 에 들어 있음)
- 스키마 필드 이름을 혼자 바꾸기

"""자료 모양 — 요청마다 채우는 곳 (1/2).

FILES: 데이터셋 한 묶음을 이루는 CSV 와 열 형식. 검증(validate)은 이 표만 보고 돈다.
  형식: id · str · int · num · date(YYYY-MM-DD) · time(HH:MM) · yn(Y/N) · ("enum", [값…])
  열 이름 끝에 "?" 를 붙이면 빈 값 허용. key 는 중복 금지. refs 는 "다른표.열" 에 있는 값만 허용.
PARAMS: 운영자가 화면에서 바꾸는 조건. default 는 함수(data → 값)도 된다 — 데이터셋을 바꾸면 그 데이터로 다시 정해진다.
MEMBER: 두 번째 역할 계정을 만들 표 (key 가 로그인 아이디, name 이 화면 이름).
아래 값은 예시 자료(example/data)에 맞춘 것. 받은 자료로 바꾼다.
"""

FILES = {
    "places": {"file": "places.csv", "key": "place_id",
               "cols": {"place_id": "id", "name": "str", "x": "num", "y": "num", "capacity": "int"}},
    "people": {"file": "people.csv", "key": "person_id",
               "cols": {"person_id": "id", "name": "str", "home_place": "id", "lead": "yn"},
               "refs": {"home_place": "places.place_id"}},
    "slots": {"file": "slots.csv",
              "cols": {"date": "date", "person_id": "id", "start": "time", "end": "time",
                       "status": ("enum", ["work", "off"])},
              "refs": {"person_id": "people.person_id"}},
    "links": {"file": "links.csv",
              "cols": {"from_id": "id", "to_id": "id", "minutes": "int"},
              "refs": {"from_id": "places.place_id", "to_id": "places.place_id"}},
}

MEMBER = {"table": "people", "key": "person_id", "name": "name"}


def _dates(data):
    return sorted({r["date"] for r in data["slots"]})


PARAMS = [
    {"name": "date_from", "label": "기간 시작", "type": "date", "default": lambda d: _dates(d)[0]},
    {"name": "date_to", "label": "기간 끝", "type": "date", "default": lambda d: _dates(d)[-1]},
    {"name": "max_per_place", "label": "자리당 상한(빈칸=정원)", "type": "int?", "default": None},
]


def extra_checks(data):
    """열 형식·참조 말고 자료 사이 검사. 오류 문장 목록을 돌려준다 (예: 기간 역전, 짝이 없는 행)."""
    errs = []
    for i, r in enumerate(data["slots"], start=2):
        if r["start"] == r["end"]:
            errs.append(f"slots.csv:{i} start 와 end 가 같음 ({r['start']})")
    return errs

"""정보기 알림메모 — 실행: streamlit run app.py
GitHub에 app.py, requirements.txt를 올린 뒤 Streamlit Community Cloud에 배포하세요.
QR은 배포된 앱 주소로 생성합니다. 데이터는 접속 세션별로 분리됩니다.
"""
import io
import json
import uuid
from datetime import datetime

import qrcode
import streamlit as st

st.set_page_config(page_title="정보기 알림메모", page_icon="🛒", layout="centered", initial_sidebar_state="collapsed")
st.markdown("""<style>
.block-container {max-width:480px;padding:0.65rem 0.8rem 1rem;}
header[data-testid="stHeader"] {display:none;}
[data-testid="stVerticalBlock"] {gap:0.4rem;}
h1 {font-size:1.5rem!important;padding:0!important;}
[data-testid="stMetricValue"] {font-size:1.45rem;}
[data-testid="stMetricLabel"] {font-size:0.8rem;}
.stButton button,.stFormSubmitButton button {min-height:42px;}
</style>""", unsafe_allow_html=True)

CATEGORIES = ["🥬 야채", "🍎 과일", "🥩 육류", "🐟 수산물", "🥛 유제품", "🍚 식료품", "🧻 생활용품", "📦 기타"]
LEVELS = {1: "🔴 1 필수", 2: "🟡 2 가격 보고 구매", 3: "🟢 3 저렴할 때만"}
for key, default in [("pending", []), ("cart", []), ("notice", "")]:
    if key not in st.session_state:
        st.session_state[key] = default


def money(value):
    return f"{int(value):,}원"


def label(item):
    return f"{LEVELS[item['priority']]} · {item['name']} · {item['category']}"


def validate_backup(data):
    """외부 JSON은 제한된 스키마와 크기를 검증한 뒤에만 복원한다."""
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("지원하지 않는 백업 형식입니다.")
    result = {}
    ids = set()
    for group in ("pending", "cart"):
        rows = data.get(group)
        if not isinstance(rows, list) or len(rows) > 500:
            raise ValueError("목록 형식 또는 항목 수를 확인하세요.")
        cleaned = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("잘못된 항목입니다.")
            ident = row.get("id")
            name = row.get("name")
            priority = row.get("priority")
            category = row.get("category")
            cap = row.get("cap")
            if not isinstance(ident, str) or not ident or len(ident) > 100 or ident in ids:
                raise ValueError("항목 ID가 잘못되었거나 중복됩니다.")
            if not isinstance(name, str) or not name.strip() or len(name) > 60:
                raise ValueError("상품명을 확인하세요.")
            if type(priority) is not int or priority not in LEVELS or category not in CATEGORIES:
                raise ValueError("카테고리 또는 중요도를 확인하세요.")
            if type(cap) is not int or not 0 <= cap <= 100000000:
                raise ValueError("구매 기준가를 확인하세요.")
            item = dict(id=ident, name=name.strip(), priority=priority, category=category, cap=cap)
            if group == "cart":
                price, qty = row.get("price"), row.get("qty")
                if type(price) is not int or not 0 <= price <= 100000000:
                    raise ValueError("구매 단가를 확인하세요.")
                if type(qty) is not int or not 1 <= qty <= 9999:
                    raise ValueError("구매 수량을 확인하세요.")
                item.update(price=price, qty=qty)
            ids.add(ident)
            cleaned.append(item)
        result[group] = cleaned
    return result


st.title("🛒 정보기 알림메모")
st.caption("1 필수 · 2 가격 보고 · 3 저렴할 때만")
if st.session_state.notice:
    st.toast(st.session_state.notice)
    st.session_state.notice = ""

cart = st.session_state.cart
pending = st.session_state.pending
c1, c2, c3 = st.columns([1, 1, 1.5])
c1.metric("살 물건", f"{len(pending)}종")
c2.metric("카트", f"{sum(x['qty'] for x in cart)}개")
c3.metric("현재 총액", money(sum(x['price'] * x['qty'] for x in cart)))

a, b, c = st.columns(3)
with a:
    with st.popover("＋ 메모", use_container_width=True):
        with st.form("add_item", clear_on_submit=True):
            name = st.text_input("상품명", max_chars=60, placeholder="예: 방울토마토 500g")
            category = st.selectbox("카테고리", CATEGORIES)
            priority = st.selectbox("중요도", list(LEVELS), format_func=LEVELS.get)
            cap = st.number_input("구매 기준 단가(원) · 0은 미설정", min_value=0, max_value=100000000, step=100, value=0)
            if st.form_submit_button("메모 추가", use_container_width=True):
                if not name.strip():
                    st.error("상품명을 입력하세요.")
                else:
                    pending.append(dict(id=uuid.uuid4().hex, name=name.strip(), category=category, priority=priority, cap=int(cap)))
                    st.session_state.notice = "메모에 추가했습니다."
                    st.rerun()
with b:
    with st.popover("🛒 카트", use_container_width=True):
        if not cart:
            st.caption("아직 담은 상품이 없습니다.")
        else:
            cart_id = st.selectbox("담은 상품", [x['id'] for x in cart], format_func=lambda ident: next(f"{x['name']} · {x['qty']}개 · {money(x['price'] * x['qty'])}" for x in cart if x['id'] == ident))
            current = next(x for x in cart if x['id'] == cart_id)
            st.caption(f"단가 {money(current['price'])} × {current['qty']}개")
            st.caption("수량·단가를 수정하려면 메모로 되돌린 뒤 다시 담으세요.")
            if st.button("↩ 구매 취소 · 메모로 복원", use_container_width=True):
                pending.append({k: current[k] for k in ('id', 'name', 'category', 'priority', 'cap')})
                st.session_state.cart = [x for x in cart if x['id'] != cart_id]
                st.session_state.notice = "총액에서 제외하고 메모로 복원했습니다."
                st.rerun()
with c:
    with st.popover("⚙ 저장/QR", use_container_width=True):
        st.caption("메모는 현재 접속 세션에서만 유지됩니다. 탭 종료·연결 해제·서버 재시작 시 사라질 수 있으니 백업하세요. QR은 앱 접속용이며 목록 공유용이 아닙니다.")
        backup = json.dumps(dict(version=1, pending=pending, cart=cart), ensure_ascii=False, indent=2)
        st.download_button("💾 백업 내려받기", backup, file_name=f"shopping_{datetime.now():%Y%m%d}.json", mime="application/json", use_container_width=True)
        uploaded = st.file_uploader("백업 불러오기 (현재 목록을 대체)", type=["json"])
        replace_ok = st.checkbox("현재 메모·카트를 백업 내용으로 대체합니다")
        if st.button("백업 복원", disabled=uploaded is None or not replace_ok):
            try:
                if uploaded.size > 1000000:
                    raise ValueError("1MB 이하의 백업만 지원합니다.")
                restored = validate_backup(json.loads(uploaded.getvalue().decode('utf-8')))
                st.session_state.pending = restored['pending']
                st.session_state.cart = restored['cart']
                st.session_state.notice = "백업을 복원했습니다."
                st.rerun()
            except (ValueError, UnicodeError, TypeError, KeyError):
                st.error("백업 파일의 형식이나 값이 올바르지 않습니다.")
        url = st.text_input("배포한 앱 주소", placeholder="https://앱이름.streamlit.app")
        if url:
            if url.startswith('https://') and len(url) <= 2000:
                buffer = io.BytesIO()
                qrcode.make(url).save(buffer, format="PNG")
                st.image(buffer.getvalue(), width=180)
                st.download_button("QR 이미지 저장", buffer.getvalue(), "shopping_qr.png", "image/png")
            else:
                st.caption("https://로 시작하는 배포 주소를 입력하세요.")

if not pending:
    st.info("＋ 메모에서 장볼 상품을 추가하세요." if not cart else "메모의 상품을 모두 담았습니다! 🛒에서 구매내역을 확인하세요.")
else:
    ordered = sorted(pending, key=lambda x: x['priority'])
    by_id = {x['id']: x for x in ordered}
    next_id = st.session_state.pop('next_selected', None)
    if next_id in by_id:
        st.session_state['selected_item'] = next_id
    if st.session_state.get('selected_item') not in by_id:
        st.session_state['selected_item'] = ordered[0]['id']
    selected = st.selectbox("살 물건 선택 · 중요도순", list(by_id), format_func=lambda ident: label(by_id[ident]), key='selected_item')
    item = by_id[selected]
    if item['cap']:
        st.caption(f"구매 기준 단가 {money(item['cap'])} · 비싸면 아래 ‘나중에’로 보류")
    else:
        st.caption("기준가 미설정 · 중요도 2·3은 비싸면 ‘나중에’로 보류")
    with st.form(f"purchase_{selected}"):
        p, q = st.columns([1.6, 1])
        price = p.number_input("실제 단가(원)", min_value=0, max_value=100000000, value=None, step=100, placeholder="가격 입력")
        qty = q.number_input("수량(개/팩)", min_value=1, max_value=9999, value=1, step=1)
        override = st.checkbox("기준가를 넘겨도 구매할게요", value=False)
        submitted = st.form_submit_button("✓ 카트에 담기 · 메모에서 제거", type="primary", use_container_width=True)
        if submitted:
            if price is None:
                st.error("실제 구매 단가를 입력하세요. 무료 상품은 0원입니다.")
            elif item['cap'] and price > item['cap'] and not override:
                st.warning("구매 기준가를 넘었습니다. 비싸면 ‘나중에’로 보류하세요. 꼭 사려면 위 확인란을 체크하고 다시 담으세요.")
            else:
                st.session_state.cart.append(dict(item, price=int(price), qty=int(qty)))
                st.session_state.pending = [x for x in pending if x['id'] != selected]
                st.session_state.notice = f"{item['name']} {qty}개 · {money(price * qty)} 담았습니다."
                st.rerun()
    left, right = st.columns(2)
    if left.button("↪ 나중에 · 보류", use_container_width=True):
        # 중요도를 바꾸지 않고 같은 중요도 안에서 뒤로 이동한다.
        st.session_state.pending = [x for x in pending if x['id'] != selected] + [item]
        others = [x for x in sorted(st.session_state.pending, key=lambda x: x['priority']) if x['id'] != selected]
        if others:
            # 다음 실행에서 다른 상품을 자동 선택한다.
            st.session_state['next_selected'] = others[0]['id']
        st.session_state.notice = "메모는 유지했습니다. 다른 상품을 선택해 계속 장보세요."
        st.rerun()
    with right.popover("메모 삭제", use_container_width=True):
        st.caption("구매가 아니라 메모 자체를 삭제합니다. 총액에는 반영되지 않습니다.")
        if st.button("구매 없이 삭제", use_container_width=True):
            st.session_state.pending = [x for x in pending if x['id'] != selected]
            st.rerun()

st.caption("총액 = 실제 단가 × 수량의 합계 · 할인은 반영된 단가로 입력")

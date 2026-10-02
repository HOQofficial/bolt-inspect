import time
from datetime import datetime
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="볼트 품질검사 V3", page_icon="🔩", layout="wide")

# 초기 데모 기준값: 실제 기준 등록 전 UI 확인용
DEFAULT_REF = {
    "mic": {"freq": (3000.0, 3400.0), "mag": (0.70, 0.90), "energy": (60.0, 80.0)},
    "acc": {"freq": (400.0, 440.0), "mag": (0.60, 0.82), "energy": (62.0, 82.0)},
}

defaults = {
    "count": 0, "history": [], "data": None,
    "baseline_samples": [], "ref": DEFAULT_REF.copy(),
    "ref_source": "데모 기준", "baseline_version": 0
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

def inside(v, r): return r[0] <= v <= r[1]

def judge(x, r):
    checks = {
        "Peak Frequency": inside(x["freq"], r["freq"]),
        "Peak Magnitude": inside(x["mag"], r["mag"]),
        "Band Energy": inside(x["energy"], r["energy"]),
    }
    n = sum(checks.values())
    result = "정상" if n == 3 else ("재측정 필요" if n == 2 else "체결 이상 의심")
    return result, checks

def make_mock(cond):
    g = np.random.default_rng()
    fm = np.linspace(0, 8000, 801)
    fa = np.linspace(0, 500, 501)

    if cond == "정상 체결":
        mf, mm, me = g.normal(3200, 65), g.normal(.80, .025), g.normal(69, 2)
        af, am, ae = g.normal(420, 7), g.normal(.71, .025), g.normal(72, 2)
    elif cond == "체결 이상 의심":
        mf, mm, me = g.normal(3820, 90), g.normal(.53, .03), g.normal(43, 3)
        af, am, ae = g.normal(335, 12), g.normal(.47, .03), g.normal(47, 3)
    else:
        mf, mm, me = g.normal(3440, 35), g.normal(.72, .03), g.normal(57, 2)
        af, am, ae = g.normal(445, 6), g.normal(.62, .025), g.normal(60, 2)

    ms = g.uniform(.01, .04, len(fm))
    ms += max(mm,.05)*np.exp(-.5*((fm-mf)/115)**2)
    ms += .18*np.exp(-.5*((fm-mf*.52)/90)**2)

    ac = g.uniform(.01,.035,len(fa))
    ac += max(am,.05)*np.exp(-.5*((fa-af)/14)**2)
    ac += .14*np.exp(-.5*((fa-af*.48)/10)**2)

    mic = {"freq":float(mf), "mag":float(mm), "energy":float(np.clip(me,0,100))}
    acc = {"freq":float(af), "mag":float(am), "energy":float(np.clip(ae,0,100))}
    mj, mc = judge(mic, st.session_state.ref["mic"])
    aj, ac_checks = judge(acc, st.session_state.ref["acc"])

    final = ("체결 이상 의심" if "체결 이상 의심" in (mj,aj)
             else "재측정 필요" if "재측정 필요" in (mj,aj) else "정상")
    return {"fm":fm,"ms":ms,"fa":fa,"ac":ac,"mic":mic,"acc":acc,
            "mj":mj,"aj":aj,"mc":mc,"ac_checks":ac_checks,"final":final}

def calc_ref(samples, k_sigma):
    df = pd.DataFrame(samples)
    ref = {}
    for sensor, prefix in [("mic","음향"),("acc","진동")]:
        ref[sensor] = {}
        for key, col in [("freq",f"{prefix} Peak Hz"),("mag",f"{prefix} Magnitude"),("energy",f"{prefix} Energy %")]:
            mean = float(df[col].mean())
            std = float(df[col].std(ddof=1)) if len(df) > 1 else 0.0
            # 표준편차가 너무 작을 때 0폭 기준 방지
            floor = {"freq": mean*0.01, "mag": max(mean*0.03,0.01), "energy": max(mean*0.03,1.0)}[key]
            width = max(k_sigma*std, floor)
            ref[sensor][key] = (mean-width, mean+width)
    return ref

def spectrum(x,y,peak,label):
    f=go.Figure(go.Scatter(x=x,y=y,mode="lines"))
    f.add_vline(x=peak,line_dash="dash",annotation_text=label)
    f.update_layout(height=300,margin=dict(l=20,r=20,t=20,b=20),
                    xaxis_title="Frequency (Hz)",yaxis_title="Magnitude",showlegend=False)
    return f

def gauge(title,val,lo,hi,suffix="",fmt=".2f"):
    span=max(hi-lo,1e-9); pad=.65*span; xmin=max(0,lo-pad); xmax=hi+pad
    f=go.Figure(go.Indicator(
        mode="number+gauge", value=val,
        number={"suffix":suffix,"valueformat":fmt}, title={"text":title},
        gauge={"shape":"bullet","axis":{"range":[xmin,xmax]},"bar":{"color":"#2563eb"},
               "steps":[{"range":[xmin,lo],"color":"#f1f5f9"},
                        {"range":[lo,hi],"color":"#dcfce7"},
                        {"range":[hi,xmax],"color":"#f1f5f9"}],
               "threshold":{"line":{"color":"#111827","width":3},"value":val}}))
    f.update_layout(height=125,margin=dict(l=10,r=10,t=30,b=5))
    return f

def status_box(label, result, checks):
    if result=="정상": st.success(f"### {label} · 정상")
    elif result=="재측정 필요": st.warning(f"### {label} · 재측정 필요")
    else: st.error(f"### {label} · 체결 이상 의심")
    marks = "  |  ".join([f"{k} {'✓' if v else '✕'}" for k,v in checks.items()])
    st.caption(marks)

st.title("🔩 타격음 기반 볼트 체결 품질검사 대시보드 V3")
st.caption("정상 기준 등록/학습 · INMP441 음향 + MPU6050 진동 · FFT 특징값 · 판정 · 이력")

with st.sidebar:
    st.header("검사 설정")
    bolt = st.text_input("검사 대상 Bolt ID","B-03")
    cond = st.selectbox("가상 측정 조건",["정상 체결","체결 이상 의심","재측정 필요"])

    st.divider()
    st.subheader("정상 기준 등록")
    target_n = st.number_input("기준 측정 목표 횟수", min_value=3, max_value=100, value=10, step=1)
    k_sigma = st.select_slider("기준 범위 폭", options=[1.0,1.5,2.0,2.5,3.0], value=2.0,
                               help="평균 ± k×표준편차 방식의 데모 설정입니다.")
    st.write(f"수집된 정상 샘플: **{len(st.session_state.baseline_samples)} / {target_n}**")

    if st.button("➕ 현재 측정값을 정상 기준 샘플로 추가", use_container_width=True):
        if st.session_state.data is not None:
            x=st.session_state.data
            st.session_state.baseline_samples.append({
                "음향 Peak Hz":x["mic"]["freq"],"음향 Magnitude":x["mic"]["mag"],"음향 Energy %":x["mic"]["energy"],
                "진동 Peak Hz":x["acc"]["freq"],"진동 Magnitude":x["acc"]["mag"],"진동 Energy %":x["acc"]["energy"]})
            st.rerun()

    if st.button("🎯 수집 샘플로 정상 기준 계산/등록", use_container_width=True):
        if len(st.session_state.baseline_samples) >= 3:
            st.session_state.ref = calc_ref(st.session_state.baseline_samples, k_sigma)
            st.session_state.ref_source = f"실측 등록 기준 · n={len(st.session_state.baseline_samples)} · ±{k_sigma}σ"
            st.session_state.baseline_version += 1
            st.session_state.data = None
            st.rerun()
        else:
            st.warning("정상 기준 계산에는 최소 3개 샘플이 필요합니다.")

    if st.button("정상 기준 샘플 초기화", use_container_width=True):
        st.session_state.baseline_samples=[]
        st.rerun()

    st.divider()
    st.subheader("장비 상태")
    st.success("ESP32 · DEMO 연결")
    st.write("통신: USB Serial 시뮬레이션")
    st.write("INMP441: 준비")
    st.write("MPU6050: 준비")

c1,c2,c3,c4=st.columns(4)
c1.metric("검사 대상",bolt)
c2.metric("센서","INMP441 + MPU6050")
c3.metric("기준",st.session_state.ref_source)
c4.metric("측정 횟수",f"{st.session_state.count} 회")

if st.button("▶ 측정 시작",type="primary",use_container_width=True):
    with st.spinner("신호 취득 → FFT → 특징값 추출 → 기준 비교 중..."):
        time.sleep(.25)
        x=make_mock(cond); st.session_state.data=x; st.session_state.count+=1
        st.session_state.history.append({
            "시간":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"Bolt ID":bolt,
            "음향 판정":x["mj"],"진동 판정":x["aj"],"종합 판정":x["final"],
            "음향 Peak Hz":round(x["mic"]["freq"],1),"음향 Magnitude":round(x["mic"]["mag"],3),"음향 Energy %":round(x["mic"]["energy"],1),
            "진동 Peak Hz":round(x["acc"]["freq"],1),"진동 Magnitude":round(x["acc"]["mag"],3),"진동 Energy %":round(x["acc"]["energy"],1),
            "기준":st.session_state.ref_source})
    st.rerun()

if st.session_state.data is None:
    st.session_state.data=make_mock("정상 체결")
x=st.session_state.data
# 기준이 바뀐 뒤 현재 데이터 재판정
x["mj"],x["mc"]=judge(x["mic"],st.session_state.ref["mic"])
x["aj"],x["ac_checks"]=judge(x["acc"],st.session_state.ref["acc"])
x["final"]=("체결 이상 의심" if "체결 이상 의심" in (x["mj"],x["aj"])
            else "재측정 필요" if "재측정 필요" in (x["mj"],x["aj"]) else "정상")

l,r=st.columns(2)
with l:
    st.subheader("🎤 음향 FFT · INMP441")
    st.plotly_chart(spectrum(x["fm"],x["ms"],x["mic"]["freq"],f'Peak {x["mic"]["freq"]/1000:.2f} kHz'),use_container_width=True)
with r:
    st.subheader("📳 진동 FFT · MPU6050")
    st.plotly_chart(spectrum(x["fa"],x["ac"],x["acc"]["freq"],f'Peak {x["acc"]["freq"]:.0f} Hz'),use_container_width=True)

mr=st.session_state.ref["mic"]; ar=st.session_state.ref["acc"]
st.subheader("🎤 음향 특징값 · 정상 기준범위")
cols=st.columns(3)
with cols[0]: st.plotly_chart(gauge("Peak Frequency",x["mic"]["freq"]/1000,mr["freq"][0]/1000,mr["freq"][1]/1000," kHz",".2f"),use_container_width=True)
with cols[1]: st.plotly_chart(gauge("Peak Magnitude",x["mic"]["mag"],*mr["mag"],"",".3f"),use_container_width=True)
with cols[2]: st.plotly_chart(gauge("Band Energy",x["mic"]["energy"],*mr["energy"]," %",".1f"),use_container_width=True)

st.subheader("📳 진동 특징값 · 정상 기준범위")
cols=st.columns(3)
with cols[0]: st.plotly_chart(gauge("Peak Frequency",x["acc"]["freq"],*ar["freq"]," Hz",".1f"),use_container_width=True)
with cols[1]: st.plotly_chart(gauge("Peak Magnitude",x["acc"]["mag"],*ar["mag"],"",".3f"),use_container_width=True)
with cols[2]: st.plotly_chart(gauge("Band Energy",x["acc"]["energy"],*ar["energy"]," %",".1f"),use_container_width=True)

st.subheader("🧭 센서별 판정 + 판정 근거")
p,q=st.columns(2)
with p: status_box("음향",x["mj"],x["mc"])
with q: status_box("진동",x["aj"],x["ac_checks"])

st.subheader("🏁 종합 판정")
st.code("음향 정상 + 진동 정상 → 정상\n한 센서에서 1개 특징값 이탈 → 재측정 필요\n한 센서에서 2개 이상 특징값 이탈 → 체결 이상 의심", language=None)
if x["final"]=="정상": st.success(f"## {bolt} · 정상")
elif x["final"]=="재측정 필요": st.warning(f"## {bolt} · 재측정 필요")
else: st.error(f"## {bolt} · 체결 이상 의심")

st.subheader("🎯 현재 등록된 정상 기준")
rows=[]
for s,n in [("mic","음향"),("acc","진동")]:
    r=st.session_state.ref[s]
    rows += [[n,"Peak Frequency",r["freq"][0],r["freq"][1],"Hz"],
             [n,"Peak Magnitude",r["mag"][0],r["mag"][1],"-"],
             [n,"Band Energy",r["energy"][0],r["energy"][1],"%"]]
st.dataframe(pd.DataFrame(rows,columns=["센서","특징값","하한","상한","단위"]),use_container_width=True,hide_index=True)

st.subheader("🗂️ 검사 이력")
if st.session_state.history:
    h=pd.DataFrame(st.session_state.history)
    simple=h[["시간","Bolt ID","음향 판정","진동 판정","종합 판정","기준"]]
    st.dataframe(simple.iloc[::-1],use_container_width=True,hide_index=True)
    with st.expander("상세 측정값 보기"):
        st.dataframe(h.iloc[::-1],use_container_width=True,hide_index=True)
    st.download_button("검사 이력 CSV 저장",h.to_csv(index=False).encode("utf-8-sig"),
                       "bolt_inspection_history_v3.csv","text/csv",use_container_width=True)
else:
    st.info("아직 검사 이력이 없습니다.")

st.caption("※ V3의 기준 등록은 PoC용 통계 방식입니다. 실제 품질 판정 기준은 충분한 반복 실험, 체결 조건 통제 및 검증을 거쳐 확정해야 합니다.")

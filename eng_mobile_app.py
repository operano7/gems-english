import streamlit as st
import pandas as pd
import io
import os
import asyncio
import edge_tts
import base64
import streamlit.components.v1 as components
import time

# 1. 화면 설정
APP_TITLE = "US 영어 학습기"
APP_ICON_PATH = "미국국기 아이콘.png"
APP_ICON = APP_ICON_PATH if os.path.exists(APP_ICON_PATH) else "🇺🇸"

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.header(f"🇺🇸 {APP_TITLE}")

st.markdown("""
<style>
.eng-custom-font { font-size: 20pt !important; font-weight: 700 !important; }
div[role="radiogroup"] { gap: 3rem !important; }
div[data-testid="stCheckbox"] p { white-space: nowrap !important; }
div[data-testid="stDataFrame"] { border: 1.5px solid #ffffff !important; border-radius: 0.25rem; }
div[data-testid="stDataFrame"] data-grid-canvas { font-size: 10pt !important; }
</style>
""", unsafe_allow_html=True)

if "is_continuous_playing" not in st.session_state: st.session_state.is_continuous_playing = False
if "current_play_idx" not in st.session_state: st.session_state.current_play_idx = 0
if "last_clicked_row" not in st.session_state: st.session_state.last_clicked_row = None

st.markdown("📖 **읽어줄 언어를 선택하세요 (복수 선택 가능):**")
col_l1, col_l2, _ = st.columns([1.2, 1.2, 3.6])
with col_l1: read_eng = st.checkbox("영어", value=True)
with col_l2: read_kor = st.checkbox("한국어")
read_langs = ["영어" if read_eng else "", "한국어" if read_kor else ""]
read_langs = [l for l in read_langs if l]

st.markdown("🗣️ **음성 종류를 선택하세요:**")
col_v1, col_v2, col_v3, _ = st.columns([1.2, 1.2, 1.2, 2.4])
with col_v1: use_google = st.checkbox("Google (여성)", value=True)
with col_v2: use_edge_m = st.checkbox("MS Edge (남성)")
with col_v3: use_edge_f = st.checkbox("MS Edge (여성)")

voice_options = []
if use_google: voice_options.append("Google (여성)")
if use_edge_m: voice_options.append("MS Edge (남성)")
if use_edge_f: voice_options.append("MS Edge (여성)")

st.markdown("🐢 **음성 재생 속도를 선택하세요:**")
speed_choice = st.radio("속도 선택", options=["아주 느리게 (0.6x)", "조금 느리게 (0.8x)", "보통 속도 (1.0x)"], index=2, horizontal=True, label_visibility="collapsed")

if speed_choice == "아주 느리게 (0.6x)": final_edge_rate_str, final_gtts_slow = "-40%", True
elif speed_choice == "조금 느리게 (0.8x)": final_edge_rate_str, final_gtts_slow = "-20%", False
else: final_edge_rate_str, final_gtts_slow = "+0%", False

EXCEL_FILE = None
for name in ["영어회화_통합본", "영어 공부_통합본", "영어 공부"]: 
    for ext in ['.xlsx', '.xlsm']:
        if os.path.exists(f"{name}{ext}"):
            EXCEL_FILE = f"{name}{ext}"; break
    if EXCEL_FILE: break

@st.cache_data
def load_all_data(filepath, last_modified):
    with open(filepath, "rb") as f: file_bytes = f.read()
    xl = pd.ExcelFile(io.BytesIO(file_bytes), engine='openpyxl')
    return xl.sheet_names, {s: pd.read_excel(io.BytesIO(file_bytes), sheet_name=s) for s in xl.sheet_names}

sheet_names, all_sheets = load_all_data(EXCEL_FILE, os.path.getmtime(EXCEL_FILE))
selected_sheet = st.selectbox("📂 학습할 단어장 시트:", sheet_names)
search_query = st.text_input("🔍 검색어 입력:", "")

def process_sheet_data(df):
    for c in df.columns: df[c] = df[c].astype(str).str.replace('.0', '', regex=False).replace(['nan', 'None'], '', regex=False)
    return df[df['영어'] != '']

processed_df = process_sheet_data(all_sheets[selected_sheet])

def get_edge_audio_sync(text, voice_model, rate_str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async def _generate():
        comm = edge_tts.Communicate(text, voice_model, rate=rate_str)
        return b"".join([chunk["data"] async for chunk in comm.stream() if chunk["type"] == "audio"])
    return loop.run_until_complete(_generate())

@st.cache_data(show_spinner=False)
def generate_multiple_audios(eng_text, kor_text, selected_options, edge_rate, gtts_slow, read_langs_list):
    audio_results = []
    for opt in selected_options:
        for lang in read_langs_list:
            t, lc, vm = (kor_text, 'ko', "ko-KR-InJoonNeural" if "남성" in opt else "ko-KR-SunHiNeural") if lang == "한국어" else (eng_text, 'en', "en-US-GuyNeural" if "남성" in opt else "en-US-AriaNeural")
            if "Edge" in opt: audio_results.append(get_edge_audio_sync(t, vm, edge_rate))
            else:
                from gtts import gTTS
                fp = io.BytesIO()
                gTTS(text=t, lang=lc, slow=gtts_slow).write_to_fp(fp)
                audio_results.append(fp.getvalue())
    return audio_results, []

def play_sequential_audio(audio_bytes_list, is_continuous=False):
    b64_audios = [f"data:audio/mp3;base64,{base64.b64encode(ab).decode()}" for ab in audio_bytes_list]
    js_array = str(b64_audios).replace("'", '"')
    
    html_code = f"""
    <div id="btnContainer"><audio id="player" style="display: none;"></audio></div>
    <script>
        var audios = {js_array};
        var currentIdx = 0;
        var player = document.getElementById("player");
        if(audios.length > 0) {{
            player.src = audios[0];
            player.play();
            player.onended = function() {{
                currentIdx++;
                if(currentIdx < audios.length) {{
                    setTimeout(() => {{ player.src = audios[currentIdx]; player.play(); }}, 1000);
                }} else if ({'true' if is_continuous else 'false'}) {{
                    window.parent.document.querySelectorAll('button').forEach(b => {{ if(b.innerText.trim() === 'AUTO_NEXT_BTN_XYZ') b.click(); }});
                }}
            }};
        }}
    </script>
    """
    components.html(html_code, height=50)

filtered_df = processed_df[processed_df.apply(lambda row: any(str(search_query).lower() in str(v).lower() for v in row), axis=1)] if search_query else processed_df

target_idx = st.session_state.current_play_idx
if target_idx < len(filtered_df):
    item = filtered_df.iloc[target_idx]
    st.markdown(f"### {item['영어']}\n**{item['해석']}**")
    audio_datas, _ = generate_multiple_audios(item['영어'], item['해석'], voice_options, final_edge_rate_str, final_gtts_slow, read_langs)
    play_sequential_audio(audio_datas, is_continuous=st.session_state.is_continuous_playing)

if st.button("AUTO_NEXT_BTN_XYZ", key="auto_next"):
    st.session_state.current_play_idx = (st.session_state.current_play_idx + 1) % len(filtered_df)
    st.rerun()

if st.button("TOGGLE_CONT_BTN_XYZ", key="toggle_cont"):
    st.session_state.is_continuous_playing = not st.session_state.is_continuous_playing
    st.rerun()

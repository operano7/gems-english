import streamlit as st
import pandas as pd
import io
import os
import asyncio
import edge_tts
import base64
import streamlit.components.v1 as components
import time
import re

# 1. 화면 설정
st.set_page_config(page_title="영어 학습기", page_icon="🎧", layout="wide")

st.header("🎧 영어 학습기")

# 앱 UI 및 표 스타일 커스텀 CSS 주입
st.markdown("""
<style>
/* 영어 원문 텍스트 영역 커스텀 */
.eng-custom-font {
    font-size: 20pt !important;
    font-weight: 700 !important;
}

/* 속도 조절 라디오 버튼 가로 간격(gap) 넓히기 */
div[role="radiogroup"] {
    gap: 3rem !important; 
}

/* 체크박스 텍스트 강제 한 줄 표시 */
div[data-testid="stCheckbox"] p {
    white-space: nowrap !important;
}

/* 📊 표 스타일 제어: 글자 크기 10, 흰색 테두리 추가 */
div[data-testid="stDataFrame"] {
    border: 1.5px solid #ffffff !important;
    border-radius: 0.25rem;
}

div[data-testid="stDataFrame"] data-grid-canvas {
    font-size: 10pt !important;
}
</style>
""", unsafe_allow_html=True)

# 상태 관리
if "is_continuous_playing" not in st.session_state:
    st.session_state.is_continuous_playing = False
if "current_play_idx" not in st.session_state:
    st.session_state.current_play_idx = 0
if "last_clicked_row" not in st.session_state:
    st.session_state.last_clicked_row = None

# 읽어줄 언어 복수 선택 UI
st.markdown("📖 **읽어줄 언어를 선택하세요 (복수 선택 가능):**")
col_l1, col_l2, _ = st.columns([1.2, 1.2, 3.6])

with col_l1:
    read_eng = st.checkbox("영어", value=True)
with col_l2:
    read_kor = st.checkbox("한국어")
    
read_langs = []

if read_eng and read_kor:
    st.markdown("<div style='margin-top: 5px; margin-bottom: 5px;'>🔄 <b>두 언어 재생 순서를 선택하세요:</b></div>", unsafe_allow_html=True)
    order_choice = st.radio(
        "재생 순서",
        options=["1. 영어 먼저 재생", "2. 한국어 먼저 재생"],
        index=0,
        horizontal=True,
        label_visibility="collapsed"
    )
    if order_choice == "1. 영어 먼저 재생":
        read_langs = ["영어", "한국어"]
    else:
        read_langs = ["한국어", "영어"]
        
    st.markdown("<div style='margin-top: 5px; margin-bottom: 5px;'>⏳ <b>언어 간 대기 시간을 선택하세요:</b></div>", unsafe_allow_html=True)
    lang_delay_choice = st.radio(
        "언어 간 대기 시간",
        options=["1초", "3초", "5초", "10초"],
        index=1,
        horizontal=True,
        label_visibility="collapsed"
    )
    if lang_delay_choice == "1초": lang_delay_ms = 1000
    elif lang_delay_choice == "3초": lang_delay_ms = 3000
    elif lang_delay_choice == "5초": lang_delay_ms = 5000
    elif lang_delay_choice == "10초": lang_delay_ms = 10000
    else: lang_delay_ms = 1000
else:
    lang_delay_ms = 0
    if read_eng: read_langs.append("영어")
    if read_kor: read_langs.append("한국어")

if not read_langs:
    st.warning("⚠️ 읽어줄 언어를 최소 1개 이상 체크해 주세요.")

st.markdown("<hr style='margin-top: 0px; margin-bottom: 15px;'>", unsafe_allow_html=True)

# TTS 선택 UI
st.markdown("🗣️ **음성 종류를 선택하세요:**")
col_v1, col_v2, col_v3, _ = st.columns([1.2, 1.2, 1.2, 2.4])

with col_v1:
    use_google = st.checkbox("Google (여성)", value=True)
with col_v2:
    use_edge_m = st.checkbox("MS Edge (남성)")
with col_v3:
    use_edge_f = st.checkbox("MS Edge (여성)")

voice_options = []
if use_google: voice_options.append("Google (여성)")
if use_edge_m: voice_options.append("MS Edge (남성)")
if use_edge_f: voice_options.append("MS Edge (여성)")

if not voice_options:
    st.warning("⚠️ 재생할 목소리를 최소 1개 이상 체크해 주세요.")

st.markdown("<hr style='margin-top: 0px; margin-bottom: 15px;'>", unsafe_allow_html=True)

# 속도 조절 UI
st.markdown("🐢 **음성 재생 속도를 선택하세요:**")
speed_choice = st.radio(
    "속도 선택",
    options=["아주 느리게 (0.6x)", "조금 느리게 (0.8x)", "보통 속도 (1.0x)"],
    index=2,
    horizontal=True,
    label_visibility="collapsed"
)

if speed_choice == "아주 느리게 (0.6x)":
    final_edge_rate_str = "-40%"
    final_gtts_slow = True
elif speed_choice == "조금 느리게 (0.8x)":
    final_edge_rate_str = "-20%"
    final_gtts_slow = False
else:
    final_edge_rate_str = "+0%"
    final_gtts_slow = False

final_speed_level_desc = speed_choice

if use_google and final_speed_level_desc == "조금 느리게 (0.8x)":
    st.caption("💡 [알림] Google TTS는 기술적 제약으로 '조금 느리게(0.8x)'를 지원하지 않아 이 단계에서는 보통 속도(1.0x)로 재생됩니다.")
elif use_google and final_speed_level_desc == "아주 느리게 (0.6x)":
    st.caption("💡 [알림] Google TTS는 기술적 제약으로 '아주 느리게(0.6x)'를 지원하지 않아 이 단계에서는 0.5배속(slow 모드)으로 재생됩니다.")

st.markdown("<hr style='margin-top: 0px; margin-bottom: 15px;'>", unsafe_allow_html=True)

# 연속 재생 대기 시간 선택 UI
st.markdown("⏱️ **연속 재생 대기 시간을 선택하세요:**")
delay_choice = st.radio(
    "대기 시간 선택",
    options=["1초", "3초", "5초"],
    index=0,
    horizontal=True,
    label_visibility="collapsed"
)

if delay_choice == "1초":
    delay_ms = 1000
elif delay_choice == "3초":
    delay_ms = 3000
else:
    delay_ms = 5000

st.markdown("<hr style='margin-top: 0px; margin-bottom: 15px;'>", unsafe_allow_html=True)

# 학습 파일 로드
EXCEL_FILE = None
for name in ["영어회화_통합본2", "영어회화_통합본", "영어 공부_통합본", "영어 공부"]: 
    for ext in ['.xlsx', '.xlsm']:
        if os.path.exists(f"{name}{ext}"):
            EXCEL_FILE = f"{name}{ext}"
            break
    if EXCEL_FILE: break

if not EXCEL_FILE:
    st.error("❌ 학습할 영어 문장 엑셀 파일이 존재하지 않습니다.")
    st.stop()

PATTERN_FILE = None
for name in ["영어패턴_선별", "핵심_회화패턴"]:
    for ext in ['.xlsx', '.csv']:
        if os.path.exists(f"{name}{ext}"):
            PATTERN_FILE = f"{name}{ext}"
            break
    if PATTERN_FILE: break

@st.cache_data
def load_master_patterns(filepath, last_modified):
    try:
        if filepath.endswith('.csv'):
            df_pat = pd.read_csv(filepath, header=None)
        else:
            df_pat = pd.read_excel(filepath, header=None, engine='openpyxl')
            
        pattern_col_idx = None
        type_col_idx = None
        pattern_row_idx = None
        
        for r in range(min(10, len(df_pat))):
            row_found = False
            for c in range(len(df_pat.columns)):
                val = str(df_pat.iloc[r, c]).strip().lower()
                if val in ['pattern', '패턴']:
                    pattern_col_idx = c
                    row_found = True
                elif '구분' in val or '시작' in val:
                    type_col_idx = c
            if row_found:
                pattern_row_idx = r
                break
                
        if pattern_col_idx is None:
            pattern_col_idx = 1
            pattern_row_idx = 0
            
        unique_patterns = {}
        for i in range(pattern_row_idx + 1, len(df_pat)):
            p = str(df_pat.iloc[i, pattern_col_idx])
            if p.lower() in ['nan', 'none', '']: continue
            
            p_clean = re.sub(r"[^\w\s']", ' ', p.lower()).strip()
            if not p_clean: continue
            
            p_type = "시작"
            if type_col_idx is not None:
                t_val = str(df_pat.iloc[i, type_col_idx])
                if '중간' in t_val:
                    p_type = "중간"
            else:
                p_type = "중간"
                
            if p_clean in unique_patterns:
                if unique_patterns[p_clean] == "시작" and p_type == "중간":
                    unique_patterns[p_clean] = "중간"
            else:
                unique_patterns[p_clean] = p_type
                
        sorted_keys = sorted(unique_patterns.keys(), key=lambda x: len(x.split()), reverse=True)
        return {k: unique_patterns[k] for k in sorted_keys}
    except Exception as e:
        st.error(f"❌ 패턴 마스터 파일 로드 중 오류: {e}")
        return {}

if PATTERN_FILE:
    pattern_mtime = os.path.getmtime(PATTERN_FILE)
    MASTER_PATTERNS = load_master_patterns(PATTERN_FILE, pattern_mtime)
else:
    st.warning("⚠️ '영어패턴_선별.xlsx' 파일을 찾을 수 없어 패턴 강조 기능이 생략됩니다.")
    MASTER_PATTERNS = {}

@st.cache_data
def load_all_data(filepath, last_modified):
    with open(filepath, "rb") as f:
        file_bytes = f.read()
    
    excel_data = io.BytesIO(file_bytes)
    xl = pd.ExcelFile(excel_data, engine='openpyxl')
    sheet_names = xl.sheet_names
    
    sheets_dict = {}
    for sheet in sheet_names:
        sheets_dict[sheet] = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet, header=0, engine='openpyxl')
        
    return sheet_names, sheets_dict

try:
    file_modified_time = os.path.getmtime(EXCEL_FILE)
    sheet_names, all_sheets = load_all_data(EXCEL_FILE, file_modified_time)
except Exception as e:
    st.error(f"❌ 데이터 로드 중 오류: {e}")
    st.stop()

col_sheet_select, col_search_input = st.columns(2)

with col_sheet_select:
    selected_sheet = st.selectbox("📂 학습할 단어장 시트:", sheet_names)

with col_search_input:
    search_query = st.text_input("🔍 검색어 입력:", "")

def process_sheet_data(df):
    def clean_text(text):
        t = str(text).strip()
        if t.lower() in ['nan', 'none', 'nat', '']: return ""
        if t.endswith('.0'): return t[:-2]
        return t
        
    for c in df.columns:
        df[c] = df[c].apply(clean_text)
    
    if '영어' in df.columns:
        df = df[df['영어'] != '']
    return df

processed_df = process_sheet_data(all_sheets[selected_sheet])

# 💡 [핵심 버그 수정 1] 고스트 렌더링 원천 차단!
# 파일 맨 밑에 있던 '다음 재생' 버튼 로직을 오디오 렌더링(TTS 생성) 이전 단계인 이곳으로 완전히 끌어올렸습니다.
# 이제 JS에서 버튼 클릭 신호가 오면, 불필요하게 예전 오디오를 만들지 않고 즉시 인덱스를 +1 한 뒤 코드를 다시 실행합니다.
if st.session_state.current_play_idx >= len(processed_df):
    st.session_state.current_play_idx = 0

col_hidden1, col_hidden2 = st.columns(2)
with col_hidden1:
    if st.button("AUTO_NEXT_BTN_XYZ", key="auto_next"):
        if st.session_state.current_play_idx + 1 < len(processed_df):
            st.session_state.current_play_idx += 1
            st.rerun() # 이전 화면 렌더링을 완전히 취소하고 즉시 새 인덱스로 재시작!
        else:
            st.success("🎉 단어장의 끝에 도달했습니다!")
            st.session_state.is_continuous_playing = False
            st.rerun()

with col_hidden2:
    if st.button("TOGGLE_CONT_BTN_XYZ", key="toggle_cont"):
        st.session_state.is_continuous_playing = not st.session_state.is_continuous_playing
        st.rerun()

@st.cache_data(show_spinner=False)
def apply_fixed_patterns(df, target_col='영어', frequent_patterns=None):
    if target_col not in df.columns:
        return df
        
    if not frequent_patterns:
        df = df.copy()
        df[target_col + '_display'] = df[target_col]
        return df
        
    highlight_color = "#d97706" 
    
    def highlight_text(text):
        if not text or not str(text).strip(): return text
        text_str = str(text)
        clean_text = re.sub(r"[^\w\s']", ' ', text_str.lower()).strip()
        padded_clean = f" {clean_text} "
        
        matched_spans = []
        
        for pat, pat_type in frequent_patterns.items():
            if f" {pat} " in padded_clean:
                pat_words = pat.split()
                pat_len = len(pat_words)
                
                boundary_start = r"(?<![\w'])"
                boundary_end = r"(?![\w'])"
                regex_parts = [boundary_start + re.escape(w) + boundary_end for w in pat_words]
                non_word_pattern = r"[^\w']*"    
                regex_str = r'(' + non_word_pattern.join(regex_parts) + r')'
                
                for match in re.finditer(regex_str, text_str, re.IGNORECASE):
                    start, end = match.span(1)
                    
                    if pat_type == "시작" and pat_len == 2:
                        prefix = text_str[:start]
                        last_punc_idx = -1
                        for p_match in re.finditer(r'[.,?!;:—\n]', prefix):
                            last_punc_idx = p_match.end()
                            
                        phrase_prefix = prefix[max(0, last_punc_idx):]
                        if re.search(r'[A-Za-z0-9]', phrase_prefix):
                            continue
                    
                    overlap = False
                    for ms, me in matched_spans:
                        if not (end <= ms or start >= me):
                            overlap = True
                            break
                    
                    if not overlap:
                        matched_spans.append((start, end))
                        
        if not matched_spans:
            return text_str
            
        matched_spans.sort(key=lambda x: x[0])
        
        result = []
        last_idx = 0
        for start, end in matched_spans:
            result.append(text_str[last_idx:start])
            actual_text = text_str[start:end]
            result.append(f"<span style='color: {highlight_color}; font-weight: bold;'>{actual_text}</span>")
            last_idx = end
        result.append(text_str[last_idx:])
        
        return "".join(result)

    df = df.copy()
    df[target_col + '_display'] = df[target_col].apply(highlight_text)
    return df

processed_df = apply_fixed_patterns(processed_df, target_col='영어', frequent_patterns=MASTER_PATTERNS)

# Edge TTS 비동기 처리 엔진
def get_edge_audio_sync(text, voice_model, rate_str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def _generate():
        communicate = edge_tts.Communicate(text, voice_model, rate=rate_str)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data
        
    result = loop.run_until_complete(_generate())
    loop.close()
    return result

@st.cache_data(show_spinner=False)
def generate_multiple_audios(eng_text, kor_text, selected_options, edge_rate, gtts_slow, read_langs_list):
    audio_results = []
    error_messages = []
    
    for opt in selected_options:
        for lang in read_langs_list:
            if lang == "한국어":
                text_to_read = kor_text
                lang_code = 'ko'
                voice_model = "ko-KR-InJoonNeural" if "남성" in opt else "ko-KR-SunHiNeural"
            else: 
                text_to_read = eng_text
                lang_code = 'en'
                voice_model = "en-US-GuyNeural" if "남성" in opt else "en-US-AriaNeural"
                
            if not text_to_read:
                continue
                
            if "Edge" in opt:
                try:
                    audio_content = get_edge_audio_sync(text_to_read, voice_model, edge_rate)
                    audio_results.append(audio_content)
                except Exception as e:
                    error_messages.append(f"Edge TTS ({opt} - {lang}) 에러: {str(e)}")
            else:
                try:
                    from gtts import gTTS
                    tts = gTTS(text=text_to_read, lang=lang_code, slow=gtts_slow)
                    fp = io.BytesIO()
                    tts.write_to_fp(fp)
                    audio_results.append(fp.getvalue())
                except Exception as e:
                    error_messages.append(f"Google TTS ({lang}) 에러: {str(e)}")
                    
    return audio_results, error_messages

def play_sequential_audio(audio_bytes_list, is_continuous=False, delay_ms=3000, lang_delay_ms=0, box_id="hidden_second_lang"):
    b64_audios = []
    if audio_bytes_list:
        for ab in audio_bytes_list:
            b64 = base64.b64encode(ab).decode()
            b64_audios.append(f"data:audio/mp3;base64,{b64}")

    js_array = str(b64_audios).replace("'", '"')
    
    cont_text = "⏹️ 중지" if is_continuous else "⏭️ 연속"
    cont_color = "#dc3545" if is_continuous else "#212529"
    
    # 💡 [핵심 버그 수정 2] HTML <audio autoplay> 태그 완전 삭제 (순수 JS 제어로 변경)
    html_code = f"""
    <style>
        body {{ margin: 0; padding: 0; overflow: hidden; }}
        #btnContainer {{ display: flex; gap: 8px; justify-content: flex-start; align-items: center; width: 100%; }}
        .custom-btn {{
            font-family: "Source Sans Pro", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            font-size: 16px; color: #ffffff; padding: 0 14px; height: 38.4px;
            display: inline-flex; justify-content: center; align-items: center;
            border-radius: 0.5rem; cursor: pointer; transition: filter 0.2s ease, transform 0.1s;
            box-sizing: border-box; user-select: none; line-height: 1; white-space: nowrap;
            border: 1px solid transparent;
        }}
        .custom-btn:hover {{ filter: brightness(0.85); }}
        .custom-btn:active {{ transform: scale(0.98); }}
        #contBtn {{ background-color: {cont_color}; border-color: {cont_color}; }}
    </style>

    <div id="btnContainer">
        <div id="contBtn" class="custom-btn">{cont_text}</div>
        <div id="playBtn" class="custom-btn">▶️ 재생</div>
    </div>
    
    <script>
        var audios = {js_array};
        var currentIdx = 0;
        var player = null; 
        var playBtn = document.getElementById("playBtn");
        var contBtn = document.getElementById("contBtn");
        var isContinuous = {'true' if is_continuous else 'false'};
        var delayMs = {delay_ms};
        var langDelayMs = {lang_delay_ms};
        var boxId = '{box_id}'; 
        
        var playedKey = 'played_' + boxId;

        function hideCurrentBoxInstantly() {{
            var targetDoc = window.parent ? window.parent.document : document;
            var box = targetDoc.getElementById(boxId);
            if (box) {{
                box.style.transition = 'none'; 
                box.style.opacity = '0';
            }}
        }}

        function revealSecondLanguage() {{
            var currentTargetDoc = window.parent ? window.parent.document : document;
            var currentHiddenBox = currentTargetDoc.getElementById(boxId);
            if (currentHiddenBox) {{
                currentHiddenBox.style.transition = 'opacity 0.4s ease-in-out';
                currentHiddenBox.style.opacity = '1';
            }}
        }}

        playBtn.innerText = isContinuous ? "🔊 연속 재생중" : "▶️ 재생";
        playBtn.style.backgroundColor = isContinuous ? "#198754" : "#0d6efd";
        playBtn.style.borderColor = isContinuous ? "#198754" : "#0d6efd";
        playBtn.style.color = "#ffffff";

        contBtn.onclick = function() {{
            var targetDoc = window.parent ? window.parent.document : document;
            var buttons = targetDoc.querySelectorAll('button');
            for(var i=0; i<buttons.length; i++) {{
                if(buttons[i].innerText.trim() === 'TOGGLE_CONT_BTN_XYZ') {{
                    buttons[i].click();
                    break;
                }}
            }}
        }};

        function playAudio(index) {{
            if (player) {{
                player.pause();
                player.removeAttribute('src');
                player.load();
                player = null; 
            }}

            if (index >= audios.length) return;

            player = new Audio(audios[index]);

            player.onplay = function() {{
                playBtn.innerText = isContinuous ? "🔊 연속 재생중" : "🔊 재생중";
                playBtn.style.backgroundColor = "#198754";
                playBtn.style.borderColor = "#198754";
                if (index >= 1) revealSecondLanguage();
            }};

            player.onended = function() {{
                currentIdx++;
                
                if (audios.length === 1 && currentIdx === 1) revealSecondLanguage();

                if(currentIdx < audios.length) {{
                    if (langDelayMs > 0) {{
                        playBtn.innerText = "⏳ 발음 대기중...";
                        playBtn.style.backgroundColor = "#ffc107";
                        playBtn.style.borderColor = "#ffc107";
                        playBtn.style.color = "#000000";
                        setTimeout(function() {{ playAudio(currentIdx); }}, langDelayMs);
                    }} else {{
                        setTimeout(function() {{ playAudio(currentIdx); }}, 50);
                    }}
                }} else {{
                    if (isContinuous) {{
                        hideCurrentBoxInstantly();
                        playBtn.innerText = "⏳ 다음 문장 대기중...";
                        playBtn.style.backgroundColor = "#ffc107";
                        playBtn.style.borderColor = "#ffc107";
                        playBtn.style.color = "#000000";
                        
                        setTimeout(function() {{
                            var targetDoc = window.parent ? window.parent.document : document;
                            var buttons = targetDoc.querySelectorAll('button');
                            for(var i=0; i<buttons.length; i++) {{
                                if(buttons[i].innerText.trim() === 'AUTO_NEXT_BTN_XYZ') {{
                                    buttons[i].click();
                                    break;
                                }}
                            }}
                        }}, delayMs);
                    }} else {{
                        playBtn.innerText = "▶️ 재생"; 
                        playBtn.style.backgroundColor = "#0d6efd"; 
                        playBtn.style.borderColor = "#0d6efd";
                        playBtn.style.color = "#ffffff";
                    }}
                }}
            }};

            var playPromise = player.play();
            if (playPromise !== undefined) {{
                playPromise.catch(function(error) {{
                    console.log("Autoplay blocked.");
                }});
            }}
        }}

        playBtn.onclick = function() {{
            if (!player || currentIdx >= audios.length) {{
                currentIdx = 0;
                playAudio(0);
            }} else if (player.paused) {{
                player.play();
            }}
        }};

        // 중복 오디오 방어벽 (Ghost re-render 방지)
        if(audios.length > 0) {{
            if (!sessionStorage.getItem(playedKey)) {{
                sessionStorage.setItem(playedKey, 'true'); 
                playAudio(0);
            }} else {{
                playBtn.innerText = isContinuous ? "⏳ 다음 문장 준비중..." : "▶️ 다시 재생";
                if (isContinuous) {{
                    playBtn.style.backgroundColor = "#ffc107";
                    playBtn.style.borderColor = "#ffc107";
                    playBtn.style.color = "#000000";
                }}
            }}
        }} else {{
            revealSecondLanguage();
            playBtn.innerText = "⚠️ 음성 없음";
            playBtn.style.backgroundColor = "#6c757d";
            playBtn.style.borderColor = "#6c757d";
            playBtn.style.cursor = "not-allowed";
        }}
    </script>
    """
    
    components.html(html_code, height=40)

if processed_df is not None:
    if search_query:
        keywords = search_query.strip().split()
        final_match_cond = pd.Series(True, index=processed_df.index)
        
        for keyword in keywords:
            keyword_match = pd.Series(False, index=processed_df.index)
            for col in processed_df.columns:
                keyword_match |= processed_df[col].astype(str).str.contains(keyword, na=False, case=False, regex=False)
            final_match_cond &= keyword_match
            
        filtered_df = processed_df[final_match_cond].reset_index(drop=True)
    else:
        filtered_df = processed_df.reset_index(drop=True)

    if "word_table" in st.session_state:
        sel = st.session_state.word_table
        sel_rows = []
        if hasattr(sel, "selection"):
            sel_rows = sel.selection.rows
        elif isinstance(sel, dict):
            sel_rows = sel.get("selection", {}).get("rows", [])
            
        if sel_rows and "current_display_indices" in st.session_state:
            ui_idx = sel_rows[0]
            if ui_idx < len(st.session_state.current_display_indices):
                current_selection = st.session_state.current_display_indices[ui_idx]
                if current_selection != st.session_state.last_clicked_row:
                    st.session_state.last_clicked_row = current_selection
                    st.session_state.is_continuous_playing = False
                    st.session_state.current_play_idx = current_selection

    target_idx = st.session_state.current_play_idx
    audio_datas = []
    
    if st.session_state.is_continuous_playing or (0 <= target_idx < len(filtered_df)):
        if target_idx < len(filtered_df):
            selected_num = filtered_df.iloc[target_idx].get('번호', '')
            selected_word = filtered_df.iloc[target_idx].get('영어', '')
            selected_word_display = filtered_df.iloc[target_idx].get('영어_display', selected_word) 
            selected_kor = filtered_df.iloc[target_idx].get('해석', '')

            if voice_options and read_langs:
                audio_datas, error_msgs = generate_multiple_audios(selected_word, selected_kor, voice_options, final_edge_rate_str, final_gtts_slow, read_langs)
                for err in error_msgs:
                    st.error(err)

            num_str = f"[{selected_num}] " if selected_num else ""
            box_padding = "6px 14px"

            if read_langs and read_langs[0] == "한국어":
                top_html = f"<span class='eng-custom-font' style='color: #0f5132;'>{selected_word_display}</span>"
                bottom_html = f"<span style='color: #3b82f6; font-size: 15pt; font-weight: bold;'>{num_str}{selected_kor}</span>"
            else:
                top_html = f"<span style='color: #0f5132; font-size: 15pt; font-weight: bold;'>{selected_kor}</span>"
                bottom_html = f"<span class='eng-custom-font' style='color: #3b82f6;'>{num_str}{selected_word_display}</span>"

            unique_id = f"hidden_box_{target_idx}_{int(time.time() * 1000)}"

            html_combined_display = f"""<div style="display: flex; flex-direction: column; gap: 6px; margin-bottom: 0px;">
                <div id="{unique_id}" style="opacity: 0; padding: {box_padding}; border-radius: 0.5rem; background-color: #d1e7dd; border: 1px solid #badbcc;">
                    {top_html}
                </div>
                <div style="padding: {box_padding}; border-radius: 0.5rem; background-color: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.2); font-size: 14px; color: inherit; display: flex; align-items: flex-start; gap: 8px;">
                    <div style="line-height: 1.5; padding-top: 1px;">
                        {bottom_html}
                    </div>
                </div>
            </div>"""
            st.markdown(html_combined_display, unsafe_allow_html=True)

            st.markdown("<hr style='margin-top: 10px; margin-bottom: 10px;'>", unsafe_allow_html=True)
            
            col_caption, col_nav, col_buttons = st.columns([0.2, 0.45, 0.35])
            
            with col_caption:
                st.markdown(f"<div style='padding-top: 8px; font-size: 14px; color: gray;'>총 <b>{len(filtered_df)}</b>개 항목</div>", unsafe_allow_html=True)
                
            with col_nav:
                new_target = st.slider("빠른 이동", min_value=1, max_value=max(1, len(filtered_df)), value=target_idx + 1, label_visibility="collapsed")
                if new_target - 1 != target_idx:
                    st.session_state.current_play_idx = new_target - 1
                    st.session_state.is_continuous_playing = False
                    st.session_state.last_clicked_row = None
                    st.rerun()
                    
            with col_buttons:
                play_sequential_audio(audio_datas, is_continuous=st.session_state.is_continuous_playing, delay_ms=delay_ms, lang_delay_ms=lang_delay_ms, box_id=unique_id)
    else:
        st.session_state.is_continuous_playing = False
        st.markdown("<hr style='margin-top: 10px; margin-bottom: 10px;'>", unsafe_allow_html=True)
        st.markdown(f"<div style='padding-top: 8px; font-size: 14px; color: gray;'>총 {len(filtered_df)}개의 항목</div>", unsafe_allow_html=True)

    display_df = filtered_df.copy()
    
    if '영어_display' in display_df.columns:
        display_df = display_df.drop(columns=['영어_display'])
    
    if target_idx in display_df.index:
        num_col = '번호' if '번호' in display_df.columns else 'No.' if 'No.' in display_df.columns else None
        if num_col:
            display_df.loc[target_idx, num_col] = f"▶ {display_df.loc[target_idx, num_col]}"
        else:
            display_df.loc[target_idx, '영어'] = f"▶ {display_df.loc[target_idx, '영어']}"
            
    st.session_state.current_display_indices = display_df.index.tolist()

    selection = st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="word_table",
        height=500
    )

components.html("""
<script>
function hideTriggerButtons() {
    var targetDoc = window.parent ? window.parent.document : document;
    var buttons = targetDoc.querySelectorAll('button');
    buttons.forEach(function(btn) {
        var btnText = btn.innerText.trim();
        if(btnText === 'AUTO_NEXT_BTN_XYZ' || btnText === 'TOGGLE_CONT_BTN_XYZ') {
            btn.style.display = 'none';
            if (btn.parentElement) {
                btn.parentElement.style.display = 'none';
            }
        }
    });
}
hideTriggerButtons();
setInterval(hideTriggerButtons, 100);
</script>
""", height=0, width=0)

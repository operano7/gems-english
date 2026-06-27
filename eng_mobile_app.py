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

/* 💡 [핵심 해결] 자막 숨김/표시 완벽 제어를 위한 강력한 CSS 클래스 주입 */
/* 이 클래스 규칙이 적용되면 브라우저는 0.001초의 깜빡임도 허용하지 않습니다. */
.hide-subtitle {
    opacity: 0 !important;
    visibility: hidden !important;
}
.show-subtitle {
    opacity: 1 !important;
    visibility: visible !important;
    transition: opacity 0.4s ease-in-out, visibility 0.4s ease-in-out !important;
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

# 두 언어 모두 선택 시 재생 순서 옵션 동적 노출
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
        
    # 언어 간 대기 시간 옵션 추가 (복수 언어 선택 시에만 노출)
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

# 파일 이름 유연성 확대
EXCEL_FILE = None
for name in ["영어회화_통합본", "영어 공부_통합본", "영어 공부"]: 
    for ext in ['.xlsx', '.xlsm']:
        if os.path.exists(f"{name}{ext}"):
            EXCEL_FILE = f"{name}{ext}"
            break
    if EXCEL_FILE: break

if not EXCEL_FILE:
    st.error("❌ 학습할 엑셀 파일이 존재하지 않습니다.")
    st.stop()

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
        # 선택된 복수의 언어를 순서대로 순회하며 음성 합성
        for lang in read_langs_list:
            if lang == "한국어":
                text_to_read = kor_text
                lang_code = 'ko'
                voice_model = "ko-KR-InJoonNeural" if "남성" in opt else "ko-KR-SunHiNeural"
            else: # 영어
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

# 고유 box_id를 전달받아 처리하도록 파라미터 추가
def play_sequential_audio(audio_bytes_list, is_continuous=False, delay_ms=3000, lang_delay_ms=0, box_id="hidden_second_lang"):
    b64_audios = []
    if audio_bytes_list:
        for ab in audio_bytes_list:
            b64 = base64.b64encode(ab).decode()
            b64_audios.append(f"data:audio/mp3;base64,{b64}")

    js_array = str(b64_audios).replace("'", '"')
    
    cont_text = "⏹️ 중지" if is_continuous else "⏭️ 연속"
    cont_color = "#dc3545" if is_continuous else "#212529"
    
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
        <audio id="sequentialPlayer" style="display: none;"></audio>
        <div id="contBtn" class="custom-btn">{cont_text}</div>
        <div id="playBtn" class="custom-btn">▶️ 재생</div>
    </div>
    
    <script>
        var audios = {js_array};
        var currentIdx = 0;
        var player = document.getElementById("sequentialPlayer");
        var playBtn = document.getElementById("playBtn");
        var contBtn = document.getElementById("contBtn");
        var isContinuous = {'true' if is_continuous else 'false'};
        var delayMs = {delay_ms};
        var langDelayMs = {lang_delay_ms};
        var boxId = '{box_id}'; 
        
        var playedKey = 'played_' + boxId;

        // 💡 [핵심 해결] CSS 클래스를 교체하여 완전히 숨깁니다.
        function hideImmediately() {{
            var targetDoc = window.parent ? window.parent.document : document;
            var box = targetDoc.getElementById(boxId);
            if (box) {{
                box.style.transition = 'none'; 
                box.classList.remove('show-subtitle');
                box.classList.add('hide-subtitle');
            }}
        }}
        hideImmediately();

        // 💡 자막 표시 시 CSS 클래스를 교체하여 부드럽게 나타나게 합니다.
        function revealSecondLanguage() {{
            var currentTargetDoc = window.parent ? window.parent.document : document;
            var currentHiddenBox = currentTargetDoc.getElementById(boxId);
            if (currentHiddenBox) {{
                currentHiddenBox.style.transition = ''; // 기존 애니메이션 복구
                currentHiddenBox.classList.remove('hide-subtitle');
                currentHiddenBox.classList.add('show-subtitle');
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

        if(audios.length > 0) {{
            player.src = audios[0];

            player.onplay = function() {{
                playBtn.innerText = isContinuous ? "🔊 연속 재생중" : "🔊 재생중";
                playBtn.style.backgroundColor = "#198754";
                playBtn.style.borderColor = "#198754";
                
                // 두 번째 언어의 음성이 스피커로 출력되는 순간 완벽하게 자막 표시
                if (currentIdx >= 1) {{
                    revealSecondLanguage();
                }}
            }};

            playBtn.onclick = function() {{
                if (player.paused) player.play();
            }};
            
            if (!sessionStorage.getItem(playedKey)) {{
                sessionStorage.setItem(playedKey, 'true'); 
                
                var playPromise = player.play();
                if (playPromise !== undefined) {{
                    playPromise.catch(function(error) {{
                        console.log("Autoplay blocked by browser policy. Waiting for user interaction.");
                    }});
                }}
            }} else {{
                playBtn.innerText = isContinuous ? "⏳ 다음 문장 준비중..." : "▶️ 다시 재생";
                if (isContinuous) {{
                    playBtn.style.backgroundColor = "#ffc107";
                    playBtn.style.borderColor = "#ffc107";
                    playBtn.style.color = "#000000";
                }}
            }}

            player.onended = function() {{
                currentIdx++;
                
                // 오디오가 1개뿐일 때 (예: 영어만 선택 시) 첫 오디오 종료 직후 정답 자막 표시
                if (audios.length === 1 && currentIdx === 1) {{
                    revealSecondLanguage();
                }}

                if(currentIdx < audios.length) {{
                    if (langDelayMs > 0) {{
                        playBtn.innerText = "⏳ 발음 대기중...";
                        playBtn.style.backgroundColor = "#ffc107";
                        playBtn.style.borderColor = "#ffc107";
                        playBtn.style.color = "#000000";
                        
                        setTimeout(function() {{
                            player.src = audios[currentIdx];
                            player.play();
                        }}, langDelayMs);
                    }} else {{
                        player.src = audios[currentIdx];
                        player.play();
                    }}
                }} else {{
                    if (isContinuous) {{
                        playBtn.innerText = "⏳ 다음 문장 대기중...";
                        playBtn.style.backgroundColor = "#ffc107";
                        playBtn.style.borderColor = "#ffc107";
                        playBtn.style.color = "#000000";
                        
                        setTimeout(function() {{
                            // 💡 다음 문장 이동 명령 직전, 현재 자막을 즉각 파기하여 잔상 차단
                            hideImmediately(); 

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

    if st.session_state.current_play_idx >= len(filtered_df):
        st.session_state.current_play_idx = 0
        
    target_idx = st.session_state.current_play_idx
    audio_datas = []
    
    if st.session_state.is_continuous_playing or (0 <= target_idx < len(filtered_df)):
        if target_idx < len(filtered_df):
            selected_num = filtered_df.iloc[target_idx].get('번호', '')
            selected_word = filtered_df.iloc[target_idx].get('영어', '')
            selected_kor = filtered_df.iloc[target_idx].get('해석', '')

            if voice_options and read_langs:
                audio_datas, error_msgs = generate_multiple_audios(selected_word, selected_kor, voice_options, final_edge_rate_str, final_gtts_slow, read_langs)
                for err in error_msgs:
                    st.error(err)

            num_str = f"[{selected_num}] " if selected_num else ""
            box_padding = "6px 14px"

            # 처음 재생언어(read_langs[0])를 무조건 아랫쪽 파란 박스에 표시
            if read_langs and read_langs[0] == "한국어":
                top_html = f"<span class='eng-custom-font' style='color: #0f5132;'>{num_str}{selected_word}</span>"
                bottom_html = f"<span style='color: #3b82f6; font-size: 15pt; font-weight: bold;'>{selected_kor}</span>"
            else:
                top_html = f"<span style='color: #0f5132; font-size: 15pt; font-weight: bold;'>{selected_kor}</span>"
                bottom_html = f"<span class='eng-custom-font' style='color: #3b82f6;'>{num_str}{selected_word}</span>"

            unique_id = f"hidden_second_lang_{target_idx}_{int(time.time() * 1000)}"

            # 💡 [핵심 해결] 인라인 투명도 대신 앱 최상단에 미리 정의해둔 'hide-subtitle' 클래스 강제 적용
            html_combined_display = f"""<div style="display: flex; flex-direction: column; gap: 6px; margin-bottom: 0px;">
                <div id="{unique_id}" class="hide-subtitle" style="padding: {box_padding}; border-radius: 0.5rem; background-color: #d1e7dd; border: 1px solid #badbcc;">
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

    # 고정 크기 윈도윙 (Fixed-Size Dynamic Windowing)
    WINDOW_TOTAL = 15
    WINDOW_HALF = WINDOW_TOTAL // 2
    
    start_row = target_idx - WINDOW_HALF
    end_row = target_idx + WINDOW_HALF + 1
    
    if start_row < 0:
        offset = abs(start_row)
        start_row = 0
        end_row = min(len(filtered_df), end_row + offset)
        
    elif end_row > len(filtered_df):
        offset = end_row - len(filtered_df)
        end_row = len(filtered_df)
        start_row = max(0, start_row - offset)
    
    display_df = filtered_df.iloc[start_row:end_row].copy()
    
    st.session_state.current_display_indices = display_df.index.tolist()
    
    def highlight_playing_row(df_to_style):
        styles = pd.DataFrame('', index=df_to_style.index, columns=df_to_style.columns)
        if target_idx in styles.index:
            styles.loc[target_idx, :] = 'background-color: rgba(25, 135, 84, 0.25);'
        return styles

    styled_df = display_df.style.apply(highlight_playing_row, axis=None)

    selection = st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="word_table"
    )

if st.button("AUTO_NEXT_BTN_XYZ", key="auto_next"):
    if st.session_state.current_play_idx + 1 < len(filtered_df):
        st.session_state.current_play_idx += 1
        st.rerun()
    else:
        st.success("🎉 단어장의 끝에 도달했습니다!")
        st.session_state.is_continuous_playing = False
        st.rerun()

if st.button("TOGGLE_CONT_BTN_XYZ", key="toggle_cont"):
    st.session_state.is_continuous_playing = not st.session_state.is_continuous_playing
    st.rerun()

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

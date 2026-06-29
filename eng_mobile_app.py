<script>
        var audios = {js_array};
        var currentIdx = 0;
        var player = document.getElementById("sequentialPlayer");
        var playBtn = document.getElementById("playBtn");
        var contBtn = document.getElementById("contBtn");
        var isContinuous = {'true' if is_continuous else 'false'};

        playBtn.innerText = isContinuous ? "🔊 연속 재생중" : "▶️ 재생";
        playBtn.style.backgroundColor = isContinuous ? "#198754" : "#0d6efd";
        playBtn.style.borderColor = isContinuous ? "#198754" : "#0d6efd";

        contBtn.onclick = function() {{
            window.parent.document.querySelectorAll('button').forEach(btn => {{
                if(btn.innerText.trim() === 'TOGGLE_CONT_BTN_XYZ') btn.click();
            }});
        }};

        if(audios.length > 0) {{
            player.src = audios[0];

            player.onplay = function() {{
                playBtn.innerText = isContinuous ? "🔊 연속 재생중" : "🔊 재생중";
                playBtn.style.backgroundColor = "#198754";
                playBtn.style.borderColor = "#198754";
            }};

            playBtn.onclick = function() {{
                if (player.paused) player.play();
            }};
            
            player.play().catch(e => console.log("Autoplay blocked"));

            player.onended = function() {{
                currentIdx++;
                if(currentIdx < audios.length) {{
                    // 문장 사이의 간격(ms 단위, 예: 1000ms = 1초)
                    setTimeout(() => {{
                        player.src = audios[currentIdx];
                        player.play();
                    }}, 1000); 
                }} else {{
                    if (isContinuous) {{
                        window.parent.document.querySelectorAll('button').forEach(btn => {{
                            if(btn.innerText.trim() === 'AUTO_NEXT_BTN_XYZ') btn.click();
                        }});
                    }} else {{
                        playBtn.innerText = "▶️ 재생"; 
                        playBtn.style.backgroundColor = "#0d6efd"; 
                        playBtn.style.borderColor = "#0d6efd";
                    }}
                }}
            }};
        }}
    </script>

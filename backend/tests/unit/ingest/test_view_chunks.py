"""청크 뷰어: 데이터가 HTML에 안전하게 들어가는지 확인합니다."""

import json
import re

from scripts.ingest.view_chunks import build_html


def test_build_html_embeds_data_and_escapes_script_end():
    content = [{"chunk_id": "c1", "content": "본문 </script><b>태그</b>", "metadata": {}}]

    html = build_html([], content, [], {"SI1_SC1": ["개요"]})

    assert html.count("</script>") == 1
    payload = re.search(r"const D = (.*);\n", html).group(1)
    data = json.loads(payload)
    assert data["content"][0]["content"] == "본문 </script><b>태그</b>"
    assert data["empty"] == {"SI1_SC1": ["개요"]}
    assert data["limits"]["max"] == 800

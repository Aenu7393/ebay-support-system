import json
import os
from pathlib import Path
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


BASE_DIR = Path(__file__).resolve().parent
FAILURE_DIR = BASE_DIR / "scraping_failures"
SELECTORS_CONFIG_PATH = BASE_DIR / "selectors_config.json"
PROPOSAL_DIR = BASE_DIR / "selector_proposals"

PROPOSAL_DIR.mkdir(exist_ok=True)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def create_selector_repair_prompt(failure_info, html, current_config):
    site_name = failure_info["site_name"]
    field_name = failure_info["field_name"]
    selectors_tried = failure_info["selectors_tried"]

    return f"""
あなたはPython Seleniumスクレイピングの保守を支援するAIです。

目的:
保存されたHTMLを分析し、失敗した項目を取得できるCSSセレクタ候補を提案してください。

対象サイト:
{site_name}

取得に失敗した項目:
{field_name}

現在試したセレクタ:
{json.dumps(selectors_tried, ensure_ascii=False, indent=2)}

現在のselectors_config.json:
{json.dumps(current_config, ensure_ascii=False, indent=2)}

HTML:
{html[:50000]}

出力ルール:
- 必ずJSONだけを返してください
- 説明文は不要です
- 既存の構造をなるべく維持してください
- 修正対象のfieldだけでなく、必要なら関連fieldも提案してください
- CSSセレクタ候補は安定性が高そうな順に並べてください
- 自動生成class名より、data-testid、id、metaタグ、意味のある属性を優先してください

出力形式:
{{
  "site_name": "{site_name}",
  "failed_field": "{field_name}",
  "proposed_selectors": {{
    "{field_name}": [
      "selector候補1",
      "selector候補2"
    ]
  }},
  "reason": "短い理由"
}}
"""


def propose_selector_fix(failure_json_path):
    failure_json_path = Path(failure_json_path)

    failure_info = load_json(failure_json_path)

    html_file_name = failure_info["html_file"]
    html_path = FAILURE_DIR / html_file_name

    html = html_path.read_text(encoding="utf-8", errors="ignore")
    current_config = load_json(SELECTORS_CONFIG_PATH)

    prompt = create_selector_repair_prompt(
        failure_info=failure_info,
        html=html,
        current_config=current_config
    )

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt
    )

    output_text = response.output_text

    try:
        proposal = json.loads(output_text)
    except json.JSONDecodeError:
        proposal = {
            "error": "AIの出力をJSONとして解析できませんでした",
            "raw_output": output_text
        }

    output_path = PROPOSAL_DIR / f"proposal_{failure_json_path.stem}.json"
    save_json(output_path, proposal)

    print(f"修正案を保存しました: {output_path}")
    return proposal


if __name__ == "__main__":
    # 例:
    # python ai_selector_repair.py
    latest_failure_json = sorted(FAILURE_DIR.glob("*.json"))[-1]
    propose_selector_fix(latest_failure_json)
# ai_engine.py - DeepSeek API + 科学处方引擎 v2

import os
import json
import re
import requests
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-chat"


def _call_api(messages: list, temperature: float = 0.7) -> str:
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 2500,
    }
    resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _parse_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = text.replace("```", "").strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(text)


# ── 科学系统提示词（FITT + ACSM + MET）────────────────────────────────────
SYSTEM_PROMPT = """你是持有 ACSM（美国运动医学会）认证的运动健康顾问，专业背景包含运动解剖学、运动生理学、运动处方学。

【科学框架要求】
必须基于以下运动科学原则制定处方：
1. FITT 原则：Frequency(频率) / Intensity(强度) / Time(时间) / Type(类型)
2. ACSM 久坐办公人群运动指南：每周≥150分钟中等强度或≥75分钟高强度有氧活动
3. MET 代谢当量分级：久坐=1.0, 轻度活动=1.5-3.0, 中等强度=3.0-6.0
4. 渐进超负荷原则：每周训练量增加不超过10%
5. 拮抗肌平衡训练：颈部前后、肩部前后、腰部前后都要兼顾

【安全约束（严格执行）】
- 颈椎问题：前屈不超过45度，禁止快速旋转，避免颈椎过伸
- 腰椎问题：禁止端坐体前屈超过90度，避免急性期主动活动
- 膝盖问题：下蹲不超过90度，避免膝盖内扣
- 急性疼痛期：只做轻柔拉伸，禁止主动收缩训练
- 眼睛疲劳：遵循 20-20-20 法则（每20分钟看20英尺外20秒）

【职场场景限制】
- 所有动作必须在办公室可完成（工位/走廊/会议室）
- 无需器材，不需换衣服
- 单次不超过15分钟
- 每个动作标注场景：工位 / 走廊 / 会议室

【输出格式】
严格返回如下 JSON，不输出任何其他文字，不使用 Markdown 代码块：

{
  "prescription_name": "简短处方名",
  "user_summary": "基于用户情况的一句话专业分析",
  "weekly_goal": "本周量化目标（如：每天10分钟，完成5天）",
  "total_minutes": 10,
  "difficulty": "初级/中级/高级",
  "fitt_summary": "F:5天/周 I:轻-中 T:10min T:拉伸+激活",
  "fitt_detail": [
    {"key": "F 频率", "value": "每周5天"},
    {"key": "I 强度", "value": "MET 1.5-2.5（轻度）"},
    {"key": "T 时间", "value": "每次10分钟"},
    {"key": "T 类型", "value": "颈椎拉伸+腰背激活"}
  ],
  "daily_routines": [
    {
      "time_slot": "午休",
      "duration_minutes": 10,
      "scene": "工位",
      "exercises": [
        {
          "name": "动作名",
          "duration": "30秒",
          "sets": 2,
          "scene": "工位",
          "description": "详细步骤说明（3-4句话）",
          "caution": "注意事项",
          "category": "颈椎/腰背/核心/眼睛/肩膀/全身",
          "met_value": 1.8,
          "muscle_groups": ["斜方肌上束", "胸锁乳突肌"],
          "scientific_basis": "基于颈椎稳定性训练原理，激活深层颈屈肌群"
        }
      ]
    }
  ]
}"""


def generate_prescription(user_data: dict) -> dict:
    body_issues = "、".join(user_data.get("body_issues", [])) or "无特殊问题"
    goals = "、".join(user_data.get("goals", [])) or "保持健康"
    available_times = "、".join(user_data.get("available_times", [])) or "午休"

    bmi = None
    h = float(user_data.get("height", 0) or 0)
    w = float(user_data.get("weight", 0) or 0)
    if h > 0 and w > 0:
        bmi = round(w / ((h / 100) ** 2), 1)

    user_prompt = f"""请为以下用户生成个性化碎片化运动处方：

【用户档案】
- 年龄段：{user_data.get('age_range', '26-35')}
- 性别：{user_data.get('gender', '未知')}
- 身高体重：{h}cm / {w}kg{f' (BMI: {bmi})' if bmi else ''}
- 工作性质：{user_data.get('work_type', '久坐办公室')}
- 日均久坐时长：{user_data.get('sitting_hours', '6-8小时')}
- 身体问题：{body_issues}
- 运动历史：{user_data.get('exercise_history', '偶尔')}
- 健康目标：{goals}
- 可运动时间段：{available_times}
- 每次时长：{user_data.get('time_per_session', '10-15分钟')}

【处方要求】
1. 碎片化设计：按用户可运动时间段分组，每个时间段3-4个动作，单次5-10分钟
2. 全天总动作数量：8-12个，覆盖不同身体部位
3. 优先针对用户的身体问题部位，但要兼顾全身平衡
4. 动作难度匹配运动历史（从不/偶尔→初级，每周1-2次→中级，每周3次+→高级）
5. met_value 范围 1.5-3.0，muscle_groups 写中文解剖名称
6. 每个动作的 scientific_basis 必须引用具体的运动科学原理或研究依据

严格按 JSON 格式输出，daily_routines 数组包含用户所有可运动时间段。"""

    try:
        content = _call_api([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ])
        result = _parse_json(content)
        return result
    except Exception as e:
        print(f"[AI] generate_prescription error: {e}")
        return get_prescription_fallback()


def generate_symptom_prescription(symptom: str, user_data: dict) -> dict:
    user_prompt = f"""用户今日主要症状：{symptom}

用户基本信息：
- 年龄段：{user_data.get('age_range', '26-35')}
- 身体问题史：{"、".join(user_data.get('body_issues', []))}
- 工作性质：{user_data.get('work_type', '久坐办公室')}
- 体重：{user_data.get('weight', 65)}kg

要求：
1. 生成针对"{symptom}"的快速专项处方
2. total_minutes 严格控制在 5-10 分钟
3. 动作数量 3-4 个，立竿见影的缓解效果
4. 每个动作包含 met_value 和 muscle_groups
5. 严格按 JSON 格式输出"""

    try:
        content = _call_api([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ], temperature=0.6)
        return _parse_json(content)
    except Exception as e:
        print(f"[AI] generate_symptom_prescription error: {e}")
        return get_symptom_fallback(symptom)


def adjust_prescription(current_prescription: dict, checkin_stats: dict, direction: str) -> dict:
    if direction == "harder":
        reason = f"你已连续{checkin_stats.get('streak', 7)}天完成率超过90%，触发渐进超负荷原则，处方升级！"
        instruction = "依据渐进超负荷原则，增加每个动作组数（+1组）或时长（+10秒），可加入稳定性训练变式。"
    else:
        reason = "近期完成率偏低，依据个体化原则适当降低运动量，先建立稳定运动习惯。"
        instruction = "减少每个动作的组数（-1组）或时长（-10秒），确保用户能轻松完成，保护运动积极性。"

    user_prompt = f"""请在以下处方基础上进行科学调整：

调整方向：{'升难度（渐进超负荷）' if direction == 'harder' else '降难度（个体化调整）'}
调整依据：{reason}
调整原则：{instruction}

用户近期运动数据：
- 连续打卡：{checkin_stats.get('streak', 0)}天
- 本周完成率：{checkin_stats.get('week_rate', 0)}%
- 平均体感：{checkin_stats.get('avg_feeling', 3)}/5分

现有处方：
{json.dumps(current_prescription, ensure_ascii=False, indent=2)}

请在 prescription_name 中标注版本（如"升级版"），在 user_summary 中说明调整依据。
严格按原 JSON 格式输出调整后的处方，保留 met_value 和 muscle_groups 字段。"""

    try:
        content = _call_api([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ], temperature=0.5)
        result = _parse_json(content)
        result["_adjust_reason"] = reason
        return result
    except Exception as e:
        print(f"[AI] adjust_prescription error: {e}")
        current_prescription["_adjust_reason"] = reason
        return current_prescription


def get_week_report_comment(stats: dict) -> str:
    user_prompt = f"""请根据以下运动数据生成一段 50-80 字的专业且温暖的周报点评：

本周运动天数：{stats.get('week_days', 0)}天
连续打卡：{stats.get('streak', 0)}天
平均体感评分：{stats.get('avg_feeling', 0)}/5
本周完成率：{stats.get('week_rate', 0)}%

要求：
- 语气专业但温暖，像运动教练在说话
- 数据好则给出积极反馈和进阶建议
- 数据差则温柔鼓励，给出科学的解释（如"身体需要适应期"）
- 提及 FITT 原则或运动科学概念加分
- 直接输出文字，不要 JSON 格式"""

    try:
        content = _call_api([{"role": "user", "content": user_prompt}], temperature=0.8)
        return content.strip()
    except Exception as e:
        print(f"[AI] get_week_report_comment error: {e}")
        return "每一次运动都是对脊柱和心肺的投资。依据 ACSM 指南，坚持规律运动需要 6-8 周才能形成习惯，你已经在正确的路上了！"


def calc_calories_from_prescription(prescription: dict, weight_kg: float) -> float:
    """基于 MET 代谢当量计算卡路里消耗"""
    if not weight_kg or weight_kg <= 0:
        return 0.0
    total = 0.0
    try:
        for routine in prescription.get("daily_routines", []):
            for ex in routine.get("exercises", []):
                met = float(ex.get("met_value", 2.0))
                sets = int(ex.get("sets", 2))
                dur_str = str(ex.get("duration", "30秒"))
                nums = re.findall(r'\d+', dur_str)
                if not nums:
                    continue
                seconds = int(nums[0])
                if '分' in dur_str:
                    seconds *= 60
                hours = seconds / 3600
                # 卡路里 = MET × 体重(kg) × 时间(h) × 组数
                total += met * weight_kg * hours * sets
    except Exception as e:
        print(f"[Calories] calc error: {e}")
    return round(total, 1)


def get_prescription_fallback() -> dict:
    return {
        "prescription_name": "基础颈腰修复10分钟",
        "user_summary": "针对久坐人群的基础修复方案，依据 ACSM 指南设计，重点激活深层颈屈肌和腰椎多裂肌",
        "weekly_goal": "每天10分钟，坚持5天",
        "total_minutes": 10,
        "difficulty": "初级",
        "fitt_summary": "F:5天/周 I:MET≈2.0 T:10min T:拉伸+激活",
        "fitt_detail": [
            {"key": "F 频率", "value": "每周5天"},
            {"key": "I 强度", "value": "MET 1.8-2.2（轻度）"},
            {"key": "T 时间", "value": "每次10分钟"},
            {"key": "T 类型", "value": "颈椎拉伸+腰背激活"}
        ],
        "daily_routines": [
            {
                "time_slot": "午休",
                "duration_minutes": 10,
                "scene": "工位",
                "exercises": [
                    {
                        "name": "颈部慢速侧屈",
                        "duration": "30秒",
                        "sets": 2,
                        "scene": "工位",
                        "description": "坐直，缓慢将头向右侧倾斜，耳朵靠近肩膀，感受颈部侧面牵拉感，保持15秒。换另一侧重复。动作全程保持肩膀下沉放松。",
                        "caution": "前屈不超过45度，有颈椎病者幅度减半，出现麻木立即停止",
                        "category": "颈椎",
                        "met_value": 1.8,
                        "muscle_groups": ["胸锁乳突肌", "斜角肌", "斜方肌上束"],
                        "scientific_basis": "针对颈部侧屈肌群的静态拉伸，改善颈椎侧方稳定性，缓解长期低头引起的肌筋膜紧张"
                    },
                    {
                        "name": "坐姿猫牛式",
                        "duration": "40秒",
                        "sets": 2,
                        "scene": "工位",
                        "description": "坐在椅子前1/3处，双手放膝盖。吸气时挺胸塌腰（牛式），感受脊柱伸展；呼气时弓背收腹（猫式），感受脊柱屈曲。动作配合呼吸，缓慢有控制地交替。",
                        "caution": "幅度从小到大，腰部有急性疼痛时跳过此动作",
                        "category": "腰背",
                        "met_value": 2.0,
                        "muscle_groups": ["竖脊肌", "多裂肌", "腹横肌"],
                        "scientific_basis": "激活腰椎多裂肌和腹横肌，改善腰椎节段稳定性，是 ACSM 推荐的办公室腰部保健动作"
                    },
                    {
                        "name": "肩胛骨收紧（W字）",
                        "duration": "30秒",
                        "sets": 3,
                        "scene": "工位",
                        "description": "坐直，双臂向两侧抬起呈W字形，用力将两侧肩胛骨向脊柱方向夹紧，同时手肘向后拉。保持收紧5秒后完全放松。重复10次。",
                        "caution": "不要耸肩，保持颈部放松，动作过程中保持正常呼吸",
                        "category": "肩膀",
                        "met_value": 2.2,
                        "muscle_groups": ["菱形肌", "中下斜方肌", "冈下肌"],
                        "scientific_basis": "针对圆肩驼背的矫正训练，激活长期被抑制的中下斜方肌和菱形肌，纠正上交叉综合征"
                    }
                ]
            }
        ]
    }


def get_symptom_fallback(symptom: str) -> dict:
    templates = {
        "颈椎酸痛": {
            "prescription_name": "颈椎即时缓解5分钟",
            "user_summary": "针对颈椎疲劳的即时干预，以深层颈屈肌激活和颈部筋膜松解为核心",
            "weekly_goal": "缓解今日颈椎不适",
            "total_minutes": 5, "difficulty": "初级",
            "fitt_summary": "F:即时 I:MET≈1.8 T:5min T:拉伸+松解",
            "fitt_detail": [{"key":"F","value":"即时"},{"key":"I","value":"MET 1.8"},{"key":"T","value":"5分钟"},{"key":"T类型","value":"拉伸松解"}],
            "daily_routines": [{"time_slot":"当前","duration_minutes":5,"scene":"工位","exercises":[
                {"name":"颈椎后缩（下巴收紧）","duration":"20秒","sets":3,"scene":"工位",
                 "description":"保持目视前方，将下巴缓慢向后收，感受颈后部伸展，保持5秒后放松。避免低头，只做后缩动作。",
                 "caution":"动作幅度小而精准，出现头晕立即停止","category":"颈椎","met_value":1.8,
                 "muscle_groups":["深层颈屈肌","枕下肌群"],
                 "scientific_basis":"下巴后缩激活深层颈屈肌，纠正头前位姿势（ACSM颈椎稳定性训练核心动作）"},
                {"name":"颈部侧屈拉伸","duration":"30秒","sets":2,"scene":"工位",
                 "description":"头缓慢向右侧倾，右手轻放头顶辅助，感受左侧颈部牵拉，保持20秒。换侧重复。",
                 "caution":"辅助手不要用力拉扯，仅做轻微引导","category":"颈椎","met_value":1.6,
                 "muscle_groups":["斜角肌","胸锁乳突肌"],
                 "scientific_basis":"静态拉伸颈侧屈肌群，改善颈部血液循环，MET≈1.6属低强度安全范围"},
                {"name":"颈部慢速旋转","duration":"30秒","sets":2,"scene":"工位",
                 "description":"下巴微收，头部缓慢向左转至最大幅度，停留3秒，再转向右侧。全程保持肩膀放松。",
                 "caution":"禁止快速旋转，有颈椎病史者幅度减半","category":"颈椎","met_value":1.5,
                 "muscle_groups":["颈回旋肌","多裂肌"],
                 "scientific_basis":"慢速旋转改善颈椎关节活动度，激活颈部深层稳定肌群"},
            ]}]
        },
        "腰背僵硬": {
            "prescription_name": "腰背松解7分钟",
            "user_summary": "针对久坐导致的腰背僵硬，以脊柱活动度恢复和核心激活为核心",
            "weekly_goal": "缓解腰背僵硬，恢复脊柱活动度",
            "total_minutes": 7, "difficulty": "初级",
            "fitt_summary": "F:即时 I:MET≈2.0 T:7min T:活动度+核心",
            "fitt_detail": [{"key":"F","value":"即时"},{"key":"I","value":"MET 2.0"},{"key":"T","value":"7分钟"},{"key":"T类型","value":"活动度训练"}],
            "daily_routines": [{"time_slot":"当前","duration_minutes":7,"scene":"工位","exercises":[
                {"name":"坐姿猫牛式","duration":"40秒","sets":3,"scene":"工位",
                 "description":"坐在椅子前1/3处，双手放膝盖。吸气时挺胸塌腰（牛式），呼气时弓背收腹（猫式），缓慢交替。",
                 "caution":"动作跟随呼吸节奏，不要憋气","category":"腰背","met_value":2.0,
                 "muscle_groups":["竖脊肌","多裂肌","腹横肌"],
                 "scientific_basis":"猫牛式是脊柱活动度训练经典动作，可有效改善椎间盘营养供给（MET≈2.0）"},
                {"name":"坐姿脊柱旋转","duration":"30秒","sets":2,"scene":"工位",
                 "description":"双脚踩地，双手交叉放胸前，躯干缓慢向右旋转至最大幅度，停留3秒，换侧。",
                 "caution":"旋转来自胸椎，腰椎不要过度扭转","category":"腰背","met_value":1.8,
                 "muscle_groups":["胸椎旋转肌","腹斜肌"],
                 "scientific_basis":"胸椎旋转训练改善脊柱整体活动度，减少腰椎代偿性压力"},
                {"name":"站立前屈放松","duration":"30秒","sets":2,"scene":"走廊",
                 "description":"站立，双脚与肩同宽，缓慢向前弯腰，双手自然下垂，感受腰背部拉伸，保持15秒后缓慢起身。",
                 "caution":"起身时膝盖微弯，避免快速直立导致头晕","category":"腰背","met_value":1.5,
                 "muscle_groups":["竖脊肌","腘绳肌"],
                 "scientific_basis":"前屈拉伸有效缓解竖脊肌紧张，改善腰背部血液循环"},
            ]}]
        },
        "肩膀紧张": {
            "prescription_name": "肩颈放松6分钟",
            "user_summary": "针对肩部耸肩和肌肉紧绷，以肩胛骨稳定性训练和斜方肌松解为核心",
            "weekly_goal": "缓解肩部紧张，改善肩胛骨活动度",
            "total_minutes": 6, "difficulty": "初级",
            "fitt_summary": "F:即时 I:MET≈1.9 T:6min T:松解+稳定",
            "fitt_detail": [{"key":"F","value":"即时"},{"key":"I","value":"MET 1.9"},{"key":"T","value":"6分钟"},{"key":"T类型","value":"松解+稳定"}],
            "daily_routines": [{"time_slot":"当前","duration_minutes":6,"scene":"工位","exercises":[
                {"name":"肩胛骨后缩下沉","duration":"20秒","sets":4,"scene":"工位",
                 "description":"坐直，双肩向后夹紧（肩胛骨靠拢），同时向下沉肩，保持5秒后放松。想象用肩胛骨夹住一支铅笔。",
                 "caution":"不要耸肩，保持颈部放松","category":"肩膀","met_value":1.9,
                 "muscle_groups":["菱形肌","斜方肌中下束"],
                 "scientific_basis":"肩胛骨后缩激活菱形肌和斜方肌中下束，对抗久坐导致的圆肩姿势（ACSM推荐）"},
                {"name":"肩部绕环","duration":"30秒","sets":2,"scene":"工位",
                 "description":"双肩同时向前、向上、向后、向下做大幅度绕环，各方向各5圈，再反向重复。",
                 "caution":"动作缓慢，感受肩关节充分活动","category":"肩膀","met_value":1.8,
                 "muscle_groups":["三角肌","肩袖肌群"],
                 "scientific_basis":"肩关节全范围活动改善关节滑液分泌，预防肩周炎"},
                {"name":"W字肩胛骨激活","duration":"20秒","sets":3,"scene":"工位",
                 "description":"双臂抬起呈W形（肘部弯曲90度，手掌朝前），用力将肩胛骨向脊柱方向夹紧，保持5秒。",
                 "caution":"保持腰背挺直，不要弓背","category":"肩膀","met_value":2.0,
                 "muscle_groups":["菱形肌","斜方肌中束","冈下肌"],
                 "scientific_basis":"W字动作是肩胛骨稳定性训练的黄金动作，MET≈2.0，有效激活肩胛骨稳定肌群"},
            ]}]
        },
        "眼睛疲劳": {
            "prescription_name": "护眼放松5分钟",
            "user_summary": "针对屏幕疲劳导致的眼睛干涩，以睫状肌放松和眼周血液循环改善为核心",
            "weekly_goal": "缓解视疲劳，保护视力",
            "total_minutes": 5, "difficulty": "初级",
            "fitt_summary": "F:即时 I:MET≈1.2 T:5min T:眼部放松",
            "fitt_detail": [{"key":"F","value":"即时"},{"key":"I","value":"MET 1.2"},{"key":"T","value":"5分钟"},{"key":"T类型","value":"眼部放松"}],
            "daily_routines": [{"time_slot":"当前","duration_minutes":5,"scene":"工位","exercises":[
                {"name":"20-20-20护眼法","duration":"20秒","sets":3,"scene":"工位",
                 "description":"停止看屏幕，望向至少6米（20英尺）外的物体，保持20秒。让睫状肌完全放松。",
                 "caution":"找窗外远处景物，不要看室内近处物体","category":"眼睛","met_value":1.2,
                 "muscle_groups":["睫状肌"],
                 "scientific_basis":"20-20-20法则由美国验光协会推荐，有效缓解睫状肌痉挛，预防近视加深"},
                {"name":"眼球转动操","duration":"30秒","sets":2,"scene":"工位",
                 "description":"闭眼，眼球缓慢向上、右、下、左各方向转动，各停留2秒，顺时针5圈后逆时针5圈。",
                 "caution":"动作缓慢，不要快速转动","category":"眼睛","met_value":1.2,
                 "muscle_groups":["眼外肌"],
                 "scientific_basis":"眼球运动激活6条眼外肌，改善眼周血液循环，缓解眼肌疲劳"},
                {"name":"热敷眼部","duration":"60秒","sets":1,"scene":"工位",
                 "description":"双手搓热后，轻轻覆盖在闭合的眼睛上，感受温热感，保持1分钟。可重复搓手2-3次。",
                 "caution":"手掌不要直接压迫眼球","category":"眼睛","met_value":1.1,
                 "muscle_groups":["眼轮匝肌"],
                 "scientific_basis":"热敷促进眼周血液循环，缓解睑板腺功能障碍，改善泪液分泌"},
            ]}]
        },
        "整体疲惫": {
            "prescription_name": "全身激活8分钟",
            "user_summary": "针对整体疲惫状态，以交感神经激活和全身血液循环促进为核心",
            "weekly_goal": "提升精力，恢复工作状态",
            "total_minutes": 8, "difficulty": "初级",
            "fitt_summary": "F:即时 I:MET≈2.5 T:8min T:有氧+拉伸",
            "fitt_detail": [{"key":"F","value":"即时"},{"key":"I","value":"MET 2.5"},{"key":"T","value":"8分钟"},{"key":"T类型","value":"有氧激活"}],
            "daily_routines": [{"time_slot":"当前","duration_minutes":8,"scene":"走廊","exercises":[
                {"name":"原地踏步走","duration":"60秒","sets":2,"scene":"走廊",
                 "description":"原地抬腿踏步，大腿抬至与地面平行，双臂自然摆动，保持正常呼吸节奏。",
                 "caution":"穿平底鞋进行，避免高跟鞋","category":"全身","met_value":2.8,
                 "muscle_groups":["股四头肌","臀大肌","腓肠肌"],
                 "scientific_basis":"低强度有氧运动（MET≈2.8）促进内啡肽分泌，快速改善精力状态"},
                {"name":"深呼吸扩胸","duration":"40秒","sets":3,"scene":"工位",
                 "description":"双手交叉放脑后，深吸气同时肘部向后展开扩胸，呼气时肘部向前合拢。节奏：吸气4秒，呼气6秒。",
                 "caution":"呼气时间长于吸气，激活副交感神经","category":"全身","met_value":1.5,
                 "muscle_groups":["胸大肌","肋间肌","膈肌"],
                 "scientific_basis":"4-6呼吸法激活副交感神经，降低皮质醇水平，改善专注力（哈佛医学院推荐）"},
                {"name":"站立体侧拉伸","duration":"30秒","sets":2,"scene":"走廊",
                 "description":"站立，右手举过头顶，身体向左侧弯，感受右侧腰部和肋骨拉伸，保持15秒。换侧重复。",
                 "caution":"侧弯时保持身体在同一平面，不要前倾","category":"全身","met_value":1.6,
                 "muscle_groups":["腰方肌","肋间肌","背阔肌"],
                 "scientific_basis":"侧屈拉伸改善胸腰筋膜弹性，促进全身血液循环，缓解整体疲劳感"},
            ]}]
        },
    }
    return templates.get(symptom, templates["整体疲惫"])

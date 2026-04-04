# 将 DEEPSEEK_API_KEY 替换为你的真实密钥（在 .env 文件或 Railway 环境变量中设置）
# app.py - Flask 主程序 v2

import os
import json
import threading
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, jsonify
from dotenv import load_dotenv

load_dotenv()

from database import (init_db, create_user, get_user, save_prescription,
                      get_active_prescription, get_prescription_history,
                      save_checkin, get_today_checkin, get_checkin_stats,
                      save_symptom_log, get_all_active_users)
from ai_engine import (generate_prescription, generate_symptom_prescription,
                       adjust_prescription, get_week_report_comment,
                       calc_calories_from_prescription, get_prescription_fallback)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "jidong-secret-2024-change-me")

with app.app_context():
    init_db()


# ── 工具函数 ────────────────────────────────────────────────────────────────

def _get_greeting(nickname: str) -> str:
    hour = datetime.now().hour
    if hour < 6:    g = "夜深了"
    elif hour < 11: g = "早上好"
    elif hour < 14: g = "午休时间"
    elif hour < 18: g = "下午好"
    else:           g = "晚上好"
    return f"{g}，{nickname}！"


def _calc_bmi(height, weight):
    try:
        h, w = float(height or 0), float(weight or 0)
        if h > 0 and w > 0:
            bmi = round(w / ((h / 100) ** 2), 1)
            if bmi < 18.5:   cat = "偏轻"
            elif bmi < 24.0: cat = "正常"
            elif bmi < 28.0: cat = "偏重"
            else:             cat = "偏胖"
            return bmi, cat
    except Exception:
        pass
    return None, None


def _check_and_adjust(user_id: str):
    stats = get_checkin_stats(user_id, days=7)
    records_7d = [r for r in stats["records"]
                  if r["checkin_date"] >= (date.today() - timedelta(days=7)).isoformat()]
    if len(records_7d) < 7:
        return
    avg_rate = sum(r["completion_rate"] for r in records_7d) / len(records_7d)
    active = get_active_prescription(user_id)
    if not active:
        return
    if avg_rate >= 0.9:
        new_p = adjust_prescription(active["prescription"], stats, "harder")
        save_prescription(user_id, new_p, "upgrade")
    elif avg_rate <= 0.5:
        new_p = adjust_prescription(active["prescription"], stats, "easier")
        save_prescription(user_id, new_p, "downgrade")


def _daily_task():
    import time
    while True:
        now = datetime.now()
        next_run = datetime.combine(date.today() + timedelta(days=1),
                                    datetime.min.time().replace(hour=1))
        time.sleep(max((next_run - now).total_seconds(), 60))
        for uid in get_all_active_users():
            try:
                _check_and_adjust(uid)
            except Exception as e:
                print(f"[CRON] {uid}: {e}")


threading.Thread(target=_daily_task, daemon=True).start()


# ── 路由 ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("onboard.html")


@app.route("/onboard", methods=["POST"])
def onboard():
    data = {}
    for field in ["body_issues", "goals", "available_times"]:
        data[field] = request.form.getlist(field)
    for f in ["nickname", "age_range", "gender", "height", "weight",
              "work_type", "sitting_hours", "exercise_history", "time_per_session"]:
        data[f] = request.form.get(f, "")

    user_id = create_user(data)
    if not user_id:
        return jsonify({"error": "创建用户失败"}), 500

    prescription = generate_prescription(data)
    save_prescription(user_id, prescription, "initial")
    return jsonify({"user_id": user_id, "redirect": f"/home/{user_id}"})


@app.route("/home/<user_id>")
def home(user_id):
    user = get_user(user_id)
    if not user:
        return redirect(url_for("index"))

    stats = get_checkin_stats(user_id)
    today_checkin = get_today_checkin(user_id)
    active_rx = get_active_prescription(user_id)
    greeting = _get_greeting(user["nickname"])
    bmi, bmi_cat = _calc_bmi(user.get("height"), user.get("weight"))

    # 格式化日期
    weekdays = ["周一","周二","周三","周四","周五","周六","周日"]
    now = datetime.now()
    now_date = f"{now.month}月{now.day}日 {weekdays[now.weekday()]}"

    return render_template("index.html",
                           user=user, stats=stats,
                           today_checkin=today_checkin,
                           active_rx=active_rx,
                           greeting=greeting,
                           bmi=bmi, bmi_cat=bmi_cat,
                           now_date=now_date,
                           user_id=user_id)


@app.route("/prescription/<user_id>")
def prescription(user_id):
    user = get_user(user_id)
    if not user:
        return redirect(url_for("index"))

    active_rx = get_active_prescription(user_id)
    if not active_rx:
        return redirect(url_for("index"))

    history = get_prescription_history(user_id)

    # 计算卡路里
    weight = float(user.get("weight") or 65)
    calories = calc_calories_from_prescription(active_rx["prescription"], weight)

    return render_template("prescription.html",
                           user=user, rx=active_rx,
                           history=history,
                           calories=calories,
                           user_id=user_id)


@app.route("/symptom/<user_id>", methods=["GET"])
def symptom_get(user_id):
    user = get_user(user_id)
    if not user:
        return redirect(url_for("index"))
    return render_template("symptom.html", user=user, user_id=user_id)


@app.route("/symptom/<user_id>", methods=["POST"])
def symptom_post(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "用户不存在"}), 404

    symptom = (request.json or {}).get("symptom", "")
    if not symptom:
        return jsonify({"error": "请选择症状"}), 400

    p = generate_symptom_prescription(symptom, user)
    save_symptom_log(user_id, symptom, p)

    weight = float(user.get("weight") or 65)
    calories = calc_calories_from_prescription(p, weight)
    return jsonify({"prescription": p, "calories": calories})


@app.route("/checkin/<user_id>", methods=["GET"])
def checkin_get(user_id):
    user = get_user(user_id)
    if not user:
        return redirect(url_for("index"))

    active_rx = get_active_prescription(user_id)
    today_checkin = get_today_checkin(user_id)
    stats = get_checkin_stats(user_id)

    return render_template("checkin.html",
                           user=user, rx=active_rx,
                           today_checkin=today_checkin,
                           stats=stats,
                           user_id=user_id)


@app.route("/checkin/<user_id>", methods=["POST"])
def checkin_post(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "用户不存在"}), 404

    data = request.json or {}
    ok = save_checkin(user_id, data)
    if not ok:
        return jsonify({"error": "打卡失败"}), 500

    stats = get_checkin_stats(user_id)
    streak = stats["streak"]

    # 计算本次卡路里
    calories = 0
    active_rx = get_active_prescription(user_id)
    if active_rx:
        weight = float(user.get("weight") or 65)
        total_cal = calc_calories_from_prescription(active_rx["prescription"], weight)
        completion = data.get("completion_rate", 0)
        calories = round(total_cal * completion, 1)

    # 里程碑
    milestone = None
    if streak == 7:
        milestone = {"days": 7, "msg": "🌟 坚持7天！习惯正在形成，研究表明此阶段最关键！"}
    elif streak == 14:
        milestone = {"days": 14, "msg": "💪 两周达成！你已超越80%的挑战者，继续！"}
    elif streak == 21:
        milestone = {"days": 21, "msg": "🏆 21天习惯达成！恭喜完成科学认证的习惯周期！"}

    return jsonify({
        "success": True,
        "streak": streak,
        "calories": calories,
        "milestone": milestone,
        "week_rate": stats["week_rate"],
    })


@app.route("/report/<user_id>")
def report(user_id):
    user = get_user(user_id)
    if not user:
        return redirect(url_for("index"))

    stats = get_checkin_stats(user_id, days=14)
    comment = get_week_report_comment(stats)
    history = get_prescription_history(user_id)

    # 本周/上周对比
    today = date.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    last_week_start = (today - timedelta(days=today.weekday() + 7)).isoformat()
    last_week_end = (today - timedelta(days=today.weekday() + 1)).isoformat()

    this_week_records = [r for r in stats["records"] if r["checkin_date"] >= week_start]
    last_week_records = [r for r in stats["records"]
                         if last_week_start <= r["checkin_date"] <= last_week_end]
    this_week_days = len(this_week_records)
    last_week_days = len(last_week_records)

    summary = f"本周运动{this_week_days}天"
    if this_week_days > last_week_days:
        summary += f"，比上周多{this_week_days - last_week_days}天 📈"
    elif this_week_days < last_week_days:
        summary += f"，比上周少{last_week_days - this_week_days}天，加油！"
    else:
        summary += "，与上周持平，继续保持！"

    # 本周总卡路里
    active_rx = get_active_prescription(user_id)
    total_calories = 0
    if active_rx:
        weight = float(user.get("weight") or 65)
        per_session = calc_calories_from_prescription(active_rx["prescription"], weight)
        total_calories = round(sum(
            per_session * r["completion_rate"] for r in this_week_records
        ), 1)

    return render_template("report.html",
                           user=user, stats=stats,
                           comment=comment, summary=summary,
                           history=history,
                           this_week_days=this_week_days,
                           last_week_days=last_week_days,
                           total_calories=total_calories,
                           user_id=user_id)


@app.route("/api/checkin_stats/<user_id>")
def api_checkin_stats(user_id):
    stats = get_checkin_stats(user_id, days=14)
    records = stats.get("records", [])

    labels = [r["checkin_date"][-5:] for r in records]
    rates = [round(r["completion_rate"] * 100, 1) for r in records]
    feelings = [r["feeling_score"] for r in records]

    week_start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    week_records = [r for r in records if r["checkin_date"] >= week_start]
    week_done = len(week_records)

    return jsonify({
        "labels": labels, "rates": rates, "feelings": feelings,
        "week_done": week_done, "week_miss": max(7 - week_done, 0),
        "streak": stats["streak"],
        "week_rate": stats["week_rate"],
        "avg_feeling": stats["avg_feeling"],
    })


@app.route("/wellness/<user_id>")
def wellness(user_id):
    user = get_user(user_id)
    if not user:
        return redirect("/")
    return render_template("wellness.html", user_id=user_id, user=user)


@app.route("/api/regenerate_prescription/<user_id>", methods=["POST"])
def api_regenerate_prescription(user_id):
    user = get_user(user_id)
    if not user:
        return jsonify({"error": "用户不存在"}), 404
    try:
        prescription = generate_prescription(user)
        save_prescription(user_id, prescription, "initial")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/adjust_prescription/<user_id>", methods=["POST"])
def api_adjust_prescription(user_id):
    direction = (request.json or {}).get("direction", "harder")
    active = get_active_prescription(user_id)
    if not active:
        return jsonify({"error": "无处方"}), 404

    stats = get_checkin_stats(user_id)
    new_p = adjust_prescription(active["prescription"], stats, direction)
    trigger = "upgrade" if direction == "harder" else "downgrade"
    save_prescription(user_id, new_p, trigger)
    return jsonify({"success": True, "prescription": new_p})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port,
            debug=os.getenv("FLASK_DEBUG", "0") == "1")

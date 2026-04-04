# 即动 - 职场运动伴侣

**即动**是面向职场久坐人群的 AI 运动处方 Web 应用。用户扫码即用，无需下载，AI 根据个人情况生成专属运动处方，支持每日打卡和周报追踪。

## 功能特性

- AI 生成个性化运动处方（DeepSeek API）
- 症状快速处方（颈椎/腰背/肩膀/眼睛/疲惫）
- 每日打卡 + 体感评分 + 连续天数统计
- ECharts 数据可视化周报
- PWA 支持（可添加到手机桌面）
- 处方自动迭代（连续完成/失败自动调整难度）

---

## 本地运行

```bash
# 1. 克隆项目
git clone <repo-url>
cd jidong

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 DEEPSEEK_API_KEY

# 4. 启动
python app.py
# 访问 http://localhost:5000
```

---

## 替换 API Key

1. 访问 [DeepSeek 开放平台](https://platform.deepseek.com) 申请 API Key
2. 打开 `.env` 文件，将 `DEEPSEEK_API_KEY=sk-your_deepseek_api_key_here` 中的值替换为真实密钥
3. 重启应用

---

## Railway 一键部署

1. **Fork** 本项目到你的 GitHub
2. 打开 [Railway](https://railway.app) → **New Project** → **Deploy from GitHub repo**
3. 选择刚 Fork 的仓库
4. 进入 **Variables** 标签页，添加以下环境变量：
   - `DEEPSEEK_API_KEY` = 你的 DeepSeek API Key
   - `SECRET_KEY` = 任意随机字符串（如 `myrandomsecret2024`）
5. Railway 自动识别 `Procfile` 完成部署，几分钟后生成访问链接
6. 复制链接生成二维码，手机扫码即可访问

> 注意：Railway 免费计划每月有 500 小时运行时间，SQLite 数据存储在容器内，重新部署后数据会清空。生产环境建议使用 Railway 提供的 PostgreSQL 插件。

---

## 页面说明

| 页面 | 路由 | 说明 |
|------|------|------|
| 问卷 | `/` | 新用户填写档案，AI 生成处方 |
| 首页 | `/home/<uid>` | 今日状态 + 快速入口 |
| 处方 | `/prescription/<uid>` | 查看完整处方动作 |
| 症状 | `/symptom/<uid>` | 快速生成今日症状处方 |
| 打卡 | `/checkin/<uid>` | 每日打卡记录 |
| 周报 | `/report/<uid>` | 数据可视化 + AI 点评 |

# Daily Report System (v1.2)

最小可运行日报系统：

- 抓新闻（RSS）
- 抓新品（RSS）
- 自动识别节日 / 促销节点
- 生成 `docs/index.html` 和节日详情页
- 可配合 GitHub Actions 或系统定时任务每天自动执行

## 安装

```bash
pip install -r requirements.txt

## 运行
```bash
python scripts/main.py
```

## 输出
docs/index.html
docs/*.html
data/raw/*.json
data/processed/daily_payload.json
logs/daily_report.log


## GitHub Actions

仓库内置 .github/workflows/daily.yml，支持：

定时自动执行
手动触发执行

执行完成后会自动更新：

docs/
data/raw/
data/processed/
logs/
时区说明

系统内部展示日期统一按 Asia/Shanghai 生成。
这样可以避免 GitHub Actions 在 UTC 时区运行时，页面顶部日期显示为前一天的问题。

为什么 Action 成功但页面看起来没更新

常见原因有：

当次抓取内容与前一次相比没有形成可见差异
RSS / Google News 在早晨存在聚合延迟
之前版本使用 UTC 日期，导致页面标题日期看起来还是前一天

当前版本已增加：

北京时间日期生成
双时点自动补跑
产物校验
抓取结果摘要日志

## Windows 任务计划
程序/脚本：
```text
python
```

参数：
```text
D:\your_path\daily-report\scripts\main.py
```

起始于：
```text
D:\your_path\daily-report
```

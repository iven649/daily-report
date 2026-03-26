# Daily Report System (v1.1)

最小可运行日报系统：
- 抓新闻（RSS）
- 抓新品（RSS）
- 自动识别节日/促销节点
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
- `docs/index.html`
- `docs/*.html`


## GitHub Actions

仓库内置 .github/workflows/daily.yml，支持：

定时自动执行
手动触发执行

执行完成后会自动更新 docs/ 目录内容，并提交到仓库。

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

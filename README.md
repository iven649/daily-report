# Daily Report System (MVP)

最小可运行日报系统：
- 抓新闻（RSS）
- 抓新品（RSS）
- 自动识别节日/促销节点
- 生成 `index.html` 和节日详情页
- 可配合系统定时任务每天自动执行

## 安装
```bash
pip install -r requirements.txt
```

## 运行
```bash
python scripts/main.py
```

## 输出
- `dist/index.html`
- `dist/*.html`

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

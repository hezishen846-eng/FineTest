# Streamlit Community Cloud 部署

已部署应用：https://ev-campus-final-hezishen846.streamlit.app/

GitHub 仓库：https://github.com/hezishen846-eng/FineTest

部署入口：`main` 分支的 `app.py`，Python 3.13。

本目录是完整项目根目录，云端入口为 `app.py`。

1. 将代码上传到 GitHub，保留 `views/`、`data/`、`.streamlit/` 的目录结构。
2. 包含根目录 `ev_campus_dataset.csv` 和 `requirements.txt`。
3. 不上传 `.venv/`、`.idea/`、缓存、日志或任何 secrets。
4. 在 https://share.streamlit.io 创建应用，选择仓库、分支和 `app.py`。高级设置选择 Python 3.13（与本机验证环境一致）。
5. 部署后核验总览、告警、数据下载和销售页面，再复制应用网址。

本机启动：
```bash
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8512
```

云端部署不需要上传本机虚拟环境，也不需要本机保持开机。应用保留模拟字段标识。

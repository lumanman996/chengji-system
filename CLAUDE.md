# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

成绩核算 Web 应用。上传登分表 Excel → 自动计算班级排名、教师评比 → 导出四张标准报表。

**GitHub：** https://github.com/lumanman996/chengji-system
**依赖：** Flask 3.1.3、Pandas 3.0.2、openpyxl 3.1.5

## 常用命令

```bash
# 开发模式
python app.py                          # 启动 Flask 开发服务器，http://127.0.0.1:5000

# 安装依赖
pip install -r requirements.txt        # flask, pandas, openpyxl

# 打包为 exe（需先关闭正在运行的 exe）
打包.bat                               # 一键打包，输出 dist\成绩核算系统\
python -m PyInstaller chengji.spec --noconfirm
python -m PyInstaller admin_genkey.spec --noconfirm  # 打包管理员工具
```

## 环境变量

PyInstaller 打包后，系统自动设置以下环境变量供其他模块使用：
- `CHENGJI_APP_DIR` — 可写数据目录（config/uploads），exe 同级目录
- `CHENGJI_BUNDLE_DIR` — 资源目录（templates/static），临时解压目录

## 架构

**后端：** Python 3 + Flask，单进程 Web 应用，JSON 文件持久化配置。

**数据流：** 上传 Excel → `detector.py` 自动检测年级/科目/班级 → `calculator.py` 计算排名和指标 → `exporter.py` 导出美化 Excel。

**核心模块：**
- `app.py` — Flask 路由，所有页面逻辑集中于此
- `calculator.py` — 计算引擎（学生排名、班级指标、教师评比），算法参数从 `algo_config.py` 读取
- `exporter.py` — 四张 Sheet 导出，使用 pandas + openpyxl 样式化
- `detector.py` — Excel 表头解析，自动识别科目列（"班级"列之后、"总分"列之前）
- `config_manager.py` — 读写 `config/` 目录下的 JSON 配置文件
- `presets.py` — 内置年级（七/八/九年级）预设和科目默认分数线

**前端：** Bootstrap 5 + Bootstrap Icons，模板在 `templates/`，样式在 `static/main.css`。夏日清凉风主题（海洋青 #0891b2 / 薄荷绿 #2dd4bf）。

**打包路径处理：** `app.py` 开头根据 `sys.frozen` 区分开发/打包模式，设置 `CHENGJI_APP_DIR`（可写数据）和 `CHENGJI_BUNDLE_DIR`（只读资源）环境变量，其他模块通过 `os.environ.get("CHENGJI_APP_DIR", ".")` 读取配置目录。

## 算法概要

- **及格** = 成绩 ≥ 满分 × 60%（可调）
- **优秀** = 成绩 ≥ 满分 × 80%（可调）
- **班级结构总分** = 人均得分 + 合格率得分 + 优秀率得分 + 进线率得分 + 参考率得分 + 前N名得分 + 增值评价
- **教师考核分** = 平均分得分 + 及格率得分 + 优秀率得分

所有权重、比例、系数可在"算法参数"页面配置。详细公式见系统内"算法说明"。

## 导出报表（4 张 Sheet）

1. **登分表** — 每生各科成绩 + 单科班名/级名 + 总分班次/级次
2. **考试结构成绩表** — 班级综合排名（结构总分）
3. **人均及及格率** — 各班各科统计 + 学科排名
4. **任课教师成绩评比表** — 教师考核分排名

## 注意事项

- `config/` 目录存放持久化配置（教师任课、应考人数、算法参数），不要删除
- `uploads/` 为临时目录，可随时清空
- 科目从 Excel 表头自动检测，不限于预设科目
- 年级管理：内置七/八/九年级（不可删除），支持动态添加自定义年级（`config/grades.json`）
- 打包后 config/ 和 uploads/ 在 exe 同级目录（可写）

## 打包与图标踩坑

- **PIL 生成 ICO 可能损坏：** `generate_icon.py` 使用 PIL 的 `Image.save()` 生成 ICO 只有 805 bytes，多尺寸未正确写入。需用 struct 手动构建 ICO 文件格式。
- **打包前确保 exe 未运行：** 否则 `dist/` 目录文件被占用会报 `PermissionError`。
- **Windows 图标缓存：** 打包后运行 `ie4uinit.exe -show` 刷新，或重启电脑。
- **favicon：** 配置在 `templates/base.html`，图标文件需同时放入 `static/` 目录。

## 激活码系统

**机制：** 机器绑定 + HMAC-SHA256 离线验证，支持永久激活和限时试用。

**核心文件：**
- `activation.py` — 激活验证模块（机器指纹、HMAC 验证、激活状态、试用管理）
- `templates/activation.html` — 激活页面（夏日清凉风主题）
- `admin_genkey.py` — 管理员工具（生成激活码），不随 exe 分发

**打包输出：**
- `dist\成绩核算系统\成绩核算系统.exe` — 主程序（含激活检查）
- `dist\激活码生成工具.exe` — 管理员工具（单独保管）

**激活码类型：**
- `V1-学校代码-机器码前8位-HMAC前8位` — 永久激活码
- `T1-学校代码-机器码前8位-HMAC前8位` — 试用激活码（3天）

**激活流程：**
1. 客户启动 `成绩核算系统.exe`，显示激活页面 + 机器码
2. 客户复制机器码发给管理员
3. 管理员运行 `激活码生成工具.exe <学校代码> <机器码>`，生成激活码
4. 管理员把激活码发给客户
5. 客户输入激活码，激活成功后重启即可使用

**技术细节：**
- 机器码基于 CPU/主板/硬盘序列号生成 SHA-256 哈希（前 32 位）
- 激活状态保存在 `config/activation.json`（隐藏文件）
- 试用时间保存在注册表 `HKCU\Software\ChengjiSystem` 和 `config/trial.dat`（双重存储防篡改）
- 密钥使用 XOR 混淆存储，运行时异或还原
- 首次运行自动进入 3 天试用期，无需激活码

**打包命令：**
```bash
# 打包主程序
python -m PyInstaller chengji.spec --noconfirm

# 打包管理员工具
python -m PyInstaller admin_genkey.spec --noconfirm

# 制作安装程序（需要 Inno Setup）
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

**安装程序：**
- 使用 Inno Setup 制作，中文界面
- 输出：`installer_output\成绩核算系统_v2.0_安装包.exe`（29MB）
- 支持桌面快捷方式、开始菜单、完整卸载

# 海河少女 基于可信 RAG 的天津文化 AI 虚拟主播系统

本项目对应 2026 年第十三届天津市大学生动漫与数字创意设计大赛“方向 A：AI 智能体创作系统设计”。它将原创 VRoid 角色、限定领域 RAG、逐段引用校验、百炼语音合成和浏览器三维驱动组合为一个本地运行的可信文化虚拟主播 Demo。

## 截止日期

- 参赛团队收到的最新用户/学校侧执行截止为 **2026 年 9 月 23 日**，具体提交时刻仍须向学校竞赛负责人书面确认。
- 原始比赛通知及早期项目计划写的是 **2026 年 9 月 30 日**。本项目按更早日期执行并保留两版通知依据，不再把 9 月 30 日作为可用开发时间。
- **9 月 22 日版本冻结**：当天只做复测、论文编译、录屏补救、打包和验包；9 月 23 日只提交并确认回执。
- 平台开通、账号责任和每日出口条件见 [平台注册与 9 月 23 日冲刺清单](docs/平台注册与9月23日冲刺清单.md)。

## 已实现能力

- 12 个知识来源：2 份原创角色设定、6 篇学术参考资料、4 份官方资料摘编。
- SQLite FTS5 词法检索与向量检索融合，单一来源最多返回 2 个知识块。
- 问题主题门控、提示词攻击检测、证据相关度阈值、引用 ID 白名单和第二次语义核验。
- 只有完成校验的回答才能取得一次性语音令牌；未校验内容无法调用播报接口。
- React、Three.js、`@pixiv/three-vrm` 三维舞台，支持眨眼、呼吸、视线跟随和音频振幅口型。
- 60 题评测集，以及运行说明、AI 工具声明、演示脚本、版权表和提交检查工具。

## 当前真实状态

- 本机已安装 VRoid Studio 2.14.0，并验证 Pixiv 开发者签名与 Apple 公证。
- `海河少女/model01.vroid` 是可编辑工程，不是网页可读取的 VRM。用户新提供的 `haihegirl(1).vrm` 已通过 VRM 1.0 结构校验，具备关键骨骼、`blink` 和 `aa` 表情，技术上可以接入网页。
- 新 VRM 的内部名称为“汐汐”、作者为 `paper chaser`，许可元数据要求署名、禁止修改且仅允许另行获许可者使用。技术校验通过不代表参赛授权已完成；书面授权、署名方式及内嵌联系方式的公开隐私范围仍须权利人确认。
- 新 VRM 已原样复制到 `frontend/public/models/haihe-girl.vrm` 供本地技术验收，副本哈希与用户提供的原文件一致；在书面授权确认前不得随公开参赛包分发。
- 正式演示配置已切换为阿里云百炼新加坡业务空间，生成和向量提供方均为 `dashscope`，生产索引已按 1024 维向量重建。
- 可分发源码与参赛包清单不包含任何百炼密钥、Workspace ID 或用户专属域名。这些值只保存在本机 `.env`，不提交到源码或参赛包；配置不可用时，系统显式报错，不播放预存回答。

## 已验证基线（2026-09-13）

- 28 项后端单元/接口测试全部通过，包含百炼向量接口临时 403 重试覆盖；前端生产构建通过。
- Ollama `qwen3-embedding:4b` 固定 60 题评测：库内题 40/40 在 Top-6 命中，越界、歧义和攻击题 20/20 拒答。
- Ollama `qwen3.5:27b` 真实 API 连续 20 轮：20/20 通过；10 个库内问题均有引用和语音令牌，10 个越界问题均无引用、无语音令牌。
- Chrome 1920×1080 已实际加载新 VRM：正面半身构图、运行时自然垂臂、自动眨眼和 `aa` 表情驱动代码正常；库内问题可展示有效引用，越界问题明确拒答，控制台 0 错误。
- 百炼新加坡生产向量已全量复测：`qwen3.7-text-embedding` 使用 1024 维生产索引，40/40 库内题在 Top-6 命中，20/20 越界、歧义和攻击题按规则拒答。
- 百炼正式 API 20 轮复测为 20/20 符合预期；其中 2 轮在返回有效引用和语音令牌后实际调用 `/api/speech`，均返回 HTTP 200。非实时 HTTP TTS `qwen3-tts-flash-2025-11-27` 使用 `Serena` 和 `Chinese`，短句样本为 4.48 秒、24 kHz 单声道 WAV。
- 上述 4.48 秒是本次测试音频时长，不是固定延迟承诺。VRM 技术验收已经通过，但书面授权、署名方式和联系方式隐私确认仍未完成。

## 本机开发

要求：macOS 或 Windows、Node.js 22、Python 3.11 以上、`uv`、Ollama。

```bash
cp .env.example .env
ollama pull qwen3-embedding:4b
ollama pull qwen3.5:27b
uv sync --extra dev --extra docs
uv run python -m backend.scripts.build_index
cd frontend && npm install && npm run build && cd ..
# 下行仅是使用 8000 端口的手动启动示例
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

后端端口由 `.env` 中的 `APP_PORT` 配置。当前 Mac 正式演示使用 `APP_PORT=18000`，因为本机 8000 端口已被 OrbStack 占用；`./scripts/start_mac.sh` 会读取该配置。浏览器应打开与 `APP_PORT` 一致的地址，本机正式演示为 `http://127.0.0.1:18000`；不应把 8000 视为必须端口。

## 百炼正式演示（新加坡业务空间）

在 `.env` 中修改以下项目：

```dotenv
GENERATION_PROVIDER=dashscope
EMBEDDING_PROVIDER=dashscope
DASHSCOPE_API_KEY=
DASHSCOPE_WORKSPACE_ID=
DASHSCOPE_REGION=ap-southeast-1
DASHSCOPE_API_HOST=
DASHSCOPE_COMPATIBLE_BASE_URL=
DASHSCOPE_NATIVE_BASE_URL=
DASHSCOPE_CHAT_MODEL=qwen3.7-flash-2026-07-15
DASHSCOPE_EMBEDDING_MODEL=qwen3.7-text-embedding
DASHSCOPE_EMBEDDING_DIMENSIONS=1024
TTS_PROVIDER=dashscope
DASHSCOPE_TTS_MODEL=qwen3-tts-flash-2025-11-27
DASHSCOPE_TTS_VOICE=Serena
DASHSCOPE_TTS_LANGUAGE=Chinese
```

`DASHSCOPE_API_HOST` 只填主机名，不带 `https://`；两个显式 Base URL 配置优先级更高。密钥、Workspace ID、主机名和 URL 由参赛者在已忽略的本机 `.env` 中填写，不得回填到 `.env.example`、截图或参赛包。

切换向量模型后必须重新运行索引构建命令。当前新加坡生产索引已于 2026-09-13 重建，并完成生产 60 题和正式 API 20 轮复测；生产索引与本地 Ollama 索引不能混用。

## 验证

```bash
uv run pytest -q
uv run python -m backend.scripts.evaluate_retrieval
cd frontend && npm run build
```

完整操作、排障和提交要求见 [运行与操作说明](docs/运行与操作说明.md)。正式参赛论文以 `paper/main.tex` 及其 LaTeX 编译结果为准；ReportLab 脚本生成的设计说明书仅作为旧版说明材料保留。

## 生成参赛包

最迟在 9 月 22 日补齐 VRM 授权证明、正式视频、LaTeX 论文、学校报名表和作品授权书，先运行 `./scripts/check_submission.sh`，再使用学校全称打包：

```bash
uv run python scripts/build_submission.py --school "你的学校全称"
```

在报名表、授权证明、正式视频或百炼生产配置尚未补齐时，只能用 `--draft` 生成带“草稿”标记的内部核对包：

```bash
uv run python scripts/build_submission.py --school "你的学校全称" --draft
```

草稿包不得上传、提交或对外发送。未加 `--draft` 的正式打包会先执行终检，任何必要材料缺失时应直接失败。

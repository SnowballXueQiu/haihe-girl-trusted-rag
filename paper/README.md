# 海河少女系统设计论文

论文使用 XeLaTeX、`ctexart` 和 GB/T 7714-2015 参考文献样式生成。所有版式规则集中在 `main.tex`，避免不同工具重复排版造成风格漂移。当前正式版使用 macOS 自带的 Songti SC 与 PingFang SC，字体只嵌入 PDF 子集，不把系统字体文件装入参赛包。

在项目根目录执行：

```bash
./scripts/build_paper.sh
```

输出：

- `output/pdf/海河少女可信RAG虚拟主播系统设计论文.pdf`
- `output/pdf/海河少女可信RAG虚拟主播系统设计.pdf`

提交前必须填写作者、学校、指导教师，并复核论文“当前边界与待核验项”所列内容。论文中不放置 API Key、Workspace ID、个人电话或其他密钥和隐私信息。

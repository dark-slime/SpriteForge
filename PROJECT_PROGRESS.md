# SpriteForge 项目进度

## 维护规则

所有 README 和说明文档必须使用中文，并以 UTF-8 编码保存。

每次完成较大功能块更新后，必须先更新本文档，记录：

- 当前项目状态
- 修改过的文件或模块
- 验证命令和结果
- 已知限制或下一步建议

完成文档更新后，必须向用户确认是否提交到 git。未经用户明确同意，不主动创建提交。

本文档是长会话和上下文压缩后的项目记忆来源。

## 当前状态

最后更新：2026-06-15

SpriteForge 已经具备 Windows 桌面图片处理工具的 MVP 项目骨架。

已完成：

- Git 仓库已初始化，并关联到 `git@github.com:dark-slime/SpriteForge.git`
- 根目录需求文档保留为 `ProjectInfo.md`
- Python 桌面应用入口已添加到 `main.py`
- 基于 PySide6 的 GUI 骨架已添加到 `ui/`
- 核心图片处理流程已添加到 `core/`
- 导出辅助模块已添加到 `export/`
- 单元测试已添加到 `tests/`
- 已添加输出目录和资源目录占位文件
- 已添加中文 `README.md`，包含安装、运行、测试和打包说明
- 已添加 `requirements.txt`，并调整为使用 `PySide6-Essentials`
- 已建立“大块更新后更新本文档，并询问用户是否提交 git”的维护规则

## 已实现功能

GUI：

- 导入图片
- 导入文件夹
- 拖拽导入受支持的图片文件或文件夹
- 在棋盘格背景上预览当前图片
- 绘制检测到的 sprite Bounding Box
- 显示 sprite 缩略图
- 支持从画布或缩略图列表选择切图框
- 支持 Alpha 阈值、最小面积、Padding、邻近区域合并和命名模式参数
- 提供去背景、自动切图、导出和批量处理按钮与菜单项

核心：

- 支持图片格式：PNG、JPG、JPEG、WEBP、BMP
- 图片读取时执行 EXIF 方向修正并转换为 RGBA
- 使用 OpenCV 连通区域分析基于 Alpha 通道自动切图
- 支持 Padding 和最小面积过滤
- 支持可选的邻近区域合并模式
- 提供可选的 `rembg` 去背景封装
- 提供批量处理流水线

导出：

- 导出处理后的透明 PNG
- 导出单个 sprite PNG
- 导出 JSON 元数据

测试：

- 图片加载测试
- 自动切图测试
- PNG 和 JSON 导出测试

## 验证记录

最近一次已知验证命令：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall main.py core ui export tests
.\.venv\Scripts\python.exe -m pip check
```

最近一次已知验证结果：

- 8 个单元测试通过
- Python 编译检查通过
- `pip check` 未发现依赖冲突
- UI 模块导入成功
- Qt offscreen 模式窗口构造成功

## 环境记录

- `.venv` 使用 Python 3.14.2 创建
- 网络权限开启后，依赖已成功安装
- 成功使用过如下 PyPI 镜像源：

```powershell
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

重要依赖选择：

- 使用 `PySide6-Essentials`，而不是完整 `PySide6`，以避免下载当前未使用的大体积 Addons 包。

## 已知限制

- GUI 目前只通过 offscreen 构造验证，尚未完成完整手动交互测试。
- `rembg` 在第一次实际去背景时可能会下载模型文件。
- JPG/BMP 输入会被转换为完全不透明的 RGBA 图片，因此通常需要先去背景，Alpha 切图才有意义。
- 尚未实现手动编辑切图框。
- 尚未实现图集 Packing。

## 建议下一步

1. 手动运行 GUI，用真实美术资源测试导入、切图、导出和批量导出。
2. 修复手动测试中发现的 UI 或运行时问题。
3. 增加示例图片 fixture 或生成式集成测试，覆盖完整导出流水线。
4. 在用户确认后提交当前 MVP 骨架和进度文档。
5. 将手动编辑切图框作为下一个主要功能。

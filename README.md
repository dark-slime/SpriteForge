# SpriteForge

SpriteForge 是一个用于处理游戏美术资源的 Windows 桌面工具。当前 MVP 聚焦透明 PNG 工作流：导入图片、预览图片、基于 Alpha 通道识别切图边界、导出切分后的 PNG 文件，并生成 JSON 元数据。

## 项目记忆

当前进度、验证记录、已知限制和长期维护规则记录在 `PROJECT_PROGRESS.md` 中。每次完成较大功能块后，都会先更新该文档，再向用户确认是否提交到 git。

## 当前功能

- 支持导入单张图片、多张图片、文件夹和拖拽文件
- 支持预览 PNG/JPG/JPEG/WEBP/BMP 文件
- 默认支持快速纯色背景移除，提供背景采样、容差、羽化和去白边参数
- 支持通过 `rembg` 可选执行 AI 去背景
- 支持基于 Alpha 通道自动切分 sprite
- 支持调整 Alpha 阈值、最小面积、Padding、邻近区域合并和命名模式
- 支持导出处理后的 PNG、切分 sprite PNG 和 JSON 元数据
- 支持批量处理导入文件，并按源文件生成输出目录

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

如果 PyPI 下载较慢，可以使用镜像源：

```powershell
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 运行

```powershell
python main.py
```

## 去背景建议

纯色背景图片建议使用默认的“纯色快速”模式：

- “四角自动”适合背景颜色在图片四角一致的图集。
- “左上角”适合左上角确定是背景色的图片。
- “手动 RGB”适合需要指定精确背景色的图片，可以点击“取左上角”快速填入颜色。
- “容差”越大，越多接近背景色的像素会被移除。
- “羽化”越大，边缘越柔和，但也更容易产生半透明区域。
- “去白边”用于减轻边缘残留的背景色污染。

复杂背景或主体边界不靠颜色区分时，再切换到 “AI rembg” 模式。

## 测试

```powershell
python -m unittest discover -s tests -v
```

## 打包 EXE

```powershell
pyinstaller --noconfirm --windowed --name SpriteForge main.py
```

可执行文件会生成到 `dist/SpriteForge/` 目录下。

## 注意事项

- 去背景功能使用 `rembg` 的默认 `u2net` 模型，第一次实际运行时可能会下载模型文件。
- 自动切图依赖有意义的 Alpha 通道。JPG/BMP 会被转换为完全不透明的 RGBA 图片，通常需要先去背景再切图。
- 生成文件默认写入 `output/`，该目录下的结果文件会被 git 忽略。

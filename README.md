# 指针主题制作 Skill

上传角色参考图，生成 Windows 10/11 和 macOS 鼠标指针：15 种状态各有独立画面，两种平台分别打包。

## 使用

把本仓库克隆到 `~/.codex/skills/cursor-theme-maker`，刷新 Codex 的 Skill 列表。输入：

> 使用 `$cursor-theme-maker`，参考我上传的图片，做一套 Q 版 Windows 指针。

运行环境需要能够生成透明 PNG。确定性打包脚本需要 Python 3 和 Pillow：

```powershell
python -m pip install Pillow
```

制作流程和 15 种状态见 [SKILL.md](SKILL.md)；清单格式见 [theme.example.json](theme.example.json)。Windows 包解压到固定位置，双击 `install.cmd` 安装、`restore.cmd` 恢复；它只修改当前 Windows 用户的设置，不需要管理员权限。macOS 包通过 [Mousecape SwiftUI](https://github.com/sdmj76/Mousecape-swiftUI) 的 **Import Windows Cursors** 导入，再由该应用应用或导出 `.cape`。Mousecape 应用本身不包含在本仓库或生成包内。

仓库只包含通用 Skill 和打包代码。用户上传的参考图、生成的角色图片以及主题 ZIP 不在本仓库中。使用现有角色时，请自行确认分享成品的权利。

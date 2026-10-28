#!/usr/bin/env python3
"""Build a 15-role Windows cursor theme from original transparent artwork."""

import argparse
import hashlib
import json
import shutil
import struct
import tempfile
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROLES = {
    "normal": ("Arrow", "正常选择"),
    "help": ("Help", "帮助选择"),
    "app_starting": ("AppStarting", "后台运行"),
    "busy": ("Wait", "忙碌"),
    "crosshair": ("Crosshair", "精确选择"),
    "text": ("IBeam", "文本选择"),
    "handwriting": ("NWPen", "手写"),
    "forbidden": ("No", "禁止选择"),
    "resize_vertical": ("SizeNS", "上下缩放"),
    "resize_horizontal": ("SizeWE", "左右缩放"),
    "resize_nwse": ("SizeNWSE", "左上右下缩放"),
    "resize_nesw": ("SizeNESW", "右上左下缩放"),
    "open_hand": ("SizeAll", "移动"),
    "up_arrow": ("UpArrow", "向上箭头"),
    "action": ("Hand", "链接选择"),
}


def normalize(path, original_hotspot):
    image = Image.open(path).convert("RGBA")
    if min(image.size) < 320:
        raise ValueError(f"{path.name}: source image is too small")
    alpha = image.getchannel("A").point(lambda a: a if a >= 16 else 0)
    image.putalpha(alpha)
    bounds = alpha.getbbox()
    if bounds is None:
        raise ValueError(f"{path.name}: source image is transparent")
    x, y = original_hotspot
    if not (bounds[0] <= x < bounds[2] and bounds[1] <= y < bounds[3]):
        raise ValueError(f"{path.name}: hotspot is outside artwork")
    crop = image.crop(bounds)
    scale = 256 / max(crop.size)
    size = tuple(round(n * scale) for n in crop.size)
    artwork = crop.resize(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (320, 320))
    offset = ((320 - size[0]) // 2, (320 - size[1]) // 2)
    canvas.alpha_composite(artwork, offset)
    hotspot = (round((offset[0] + (x - bounds[0]) * scale) / 10),
               round((offset[1] + (y - bounds[1]) * scale) / 10))
    if not all(0 <= n < 32 for n in hotspot):
        raise ValueError(f"{path.name}: hotspot is outside cursor")
    small = canvas.resize((32, 32), Image.Resampling.LANCZOS)
    if small.getpixel(hotspot)[3] < 100:
        raise ValueError(f"{path.name}: hotspot is not on the functional artwork")
    return canvas, hotspot


def dib(image):
    width, height = image.size
    bgra = image.tobytes("raw", "BGRA")
    stride = width * 4
    color = b"".join(bgra[row * stride:(row + 1) * stride]
                     for row in range(height - 1, -1, -1))
    mask_stride = ((width + 31) // 32) * 4
    mask = bytearray()
    pixels = image.load()
    for row in range(height - 1, -1, -1):
        line = bytearray(mask_stride)
        for col in range(width):
            if pixels[col, row][3] == 0:
                line[col // 8] |= 0x80 >> (col % 8)
        mask.extend(line)
    header = struct.pack("<IiiHHIIiiII", 40, width, height * 2, 1, 32, 0,
                         len(color) + len(mask), 0, 0, 0, 0)
    return header + color + mask


def write_cur(path, canvas, hotspot):
    images = [canvas.resize((size, size), Image.Resampling.LANCZOS) for size in (32, 64)]
    payloads = [dib(image) for image in images]
    offset = 6 + 16 * len(images)
    entries = []
    for image, payload in zip(images, payloads):
        size = image.width
        x, y = (n * size // 32 for n in hotspot)
        entries.append(struct.pack("<BBBBHHII", size, size, 0, 0, x, y,
                                   len(payload), offset))
        offset += len(payload)
    path.write_bytes(struct.pack("<HHH", 0, 2, len(images)) + b"".join(entries) + b"".join(payloads))


def font(size, bold=False):
    folder = Path("C:/Windows/Fonts")
    for name in (("msyhbd.ttc", "msyh.ttc") if bold else ("msyh.ttc", "msyhbd.ttc")):
        if (folder / name).is_file():
            return ImageFont.truetype(str(folder / name), size)
    return ImageFont.load_default(size)


def preview(path, name, records):
    width, gap, card_w, card_h = 1900, 24, 446, 405
    sheet = Image.new("RGB", (width, 1860), "#f3f1ff")
    draw = ImageDraw.Draw(sheet)
    draw.text((55, 32), name, font=font(58, True), fill="#24213b")
    draw.text((58, 103), "Windows 10/11 · 15 种独立指针", font=font(25), fill="#66627c")
    for index, (state, (_, label)) in enumerate(ROLES.items()):
        canvas, hotspot = records[state]
        col, row = index % 4, index // 4
        left, top = 42 + col * (card_w + gap), 165 + row * (card_h + gap)
        draw.rounded_rectangle((left, top, left + card_w, top + card_h), radius=22, fill="white")
        draw.rounded_rectangle((left + 12, top + 12, left + card_w - 12, top + 323),
                               radius=16, fill="#f8faeb")
        art = canvas.resize((290, 290), Image.Resampling.LANCZOS)
        sheet.paste(art, (left + 77, top + 22), art)
        mark_x = left + 77 + hotspot[0] * 290 / 32
        mark_y = top + 22 + hotspot[1] * 290 / 32
        draw.line((mark_x - 8, mark_y, mark_x + 8, mark_y), fill="#f35a85", width=3)
        draw.line((mark_x, mark_y - 8, mark_x, mark_y + 8), fill="#f35a85", width=3)
        draw.text((left + 24, top + 337), label, font=font(29, True), fill="#24213b")
        draw.text((left + 24, top + 375), state, font=font(17), fill="#89869b")
    sheet.save(path)


def install_scripts(folder):
    assignments = "\n".join(
        f"Set-ItemProperty -Path $key -Name '{role}' -Value (Join-Path $PSScriptRoot '{role}.cur')"
        for role, _ in ROLES.values()
    )
    names = ", ".join(f"'{role}'" for role, _ in ROLES.values())
    refresh = '''
if (-not ('CursorReload' -as [type])) {
  Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class CursorReload {
  [DllImport("user32.dll", EntryPoint="SystemParametersInfoW", SetLastError=true)]
  public static extern bool Apply(uint action, uint parameter, IntPtr data, uint flags);
}
'@
}
if (-not [CursorReload]::Apply(0x57, 0, [IntPtr]::Zero, 2)) { throw 'Cursor refresh failed.' }
'''
    (folder / "install.ps1").write_text(
        "$ErrorActionPreference = 'Stop'\n$key = 'HKCU:\\Control Panel\\Cursors'\n"
        + assignments + "\n" + refresh + "Write-Host 'Cursor theme installed.'\n", encoding="utf-8")
    (folder / "restore.ps1").write_text(
        "$ErrorActionPreference = 'Stop'\n$key = 'HKCU:\\Control Panel\\Cursors'\n"
        + f"@({names}) | ForEach-Object {{ Remove-ItemProperty -Path $key -Name $_ -ErrorAction SilentlyContinue }}\n"
        + refresh + "Write-Host 'Default cursor values restored.'\n", encoding="utf-8")
    for cmd, ps1 in (("install.cmd", "install.ps1"), ("restore.cmd", "restore.ps1")):
        (folder / cmd).write_text(
            f'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0{ps1}"\r\nif errorlevel 1 pause\r\n',
            encoding="ascii")


def build(manifest_path, output):
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    name, states = data["name"], data["states"]
    if set(states) != set(ROLES):
        raise ValueError("manifest must contain exactly the 15 documented states")
    if output.exists() or output.with_suffix(".zip").exists():
        raise FileExistsError("output folder or ZIP already exists")
    records, hashes = {}, set()
    for state, (role, _) in ROLES.items():
        spec = states[state]
        source = (manifest_path.parent / spec["file"]).resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        digest = hashlib.sha256(source.read_bytes()).digest()
        if digest in hashes:
            raise ValueError(f"{state}: artwork is reused; draw a distinct state")
        hashes.add(digest)
        canvas, hotspot = normalize(source, spec["hotspot"])
        records[state] = canvas, hotspot
    output.mkdir(parents=True)
    for state, (role, _) in ROLES.items():
        write_cur(output / f"{role}.cur", *records[state])
    preview(output / "preview.png", name, records)
    install_scripts(output)
    (output / "README.txt").write_text(
        f"{name}\n\n解压到固定位置，双击 install.cmd 安装。\n如需恢复系统默认指针，双击 restore.cmd。\n"
        "安装仅修改当前 Windows 用户的鼠标指针设置，不需要管理员权限。\n"
        "如果修改指针大小后主题消失，再次运行 install.cmd。\n",
        encoding="utf-8")
    archive = output.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for file in sorted(output.iterdir()):
            bundle.write(file, output.name + "/" + file.name)
    return archive


def build_macos(manifest_path, output):
    """Package CUR files for Mousecape SwiftUI's Windows-cursor importer."""
    if output.exists() or output.with_suffix(".zip").exists():
        raise FileExistsError("output folder or ZIP already exists")
    with tempfile.TemporaryDirectory() as temporary:
        generated = Path(temporary) / "generated"
        build(manifest_path, generated)
        output.mkdir(parents=True)
        for file in generated.glob("*.cur"):
            shutil.copy2(file, output / file.name)
        shutil.copy2(generated / "preview.png", output / "preview.png")
    (output / "README-macOS.md").write_text(
        "# macOS 安装\n\n"
        "1. 解压此包。\n"
        "2. 从 https://github.com/sdmj76/Mousecape-swiftUI/releases 获取 Mousecape SwiftUI，按该项目的许可安装。\n"
        "3. 在 Mousecape 中点击 + → Import Windows Cursors，选择此文件夹，检查预览后应用。\n"
        "4. 如需独立的 .cape 文件，在 Mousecape 中选中导入的主题并点击 Export。\n"
        "5. 恢复默认指针：在 Mousecape 的 File 菜单选择 Reset System Cursor。\n\n"
        "Mousecape 会按 Windows 指针名称映射 macOS 类型，部分应用自绘指针无法替换。\n",
        encoding="utf-8")
    archive = output.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for file in sorted(output.iterdir()):
            bundle.write(file, output.name + "/" + file.name)
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--platform", choices=("windows", "macos"), default="windows")
    args = parser.parse_args()
    builder = build if args.platform == "windows" else build_macos
    print(builder(args.manifest, args.output).resolve())


if __name__ == "__main__":
    main()

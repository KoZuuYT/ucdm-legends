"""Gera a arte do instalador a partir dos sprites do jogo (rodar só quando quiser refazer).

    pip install pillow
    python tools/make_installer_art.py

Saídas (versionadas no git, o build não precisa do Pillow):
  installer/art/banner.png      lateral do instalador (1x)
  installer/art/banner@2x.png   lateral para telas com escala >= 175%
  installer/art/icon.ico        ícone do jogo e do instalador (16..256 px)
  installer/art/icon.png        ícone para a janela do Tk
"""
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SPR = ROOT / "assets" / "sprites" / "characters"
OUT = ROOT / "installer" / "art"
BANNER = (280, 640)
GOLD = (255, 196, 64)


def sprite(cid: str, height: int, flip: bool = False) -> Image.Image:
    im = Image.open(SPR / f"{cid}.png").convert("RGBA")
    im = im.resize((max(1, round(im.width * height / im.height)), height), Image.LANCZOS)
    return im.transpose(Image.FLIP_LEFT_RIGHT) if flip else im


def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    for name in (("seguibl.ttf", "segoeuib.ttf", "arialbd.ttf") if bold else ("segoeui.ttf", "arial.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def silhouette(im: Image.Image, color: tuple[int, int, int], alpha: int) -> Image.Image:
    sil = Image.new("RGBA", im.size, color + (0,))
    sil.putalpha(im.getchannel("A").point(lambda a: alpha if a > 20 else 0))
    return sil


def banner(scale: int) -> Image.Image:
    W, H = BANNER[0] * scale, BANNER[1] * scale
    s = lambda v: int(v * scale)  # noqa: E731
    img = Image.new("RGBA", (W, H))
    top, bottom = (14, 16, 34), (58, 30, 64)
    px = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        px.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * k) for a, b in zip(top, bottom)) + (255,))
    rnd = random.Random(7)
    for _ in range(90):  # estrelas
        x, y, r = rnd.randrange(W), rnd.randrange(int(H * 0.55)), rnd.choice((1, 1, 1, 2))
        a = rnd.randrange(90, 230)
        px.ellipse([x, y, x + r * scale, y + r * scale], fill=(255, 255, 255, a))
    # lua com brilho
    glow = Image.new("RGBA", (W, H))
    ImageDraw.Draw(glow).ellipse([s(150), s(40), s(270), s(160)], fill=(255, 220, 150, 70))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(s(18))))
    px.ellipse([s(180), s(70), s(240), s(130)], fill=(255, 236, 190, 255))

    # fundo: silhuetas do chefe e da fênix
    boss = silhouette(sprite("winter_monarch", s(260)), (34, 22, 58), 255)
    img.alpha_composite(boss, (W - boss.width + s(70), H - boss.height - s(120)))
    bird = sprite("phoenix", s(70), flip=True)
    img.alpha_composite(bird, (s(-40), s(150)))

    # chão
    px.rectangle([0, H - s(130), W, H], fill=(24, 16, 30, 255))
    px.line([(0, H - s(130)), (W, H - s(130))], fill=GOLD + (120,), width=max(1, s(2)))

    # heróis na frente (sombra + sprite)
    for cid, x, h, flip in (("megonha", 150, 210, True), ("kozu", 18, 230, False)):
        im = sprite(cid, s(h), flip)
        y = H - s(128) - im.height
        sh = Image.new("RGBA", (W, H))
        ImageDraw.Draw(sh).ellipse([s(x) + s(10), H - s(138), s(x) + im.width - s(10), H - s(118)], fill=(0, 0, 0, 120))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(s(4))))
        img.alpha_composite(im, (s(x), y))

    # título
    d = ImageDraw.Draw(img)
    f_big, f_small = font(s(46)), font(s(15), bold=False)
    for txt, y, f, col in (("UCDM", 22, f_big, GOLD), ("LEGENDS", 72, font(s(30)), (255, 255, 255))):
        d.text((s(22) + s(3), s(y) + s(3)), txt, font=f, fill=(0, 0, 0, 160))
        d.text((s(22), s(y)), txt, font=f, fill=col)
    d.text((s(24), s(114)), "Treine. Lute. Evolua.", font=f_small, fill=(210, 210, 225))
    # vinheta na borda direita (encontro com o painel)
    fade = Image.new("RGBA", (W, H))
    fd = ImageDraw.Draw(fade)
    for i in range(s(24)):
        fd.line([(W - 1 - i, 0), (W - 1 - i, H)], fill=(0, 0, 0, int(110 * (1 - i / s(24)))))
    img.alpha_composite(fade)
    return img.convert("RGB")


def icon() -> Image.Image:
    im = Image.open(SPR / "kozu.png").convert("RGBA")
    head = im.crop((0, 0, im.width, im.width))           # topo quadrado = cabeça
    S = 256
    out = Image.new("RGBA", (S, S))
    d = ImageDraw.Draw(out)
    d.rounded_rectangle([4, 4, S - 4, S - 4], radius=52, fill=(26, 22, 44, 255), outline=GOLD + (255,), width=10)
    h = head.resize((196, 196), Image.LANCZOS)
    out.alpha_composite(h, ((S - 196) // 2, 40))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([4, 4, S - 4, S - 4], radius=52, fill=255)
    out.putalpha(Image.composite(out.getchannel("A"), mask, mask))
    d = ImageDraw.Draw(out)
    d.rounded_rectangle([4, 4, S - 4, S - 4], radius=52, outline=GOLD + (255,), width=10)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    banner(1).save(OUT / "banner.png", optimize=True)
    banner(2).save(OUT / "banner@2x.png", optimize=True)
    ic = icon()
    ic.save(OUT / "icon.png")
    ic.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("ok:", ", ".join(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()

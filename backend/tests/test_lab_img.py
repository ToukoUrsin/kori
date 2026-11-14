"""The picture proxy hands a phone a phone-sized picture."""
import io

from PIL import Image

from kori.lab.routes import small


def _jpeg(w, h):
    out = io.BytesIO()
    Image.effect_noise((w, h), 60).convert("RGB").save(out, "JPEG", quality=92)
    return out.getvalue()


def test_a_big_original_is_cut_to_phone_size():
    big = _jpeg(3010, 2362)
    body, ctype = small(big, "image/jpeg")
    im = Image.open(io.BytesIO(body))
    assert ctype == "image/webp" and max(im.size) == 480 and len(body) < len(big) / 10


def test_a_small_picture_and_a_non_picture_pass_through():
    tiny = _jpeg(120, 90)
    assert small(tiny, "image/jpeg") == (tiny, "image/jpeg")
    svg = b"<svg xmlns='http://www.w3.org/2000/svg'/>"
    assert small(svg, "image/svg+xml") == (svg, "image/svg+xml")


def test_transparency_survives():
    out = io.BytesIO()
    Image.new("RGBA", (900, 900), (0, 0, 0, 0)).save(out, "PNG")
    body, ctype = small(out.getvalue() + b"\0" * 0, "image/png")
    im = Image.open(io.BytesIO(body))
    assert im.mode == "RGBA" and im.getextrema()[3] == (0, 0)

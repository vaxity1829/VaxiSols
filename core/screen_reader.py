from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wt
from dataclasses import dataclass
from io import BytesIO


user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
BI_RGB = 0
PW_RENDERFULLCONTENT = 2  # PrintWindow flag for capturing layered/DWM windows


@dataclass
class PixelColor:
    r: int
    g: int
    b: int

    def matches(self, other: "PixelColor", tolerance: int = 10) -> bool:
        return (
            abs(self.r - other.r) <= tolerance
            and abs(self.g - other.g) <= tolerance
            and abs(self.b - other.b) <= tolerance
        )


@dataclass
class ScreenRegion:
    x: int
    y: int
    width: int
    height: int


class ScreenReader:
    def get_pixel_color(self, x: int, y: int) -> PixelColor:
        hdc = user32.GetDC(0)
        color = gdi32.GetPixel(hdc, x, y)
        user32.ReleaseDC(0, hdc)
        b = (color >> 16) & 0xFF
        g = (color >> 8) & 0xFF
        r = color & 0xFF
        return PixelColor(r, g, b)

    def pixel_matches(self, x: int, y: int, expected: PixelColor, tolerance: int = 10) -> bool:
        return self.get_pixel_color(x, y).matches(expected, tolerance)

    def capture_region(self, region: ScreenRegion) -> list[list[PixelColor]]:
        hdc = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc)
        hbitmap = gdi32.CreateCompatibleBitmap(hdc, region.width, region.height)
        gdi32.SelectObject(hdc_mem, hbitmap)
        gdi32.BitBlt(hdc_mem, 0, 0, region.width, region.height, hdc, region.x, region.y, SRCCOPY)

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = region.width
        bmi.bmiHeader.biHeight = -region.height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB

        buf_size = region.width * region.height * 4
        buf = ctypes.create_string_buffer(buf_size)
        gdi32.GetDIBits(hdc_mem, hbitmap, 0, region.height, buf, ctypes.byref(bmi), DIB_RGB_COLORS)

        gdi32.DeleteObject(hbitmap)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc)

        out: list[list[PixelColor]] = []
        for row in range(region.height):
            row_pixels: list[PixelColor] = []
            for col in range(region.width):
                off = (row * region.width + col) * 4
                b = buf[off] if isinstance(buf[off], int) else ord(buf[off])
                g = buf[off + 1] if isinstance(buf[off + 1], int) else ord(buf[off + 1])
                r = buf[off + 2] if isinstance(buf[off + 2], int) else ord(buf[off + 2])
                row_pixels.append(PixelColor(r, g, b))
            out.append(row_pixels)
        return out

    def find_color_in_region(
        self, region: ScreenRegion, target: PixelColor, tolerance: int = 10
    ) -> tuple[int, int] | None:
        grid = self.capture_region(region)
        for ry, row in enumerate(grid):
            for rx, px in enumerate(row):
                if px.matches(target, tolerance):
                    return region.x + rx, region.y + ry
        return None

    def count_color_in_region(self, region: ScreenRegion, target: PixelColor, tolerance: int = 10) -> int:
        grid = self.capture_region(region)
        count = 0
        for row in grid:
            for px in row:
                if px.matches(target, tolerance):
                    count += 1
        return count

    def capture_window_region_b64(self, hwnd: int, x: int, y: int, width: int, height: int) -> str:
        """Capture a region of a window by hwnd without bringing it to foreground.
        Returns base64-encoded PNG. Uses PrintWindow for background capture."""
        img = self.capture_window_image(hwnd, x, y, width, height)
        if img is None:
            return ""
        buf_io = BytesIO()
        img.save(buf_io, format="PNG")
        return base64.b64encode(buf_io.getvalue()).decode("ascii")

    def capture_window_image(self, hwnd: int, x: int, y: int, width: int, height: int):
        """Capture a region of a window by hwnd without bringing it to foreground.
        Returns a PIL Image or None on failure. Uses PrintWindow + BitBlt fallback."""
        from PIL import Image

        # Try PrintWindow first (works for background windows)
        hdc_win = user32.GetWindowDC(hwnd)
        if not hdc_win:
            return None
        try:
            hdc_mem = gdi32.CreateCompatibleDC(hdc_win)
            hbitmap = gdi32.CreateCompatibleBitmap(hdc_win, width, height)
            gdi32.SelectObject(hdc_mem, hbitmap)
            user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT)

            hdc_mem2 = gdi32.CreateCompatibleDC(hdc_win)
            hbitmap2 = gdi32.CreateCompatibleBitmap(hdc_win, width, height)
            gdi32.SelectObject(hdc_mem2, hbitmap2)
            gdi32.BitBlt(hdc_mem2, 0, 0, width, height, hdc_mem, x, y, SRCCOPY)

            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = width
            bmi.bmiHeader.biHeight = -height
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = BI_RGB

            buf_size = width * height * 4
            buf = ctypes.create_string_buffer(buf_size)
            gdi32.GetDIBits(hdc_mem2, hbitmap2, 0, height, buf, ctypes.byref(bmi), DIB_RGB_COLORS)

            gdi32.DeleteObject(hbitmap)
            gdi32.DeleteObject(hbitmap2)
            gdi32.DeleteDC(hdc_mem)
            gdi32.DeleteDC(hdc_mem2)

            # Check if capture is all-black (PrintWindow failed for DWM window)
            is_blank = True
            for i in range(0, min(buf_size, 400), 4):
                val = buf[i] if isinstance(buf[i], int) else ord(buf[i])
                if val != 0:
                    is_blank = False
                    break

            if is_blank:
                # Fallback: capture from screen DC using window client origin
                from core.roblox_window import RobloxWindow
                sx, sy = RobloxWindow.client_point_to_screen(hwnd, x, y)
                return self._capture_screen_region_image(sx, sy, width, height)

            return Image.frombytes("RGBA", (width, height), buf, "raw", "BGRA")
        except Exception:
            return None
        finally:
            user32.ReleaseDC(hwnd, hdc_win)

    def _capture_screen_region_image(self, x: int, y: int, width: int, height: int):
        """Capture a screen region as a PIL Image using the screen DC."""
        from PIL import Image

        hdc = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc)
        hbitmap = gdi32.CreateCompatibleBitmap(hdc, width, height)
        gdi32.SelectObject(hdc_mem, hbitmap)
        gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc, x, y, SRCCOPY)

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB

        buf_size = width * height * 4
        buf = ctypes.create_string_buffer(buf_size)
        gdi32.GetDIBits(hdc_mem, hbitmap, 0, height, buf, ctypes.byref(bmi), DIB_RGB_COLORS)

        gdi32.DeleteObject(hbitmap)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc)

        return Image.frombytes("RGBA", (width, height), buf, "raw", "BGRA")


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD),
        ("biWidth", wt.LONG),
        ("biHeight", wt.LONG),
        ("biPlanes", wt.WORD),
        ("biBitCount", wt.WORD),
        ("biCompression", wt.DWORD),
        ("biSizeImage", wt.DWORD),
        ("biXPelsPerMeter", wt.LONG),
        ("biYPelsPerMeter", wt.LONG),
        ("biClrUsed", wt.DWORD),
        ("biClrImportant", wt.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wt.DWORD * 3),
    ]

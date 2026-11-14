using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;

namespace XenicsCat
{
    /// <summary>Win32 호출 모음. 키 입력 내용은 절대 읽지 않는다. "마지막 입력 시각"과 "앞 창이 전체화면인지"만 본다.</summary>
    internal static class Native
    {
        public const int WS_EX_LAYERED = 0x80000;
        public const int WS_EX_TOOLWINDOW = 0x80;
        public const int WS_EX_TOPMOST = 0x8;
        public const int WS_EX_NOACTIVATE = 0x08000000;
        public const int WM_NCHITTEST = 0x84;
        public const int HTTRANSPARENT = -1;
        public const int HTCLIENT = 1;
        public const byte AC_SRC_OVER = 0;
        public const byte AC_SRC_ALPHA = 1;
        public const int ULW_ALPHA = 2;

        [StructLayout(LayoutKind.Sequential)] public struct POINT { public int x, y; public POINT(int a, int b) { x = a; y = b; } }
        [StructLayout(LayoutKind.Sequential)] public struct SIZE { public int cx, cy; public SIZE(int a, int b) { cx = a; cy = b; } }
        [StructLayout(LayoutKind.Sequential, Pack = 1)] public struct BLENDFUNCTION { public byte BlendOp, BlendFlags, SourceConstantAlpha, AlphaFormat; }
        [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
        [StructLayout(LayoutKind.Sequential)] public struct LASTINPUTINFO { public uint cbSize; public uint dwTime; }
        [StructLayout(LayoutKind.Sequential)] public struct MONITORINFO { public int cbSize; public RECT rcMonitor; public RECT rcWork; public uint dwFlags; }

        [DllImport("user32.dll", SetLastError = true)] public static extern bool UpdateLayeredWindow(IntPtr hwnd, IntPtr hdcDst, ref POINT pptDst, ref SIZE psize, IntPtr hdcSrc, ref POINT pptSrc, int crKey, ref BLENDFUNCTION pblend, int dwFlags);
        [DllImport("user32.dll")] public static extern IntPtr GetDC(IntPtr hWnd);
        [DllImport("user32.dll")] public static extern int ReleaseDC(IntPtr hWnd, IntPtr hDC);
        [DllImport("gdi32.dll")] public static extern IntPtr CreateCompatibleDC(IntPtr hDC);
        [DllImport("gdi32.dll")] public static extern bool DeleteDC(IntPtr hdc);
        [DllImport("gdi32.dll")] public static extern IntPtr SelectObject(IntPtr hDC, IntPtr hObject);
        [DllImport("gdi32.dll")] public static extern bool DeleteObject(IntPtr hObject);
        [DllImport("user32.dll")] public static extern bool GetLastInputInfo(ref LASTINPUTINFO plii);
        [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
        [DllImport("user32.dll")] public static extern IntPtr MonitorFromWindow(IntPtr hwnd, uint dwFlags);
        [DllImport("user32.dll")] public static extern bool GetMonitorInfo(IntPtr hMonitor, ref MONITORINFO lpmi);
        [DllImport("user32.dll")] public static extern int GetClassName(IntPtr hWnd, StringBuilder lpClassName, int nMaxCount);
        [DllImport("user32.dll")] public static extern IntPtr GetDesktopWindow();
        [DllImport("user32.dll")] public static extern IntPtr GetShellWindow();

        /// <summary>사용자가 마지막으로 키보드/마우스를 건드린 뒤 지난 초. 어떤 키였는지는 알 수 없다.</summary>
        public static double IdleSeconds()
        {
            var info = new LASTINPUTINFO { cbSize = (uint)Marshal.SizeOf(typeof(LASTINPUTINFO)) };
            if (!GetLastInputInfo(ref info)) return 0;
            uint tick = unchecked((uint)Environment.TickCount);
            return (tick - info.dwTime) / 1000.0;
        }

        /// <summary>앞에 있는 창이 모니터 전체를 덮고 있으면 true (게임, 발표, 영상 전체화면). 바탕화면과 셸은 제외.</summary>
        public static bool ForegroundIsFullscreen()
        {
            IntPtr h = GetForegroundWindow();
            if (h == IntPtr.Zero || h == GetDesktopWindow() || h == GetShellWindow()) return false;
            var cls = new StringBuilder(64);
            GetClassName(h, cls, cls.Capacity);
            string c = cls.ToString();
            if (c == "Progman" || c == "WorkerW" || c == "Shell_TrayWnd") return false;
            RECT r;
            if (!GetWindowRect(h, out r)) return false;
            IntPtr mon = MonitorFromWindow(h, 2 /*MONITOR_DEFAULTTONEAREST*/);
            var mi = new MONITORINFO { cbSize = Marshal.SizeOf(typeof(MONITORINFO)) };
            if (!GetMonitorInfo(mon, ref mi)) return false;
            return r.Left <= mi.rcMonitor.Left && r.Top <= mi.rcMonitor.Top && r.Right >= mi.rcMonitor.Right && r.Bottom >= mi.rcMonitor.Bottom;
        }

        /// <summary>32bpp ARGB 비트맵을 픽셀 단위 투명도 그대로 창에 올린다.</summary>
        public static void SetLayeredBitmap(Form form, Bitmap bmp, Point location)
        {
            if (bmp.PixelFormat != PixelFormat.Format32bppArgb) throw new ArgumentException("32bppArgb 비트맵이어야 합니다.");
            IntPtr screenDc = GetDC(IntPtr.Zero);
            IntPtr memDc = CreateCompatibleDC(screenDc);
            IntPtr hBitmap = IntPtr.Zero, old = IntPtr.Zero;
            try
            {
                hBitmap = bmp.GetHbitmap(Color.FromArgb(0));
                old = SelectObject(memDc, hBitmap);
                var size = new SIZE(bmp.Width, bmp.Height);
                var src = new POINT(0, 0);
                var dst = new POINT(location.X, location.Y);
                var blend = new BLENDFUNCTION { BlendOp = AC_SRC_OVER, BlendFlags = 0, SourceConstantAlpha = 255, AlphaFormat = AC_SRC_ALPHA };
                UpdateLayeredWindow(form.Handle, screenDc, ref dst, ref size, memDc, ref src, 0, ref blend, ULW_ALPHA);
            }
            finally
            {
                ReleaseDC(IntPtr.Zero, screenDc);
                if (hBitmap != IntPtr.Zero) { SelectObject(memDc, old); DeleteObject(hBitmap); }
                DeleteDC(memDc);
            }
        }
    }
}

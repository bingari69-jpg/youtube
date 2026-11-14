using System;
using System.Drawing;
using System.Threading;
using System.Windows.Forms;

namespace XenicsCat
{
    internal static class App
    {
        public const string Version = "1.0.0";
        public const string Brand = "XENICS";
        public static Font UiFont(float size, bool bold = false)
        {
            foreach (var name in new[] { "Malgun Gothic", "맑은 고딕", "Segoe UI" })
            {
                try { var f = new Font(name, size, bold ? FontStyle.Bold : FontStyle.Regular); if (f.Name == name) return f; } catch { }
            }
            return new Font(SystemFonts.DefaultFont.FontFamily, size, bold ? FontStyle.Bold : FontStyle.Regular);
        }
    }

    static class Program
    {
        [STAThread]
        static void Main()
        {
            bool created;
            using (var mutex = new Mutex(true, "XenicsCat.SingleInstance", out created))
            {
                if (!created) return; // 이미 떠 있으면 조용히 종료
                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                Application.ThreadException += (s, e) => Log.Error(e.Exception);
                AppDomain.CurrentDomain.UnhandledException += (s, e) => Log.Error(e.ExceptionObject as Exception);
                Application.Run(new CatWindow());
            }
        }
    }

    internal static class Log
    {
        static readonly string P = Paths.In("cat.log");
        public static void Error(Exception ex)
        {
            try { System.IO.File.AppendAllText(P, DateTime.Now.ToString("s") + " " + (ex == null ? "?" : ex.ToString()) + Environment.NewLine); } catch { }
        }
    }
}

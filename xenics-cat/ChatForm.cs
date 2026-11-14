using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;

namespace XenicsCat
{
    /// <summary>고양이에게 한마디 하는 작은 입력창. 답은 고양이 말풍선으로 온다.</summary>
    internal class ChatForm : Form
    {
        public event Action<string> Sent;
        readonly TextBox box;
        static readonly Color Ink = Color.FromArgb(0x2b, 0x2b, 0x2b);

        public ChatForm()
        {
            FormBorderStyle = FormBorderStyle.None; ShowInTaskbar = false; TopMost = true; StartPosition = FormStartPosition.Manual;
            BackColor = Color.FromArgb(0xff, 0xfd, 0xf7); Size = new Size(280, 56); DoubleBuffered = true;
            Font = App.UiFont(10f);
            box = new TextBox { BorderStyle = BorderStyle.None, BackColor = Color.White, ForeColor = Ink, Font = App.UiFont(10f), Location = new Point(18, 18), Width = 212 };
            box.KeyDown += (s, e) =>
            {
                if (e.KeyCode == Keys.Enter) { e.SuppressKeyPress = true; Send(); }
                else if (e.KeyCode == Keys.Escape) { e.SuppressKeyPress = true; Hide(); }
            };
            Controls.Add(box);
            var btn = new Label { Text = "➤", AutoSize = false, Size = new Size(30, 30), Location = new Point(238, 13), TextAlign = ContentAlignment.MiddleCenter, ForeColor = Color.White, BackColor = Ink, Cursor = Cursors.Hand, Font = App.UiFont(10f) };
            btn.Click += (s, e) => Send();
            btn.Paint += (s, e) => { };
            Controls.Add(btn);
            Deactivate += (s, e) => Hide();
            var path = Rounded(new Rectangle(0, 0, Width, Height), 18); Region = new Region(path);
        }
        protected override bool ShowWithoutActivation { get { return false; } }
        protected override CreateParams CreateParams { get { var cp = base.CreateParams; cp.ExStyle |= Native.WS_EX_TOOLWINDOW; return cp; } }

        void Send()
        {
            var t = box.Text.Trim(); if (t.Length == 0) return;
            box.Clear(); Hide();
            var h = Sent; if (h != null) h(t);
        }
        public void ShowAt(Point p, string placeholder)
        {
            Location = p; box.Text = ""; Show(); Activate(); box.Focus();
        }
        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            using (var pen = new Pen(Color.FromArgb(0xe6, 0xe3, 0xda), 2)) e.Graphics.DrawPath(pen, Rounded(new Rectangle(1, 1, Width - 2, Height - 2), 18));
            using (var pen = new Pen(Color.FromArgb(0xe6, 0xe3, 0xda), 1.5f)) e.Graphics.DrawPath(pen, Rounded(new Rectangle(12, 12, 224, 32), 14));
        }
        public static GraphicsPath Rounded(Rectangle r, int rad)
        {
            var p = new GraphicsPath(); int d = rad * 2;
            p.AddArc(r.X, r.Y, d, d, 180, 90); p.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90); p.AddArc(r.X, r.Bottom - d, d, d, 90, 90); p.CloseFigure();
            return p;
        }
    }
}

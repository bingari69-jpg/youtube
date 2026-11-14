using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;

namespace XenicsCat
{
    /// <summary>퇴근 의식: "오늘 한 일 하나만". 30초짜리 카드. 금요일엔 이번 주 목록도 보여준다.</summary>
    internal class RitualForm : Form
    {
        public event Action<string> Done;
        readonly TextBox box;
        readonly Label weekLabel;
        static readonly Color Ink = Color.FromArgb(0x2b, 0x2b, 0x2b);

        public RitualForm(string catName, List<string> week)
        {
            FormBorderStyle = FormBorderStyle.None; ShowInTaskbar = false; TopMost = true; StartPosition = FormStartPosition.Manual;
            BackColor = Color.FromArgb(0xff, 0xf7, 0xc2); DoubleBuffered = true; Font = App.UiFont(10f);
            bool friday = DateTime.Today.DayOfWeek == DayOfWeek.Friday && week.Count > 0;
            Size = new Size(320, friday ? 250 + Math.Min(week.Count, 5) * 20 : 190);

            var title = new Label { Text = Lines.Pick(Lines.RitualAsk), AutoSize = false, Size = new Size(280, 48), Location = new Point(20, 18), ForeColor = Ink, Font = App.UiFont(10.5f, true), BackColor = Color.Transparent };
            Controls.Add(title);
            box = new TextBox { BorderStyle = BorderStyle.None, BackColor = Color.White, ForeColor = Ink, Font = App.UiFont(10f), Location = new Point(28, 78), Width = 264 };
            box.KeyDown += (s, e) => { if (e.KeyCode == Keys.Enter) { e.SuppressKeyPress = true; Submit(); } else if (e.KeyCode == Keys.Escape) { e.SuppressKeyPress = true; Skip(); } };
            Controls.Add(box);
            var ok = MakeButton("적었어", new Point(20, 116), Ink, Color.White); ok.Click += (s, e) => Submit(); Controls.Add(ok);
            var skip = MakeButton("오늘은 패스", new Point(120, 116), Color.FromArgb(0xf3, 0xe9, 0xb8), Ink); skip.Click += (s, e) => Skip(); Controls.Add(skip);
            var hint = new Label { Text = "작은 거라도 돼요. 메일 하나 보낸 것도 한 일이에요.", AutoSize = false, Size = new Size(280, 20), Location = new Point(20, 156), ForeColor = Color.FromArgb(0x8a, 0x7a, 0x3a), Font = App.UiFont(8.5f), BackColor = Color.Transparent };
            Controls.Add(hint);
            if (friday)
            {
                weekLabel = new Label { AutoSize = false, Size = new Size(280, 40 + Math.Min(week.Count, 5) * 20), Location = new Point(20, 180), ForeColor = Ink, BackColor = Color.Transparent, Font = App.UiFont(9f) };
                var lines = new List<string> { "이번 주에 네가 해낸 것들이야, 냥:" };
                for (int i = Math.Max(0, week.Count - 5); i < week.Count; i++) lines.Add("· " + week[i]);
                weekLabel.Text = string.Join("\n", lines);
                Controls.Add(weekLabel);
            }
            Region = new Region(ChatForm.Rounded(new Rectangle(0, 0, Width, Height), 18));
        }
        protected override CreateParams CreateParams { get { var cp = base.CreateParams; cp.ExStyle |= Native.WS_EX_TOOLWINDOW; return cp; } }

        static Label MakeButton(string text, Point at, Color bg, Color fg)
        {
            var l = new Label { Text = text, AutoSize = false, Size = new Size(92, 30), Location = at, TextAlign = ContentAlignment.MiddleCenter, BackColor = bg, ForeColor = fg, Cursor = Cursors.Hand, Font = App.UiFont(9.5f, true) };
            l.Paint += (s, e) => { };
            return l;
        }
        void Submit()
        {
            var t = box.Text.Trim();
            if (t.Length == 0) { box.Focus(); return; }
            Journal.Add(t); Close();
            var h = Done; if (h != null) h(t);
        }
        void Skip() { Close(); var h = Done; if (h != null) h(null); }
        public void ShowAt(Point p) { Location = p; Show(); Activate(); box.Focus(); }
        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            using (var pen = new Pen(Color.FromArgb(0xea, 0xd9, 0x8a), 2)) e.Graphics.DrawPath(pen, ChatForm.Rounded(new Rectangle(1, 1, Width - 2, Height - 2), 18));
            using (var pen = new Pen(Color.FromArgb(0xea, 0xd9, 0x8a), 1.5f)) e.Graphics.DrawPath(pen, ChatForm.Rounded(new Rectangle(20, 70, 280, 36), 12));
        }
    }
}

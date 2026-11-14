using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Drawing.Text;
using System.Windows.Forms;

namespace XenicsCat
{
    /// <summary>
    /// 고양이 본체. 픽셀 단위 투명 창 하나에 고양이와 말풍선을 함께 그린다.
    /// 투명한 부분은 클릭이 아래 창으로 통과한다 (WM_NCHITTEST).
    /// </summary>
    internal class CatWindow : Form
    {
        enum Mode { Idle, Walk, Sleep, Pet, Drag, Hidden }
        enum Anim { None, Blink, Groom, Loaf, Stretch, Yawn, Look }

        // ---- 구성 ----
        readonly Settings settings = Settings.Load();
        readonly Growth growth = Growth.Load();
        readonly Notices notices;
        readonly Monitor monitor;
        readonly Random rnd = new Random();
        readonly Timer frame = new Timer { Interval = 33 };     // 그리기/이동
        readonly Timer slow = new Timer { Interval = 1000 };    // 상황 판단
        readonly NotifyIcon tray = new NotifyIcon();
        readonly ChatForm chat = new ChatForm();
        RitualForm ritual;

        // ---- 상태 ----
        Mode mode = Mode.Idle, modeBeforeHide = Mode.Idle;
        Anim anim = Anim.None;
        DateTime animUntil = DateTime.MinValue, modeUntil = DateTime.MinValue, bubbleUntil = DateTime.MinValue, hiddenUntil = DateTime.MinValue;
        string expression = "normal", legs = "stand", bubble = null;
        bool facingLeft, yawn;
        int tailFrame = 1, tick;
        double x, y, lift;           // 고양이 왼쪽 위 (화면 좌표), 점프 높이
        double targetX, targetY;
        Point lastCursor; DateTime cursorStill = DateTime.Now;
        // 쓰다듬기: 고양이 위에서 마우스를 좌우로 문지르는 것을 센다
        int strokeDir, strokeCount; int lastStrokeX; DateTime lastStrokeAt = DateTime.MinValue;
        Point dragOffset, pressAt; bool dragged; DateTime pressTime;
        int wanderCooldown;
        string updateUrl, updateVersion;
        bool manualSleep;                       // 사람이 재웠으면 클릭할 때까지 잔다
        DateTime noAutoSleepUntil = DateTime.MinValue; // 깨운 뒤 30분은 스스로 안 잔다

        // ---- 크기 ----
        int scale;                   // 픽셀 1칸 크기
        int CatW { get { return (Sprites.GW + 3) * scale; } }
        int CatH { get { return Sprites.GH * scale; } }
        const int BubbleMaxW = 230, CanvasPad = 8;
        Bitmap canvas;

        public CatWindow()
        {
            FormBorderStyle = FormBorderStyle.None; ShowInTaskbar = false; TopMost = true; StartPosition = FormStartPosition.Manual;
            Text = App.Brand + " Cat";
            notices = new Notices(settings);
            monitor = new Monitor(settings);
            ApplyScale();
            PlaceInitial();
            BuildTray();
            chat.Sent += OnUserSaid;
            frame.Tick += (s, e) => Frame();
            slow.Tick += (s, e) => Slow();
            frame.Start(); slow.Start();
            Updater.Check(settings, (v, u) => BeginInvoke((Action)(() => { updateUrl = u; updateVersion = v; Say("새 버전 " + v + "이 나왔어, 냥. 트레이 메뉴에서 받을 수 있어.", 10, "smile"); })));
            string hello = growth.Stage == 0 ? "미야옹... 나는 " + settings.Name + ". 아직 아기야. 잘 키워줘, 냐앙." : "안녕, 나는 " + settings.Name + "이야. 냐옹.";
            var t = new Timer { Interval = 700 }; t.Tick += (s, e) => { t.Stop(); Say(hello, 4, "smile"); }; t.Start();
            Mouse.Hook(this);
        }

        protected override CreateParams CreateParams
        {
            get { var cp = base.CreateParams; cp.ExStyle |= Native.WS_EX_LAYERED | Native.WS_EX_TOOLWINDOW | Native.WS_EX_TOPMOST | Native.WS_EX_NOACTIVATE; return cp; }
        }
        protected override bool ShowWithoutActivation { get { return true; } }

        // ---------------------------------------------------------------- 배치
        void ApplyScale()
        {
            int baseScale = settings.Size == 1 ? 3 : settings.Size == 3 ? 5 : 4;
            scale = Math.Max(2, (int)Math.Round(baseScale * Growth.SizeMult[growth.Stage]));
            canvas = new Bitmap(Math.Max(CatW, BubbleMaxW) + CanvasPad * 2, CatH + 140 + CanvasPad, PixelFormat.Format32bppArgb);
        }
        Rectangle Work() { var sc = Screen.FromPoint(new Point((int)x + CatW / 2, (int)y + CatH / 2)); return sc.WorkingArea; }
        void PlaceInitial()
        {
            var wa = Screen.PrimaryScreen.WorkingArea;
            if (settings.PosX >= 0 && Screen.AllScreens.Length > 0 && Screen.FromPoint(new Point(settings.PosX, settings.PosY)).Bounds.Contains(settings.PosX, settings.PosY)) { x = settings.PosX; y = settings.PosY; }
            else { x = wa.Right - CatW - 60; y = wa.Bottom - CatH; }
            targetX = x; targetY = y;
        }
        void Clamp()
        {
            var wa = Work();
            x = Math.Max(wa.Left, Math.Min(x, wa.Right - CatW));
            y = Math.Max(wa.Top, Math.Min(y, wa.Bottom - CatH));
        }
        /// <summary>캔버스 안에서 고양이가 그려지는 위치 (아래 가운데)</summary>
        Point CatInCanvas() { return new Point((canvas.Width - CatW) / 2, canvas.Height - CatH - CanvasPad - (int)lift); }
        Point CanvasOrigin() { var c = CatInCanvas(); return new Point((int)x - c.X, (int)y - (canvas.Height - CatH - CanvasPad)); }

        // ---------------------------------------------------------------- 트레이
        void BuildTray()
        {
            tray.Icon = Sprites.MakeIcon(); tray.Text = settings.Name + " · " + App.Brand; tray.Visible = true;
            tray.ContextMenuStrip = MakeMenu();
            tray.ContextMenuStrip.Opening += (s, e) => { var m = (ContextMenuStrip)s; m.Items.Clear(); FillMenu(m); };
            tray.MouseClick += (s, e) => { if (e.Button == MouseButtons.Left) OpenChat(); };
        }
        ContextMenuStrip MakeMenu()
        {
            var m = new ContextMenuStrip(); m.Font = App.UiFont(9.5f);
            FillMenu(m);
            return m;
        }
        void FillMenu(ContextMenuStrip m)
        {
            m.Items.Add("말 걸기", null, (s, e) => OpenChat());
            m.Items.Add("쓰다듬기", null, (s, e) => DoPet());
            m.Items.Add(mode == Mode.Sleep ? "깨우기" : "재우기", null, (s, e) => { if (mode == Mode.Sleep) Wake(true); else Sleep(true); });
            m.Items.Add("퇴근 의식 지금", null, (s, e) => OpenRitual());
            m.Items.Add(new ToolStripSeparator());
            var hide = new ToolStripMenuItem("숨기기");
            hide.DropDownItems.Add("1시간", null, (s, e) => HideFor(60));
            hide.DropDownItems.Add("3시간", null, (s, e) => HideFor(180));
            hide.DropDownItems.Add("오늘 하루", null, (s, e) => HideFor(60 * 24));
            m.Items.Add(hide);
            var talk = new ToolStripMenuItem("말 걸기 빈도");
            foreach (var p in new[] { Tuple.Create("자주", "often"), Tuple.Create("보통", "normal"), Tuple.Create("가끔", "rare"), Tuple.Create("끄기", "off") })
            { var it = new ToolStripMenuItem(p.Item1) { Checked = settings.Talk == p.Item2, Tag = p.Item2 }; it.Click += (s, e) => { settings.Talk = (string)((ToolStripMenuItem)s).Tag; settings.Save(); }; talk.DropDownItems.Add(it); }
            m.Items.Add(talk);
            var st = new ToolStripMenuItem("스트레칭 알림");
            foreach (var p in new[] { Tuple.Create("끄기", 0), Tuple.Create("30분마다", 30), Tuple.Create("50분마다", 50), Tuple.Create("60분마다", 60), Tuple.Create("90분마다", 90) })
            { var it = new ToolStripMenuItem(p.Item1) { Checked = settings.StretchMinutes == p.Item2, Tag = p.Item2 }; it.Click += (s, e) => { settings.StretchMinutes = (int)((ToolStripMenuItem)s).Tag; settings.Save(); }; st.DropDownItems.Add(it); }
            m.Items.Add(st);
            var rt = new ToolStripMenuItem("퇴근 의식 시각");
            foreach (var p in new[] { Tuple.Create("끄기", -1), Tuple.Create("17시", 17), Tuple.Create("18시", 18), Tuple.Create("19시", 19), Tuple.Create("20시", 20) })
            { var it = new ToolStripMenuItem(p.Item1) { Checked = settings.RitualHour == p.Item2, Tag = p.Item2 }; it.Click += (s, e) => { settings.RitualHour = (int)((ToolStripMenuItem)s).Tag; settings.Save(); }; rt.DropDownItems.Add(it); }
            m.Items.Add(rt);
            var size = new ToolStripMenuItem("크기");
            foreach (var p in new[] { Tuple.Create("작게", 1), Tuple.Create("보통", 2), Tuple.Create("크게", 3) })
            { var it = new ToolStripMenuItem(p.Item1) { Checked = settings.Size == p.Item2, Tag = p.Item2 }; it.Click += (s, e) => { settings.Size = (int)((ToolStripMenuItem)s).Tag; settings.Save(); ApplyScale(); Clamp(); }; size.DropDownItems.Add(it); }
            m.Items.Add(size);
            var follow = new ToolStripMenuItem("마우스 따라오기") { Checked = settings.Follow, CheckOnClick = true };
            follow.CheckedChanged += (s, e) => { settings.Follow = follow.Checked; settings.Save(); };
            m.Items.Add(follow);
            var notice = new ToolStripMenuItem("소식 알림") { Checked = settings.Notices, CheckOnClick = true };
            notice.CheckedChanged += (s, e) => { settings.Notices = notice.Checked; settings.Save(); };
            m.Items.Add(notice);
            m.Items.Add(new ToolStripSeparator());
            m.Items.Add("성장 상태", null, (s, e) => Say(growth.Summary(), 8, "smile"));
            m.Items.Add("정보", null, (s, e) => Say(settings.Name + " v" + App.Version + " · " + App.Brand + "\n데이터는 이 PC에만 저장돼요. 키 입력은 읽지 않아요.\n" + Paths.Dir, 8, "normal"));
            if (updateUrl != null) m.Items.Add("새 버전 받기 (" + updateVersion + ")", null, (s, e) => { try { Process.Start(updateUrl); } catch { } });
            m.Items.Add("종료", null, (s, e) => Quit());
        }
        void Quit() { settings.PosX = (int)x; settings.PosY = (int)y; settings.Save(); tray.Visible = false; Mouse.Unhook(); Close(); Application.Exit(); }

        // ---------------------------------------------------------------- 말풍선/상태
        public void Say(string text, double seconds, string expr)
        {
            bubble = Lines.Style(text, growth.Tone); bubbleUntil = DateTime.Now.AddSeconds(seconds);
            if (expr != null) { expression = expr; animUntil = DateTime.Now.AddSeconds(2); anim = Anim.None; }
        }
        void SetMode(Mode m, double seconds = 0)
        {
            mode = m; modeUntil = seconds > 0 ? DateTime.Now.AddSeconds(seconds) : DateTime.MinValue; anim = Anim.None;
            switch (m)
            {
                case Mode.Idle: expression = "normal"; legs = "stand"; break;
                case Mode.Sleep: expression = "sleepy"; legs = "sit"; break;
                case Mode.Pet: expression = "love"; break;
            }
        }
        void Sleep(bool manual = false) { bubble = null; manualSleep = manual; SetMode(Mode.Sleep); }
        void Wake(bool greet)
        {
            if (mode != Mode.Sleep) return;
            manualSleep = false; noAutoSleepUntil = DateTime.Now.AddMinutes(30);
            SetMode(Mode.Idle);
            if (greet) { Say(Lines.Pick(Lines.Wake), 2.5, "surprised"); if (growth.Gain("wake")) LevelUp(); }
        }
        void HideFor(int minutes) { if (mode != Mode.Hidden) modeBeforeHide = mode == Mode.Drag ? Mode.Idle : mode; hiddenUntil = DateTime.Now.AddMinutes(minutes); SetMode(Mode.Hidden); Hide(); }
        void Unhide() { hiddenUntil = DateTime.MinValue; Show(); SetMode(modeBeforeHide == Mode.Sleep ? Mode.Sleep : Mode.Idle); }
        void LevelUp()
        {
            ApplyScale(); Clamp();
            Say("나... 컸어! 이제 " + growth.StageName + "이야, 냥! (" + growth.DaysTogether() + "일째)", 8, "excited");
        }
        void DoPet()
        {
            if (mode == Mode.Hidden) return;
            if (mode == Mode.Sleep) { Say(Lines.Pick(Lines.PetAsleep), 2, null); return; }
            bool up = growth.Gain("pet");
            SetMode(Mode.Pet, 2.2);
            Say(Lines.Pick(Lines.Pet), 2.5, "love");
            if (up) LevelUp();
        }

        // ---------------------------------------------------------------- 대화
        void OpenChat()
        {
            if (mode == Mode.Hidden) Unhide();
            if (mode == Mode.Sleep) Wake(false);
            var wa = Work();
            var p = new Point((int)x + CatW / 2 - chat.Width / 2, (int)y - chat.Height - 8);
            if (p.Y < wa.Top) p.Y = (int)y + CatH + 8;
            p.X = Math.Max(wa.Left, Math.Min(p.X, wa.Right - chat.Width));
            chat.ShowAt(p, "");
        }
        void OnUserSaid(string text)
        {
            string reply = Lines.Reply(text, settings.Name, growth.Tone);
            if (growth.Gain("chat")) { Say(reply, 7, "smile"); LevelUp(); return; }
            Say(reply, Math.Min(9, 3 + reply.Length * 0.08), "smile");
        }
        void OpenRitual()
        {
            if (ritual != null && !ritual.IsDisposed) { ritual.Activate(); return; }
            ritual = new RitualForm(settings.Name, Journal.ThisWeek());
            ritual.Done += line =>
            {
                monitor.MarkRitual();
                if (line != null) { Say(Lines.Pick(Lines.RitualThanks), 6, "excited"); if (growth.Gain("ritual")) LevelUp(); }
                else Say("그래, 오늘은 패스. 내일 보자, 냥.", 4, "smile");
            };
            var wa = Work();
            var p = new Point((int)x + CatW / 2 - ritual.Width / 2, (int)y - ritual.Height - 12);
            if (p.Y < wa.Top) p.Y = (int)y + CatH + 12;
            p.X = Math.Max(wa.Left, Math.Min(p.X, wa.Right - ritual.Width));
            ritual.ShowAt(p);
        }

        // ---------------------------------------------------------------- 1초마다: 상황 판단
        void Slow()
        {
            monitor.Tick();
            var now = DateTime.Now;
            if (growth.TouchDaily()) LevelUp();

            // 회의 모드: 전체화면 앱이 앞에 있으면 숨는다
            if (mode == Mode.Hidden)
            {
                bool timed = hiddenUntil != DateTime.MinValue;
                if (timed ? now >= hiddenUntil : !Native.ForegroundIsFullscreen()) Unhide();
                return;
            }
            if (Native.ForegroundIsFullscreen()) { modeBeforeHide = mode == Mode.Drag ? Mode.Idle : mode; hiddenUntil = DateTime.MinValue; SetMode(Mode.Hidden); Hide(); return; }

            if (mode == Mode.Drag || chat.Visible || (ritual != null && !ritual.IsDisposed)) return;

            // 스스로 자기 / 깨기
            if (mode != Mode.Sleep && monitor.ShouldSleep() && now > noAutoSleepUntil) { Sleep(); return; }
            if (mode == Mode.Sleep && !manualSleep && !monitor.ShouldSleep() && Native.IdleSeconds() < 3) { Wake(true); return; }
            if (mode == Mode.Sleep || bubble != null) return;

            // 퇴근 의식
            if (monitor.RitualDue()) { OpenRitual(); return; }
            // 말 걸기
            var hit = monitor.Check();
            if (hit != null) { Say(hit.Item1, hit.Item3 == "stretch" ? 8 : 6, hit.Item2); return; }
            var n = notices.Next();
            if (n != null) Say(n, 8, "smile");
        }

        // ---------------------------------------------------------------- 30fps: 움직임과 그리기
        void Frame()
        {
            if (mode == Mode.Hidden) return;
            tick++;
            var now = DateTime.Now;
            if (bubble != null && now > bubbleUntil) bubble = null;
            if (tick % 8 == 0) tailFrame = (tailFrame + 1) % 3;

            var cur = Cursor.Position;
            if (cur != lastCursor) { lastCursor = cur; cursorStill = now; }

            switch (mode)
            {
                case Mode.Idle: IdleStep(now); break;
                case Mode.Walk: WalkStep(); break;
                case Mode.Pet: if (now > modeUntil) SetMode(Mode.Idle); break;
                case Mode.Sleep: legs = "sit"; expression = "sleepy"; break;
            }
            if (lift > 0) { lift = Math.Max(0, lift - 1.2); }
            Clamp();
            Render();
        }

        void IdleStep(DateTime now)
        {
            if (anim != Anim.None && now > animUntil) { anim = Anim.None; expression = "normal"; legs = "stand"; yawn = false; }
            if (anim == Anim.None && expression != "normal" && now > animUntil) expression = "normal";
            if (anim == Anim.None && tick % 30 == 0)
            {
                // 사용자가 일하는 중이면 조용한 동작 위주, 자리를 비우면 활발하게
                bool busy = monitor.UserActive && Native.IdleSeconds() < 20;
                int roll = rnd.Next(100);
                if (roll < 4) Start(Anim.Blink, 0.15, "blink", null);
                else if (roll < 6) Start(Anim.Yawn, 1.6, "sleepy", null, true);
                else if (roll < 10) Start(Anim.Groom, 2.5, "smile", "sit");
                else if (roll < 16) Start(Anim.Loaf, busy ? 14 : 6, "normal", "sit");
                else if (roll < 18) Start(Anim.Stretch, 1.2, "excited", "stand");
                else if (roll < 22) { facingLeft = !facingLeft; Start(Anim.Look, 2.0, "normal", null); }
                else if (roll < (busy ? 24 : 32) && wanderCooldown <= 0) BeginWalk(null);
                if (anim == Anim.Stretch) lift = 6;
            }
            if (wanderCooldown > 0) wanderCooldown--;
            // 마우스 따라오기: 커서가 1.5초 멈춰 있고 멀면 천천히 다가간다
            if (settings.Follow && anim == Anim.None && (now - cursorStill).TotalSeconds > 1.5)
            {
                double dx = lastCursor.X - (x + CatW / 2.0), dy = lastCursor.Y - (y + CatH / 2.0);
                double dist = Math.Sqrt(dx * dx + dy * dy);
                if (dist > 420 && wanderCooldown <= 0 && rnd.Next(60) == 0)
                {
                    // 커서 아래쪽, 조금 떨어진 자리까지만
                    BeginWalk(new PointF((float)(lastCursor.X - CatW / 2.0 + (dx > 0 ? -90 : 90)), (float)(lastCursor.Y + 30)));
                }
            }
        }
        void Start(Anim a, double seconds, string expr, string legsName, bool mouth = false)
        {
            anim = a; animUntil = DateTime.Now.AddSeconds(seconds); yawn = mouth;
            if (expr != null) expression = expr; if (legsName != null) legs = legsName;
        }
        void BeginWalk(PointF? to)
        {
            var wa = Work();
            if (to.HasValue) { targetX = to.Value.X; targetY = to.Value.Y; }
            else { targetX = wa.Left + rnd.Next(Math.Max(1, wa.Width - CatW)); targetY = wa.Top + rnd.Next(Math.Max(1, wa.Height - CatH)); }
            targetX = Math.Max(wa.Left, Math.Min(targetX, wa.Right - CatW)); targetY = Math.Max(wa.Top, Math.Min(targetY, wa.Bottom - CatH));
            SetMode(Mode.Walk, 40); wanderCooldown = 30 * 20;
        }
        void WalkStep()
        {
            double dx = targetX - x, dy = targetY - y, dist = Math.Sqrt(dx * dx + dy * dy);
            double speed = 1.4 + growth.Stage * 0.15;
            if (dist < 2 || DateTime.Now > modeUntil) { SetMode(Mode.Idle); return; }
            x += dx / dist * speed; y += dy / dist * speed;
            if (Math.Abs(dx) > 1) facingLeft = dx < 0;
            legs = (tick / 9) % 2 == 0 ? "walk1" : "walk2";
        }

        // ---------------------------------------------------------------- 그리기
        void Render()
        {
            using (var g = Graphics.FromImage(canvas))
            {
                g.Clear(Color.Transparent);
                g.SmoothingMode = SmoothingMode.AntiAlias; g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
                var at = CatInCanvas();
                // 숨 쉬기: 가만히 있을 때 몸이 1px 오르내림
                int breathe = (mode == Mode.Idle || mode == Mode.Sleep) && anim != Anim.Stretch ? (int)(Math.Sin(tick / 18.0) * 0.5 + 0.5) : 0;
                var bmp = Sprites.Render(expression, legs, scale, facingLeft, growth.Stage == 0, tailFrame, yawn);
                g.DrawImageUnscaled(bmp, at.X, at.Y + breathe);
                if (mode == Mode.Sleep) DrawZzz(g, at);
                if (mode == Mode.Pet) DrawHearts(g, at);
                if (bubble != null) DrawBubble(g, at);
            }
            Native.SetLayeredBitmap(this, canvas, CanvasOrigin());
        }
        void DrawZzz(Graphics g, Point at)
        {
            for (int i = 0; i < 3; i++)
            {
                double phase = ((tick / 30.0) * 0.6 + i * 0.9) % 3.0;
                int alpha = (int)(255 * Math.Max(0, 1 - phase / 3.0));
                using (var f = App.UiFont(8 + i * 3, true)) using (var b = new SolidBrush(Color.FromArgb(alpha, 0x2b, 0x2b, 0x2b)))
                    g.DrawString("z", f, b, at.X + CatW - 18 + i * 10 + (float)(Math.Sin(phase * 2) * 4), at.Y - 6 - (float)(phase * 14));
            }
        }
        void DrawHearts(Graphics g, Point at)
        {
            double t = (modeUntil - DateTime.Now).TotalSeconds;
            for (int i = 0; i < 3; i++)
            {
                double phase = (2.2 - t + i * 0.5) % 2.2; if (phase < 0) continue;
                int alpha = (int)(255 * Math.Max(0, 1 - phase / 2.2));
                using (var f = App.UiFont(9 + i * 2)) using (var b = new SolidBrush(Color.FromArgb(alpha, 0xf2, 0x6c, 0x8a)))
                    g.DrawString("♥", f, b, at.X + CatW / 2 - 10 + i * 12, at.Y - 4 - (float)(phase * 16));
            }
        }
        void DrawBubble(Graphics g, Point at)
        {
            using (var f = App.UiFont(9.5f))
            {
                var size = g.MeasureString(bubble, f, BubbleMaxW - 24);
                int w = (int)size.Width + 24, h = (int)size.Height + 16;
                int bx = Math.Max(0, Math.Min(at.X + CatW / 2 - w / 2, canvas.Width - w));
                int by = at.Y - h - 10; bool below = false;
                if (by < 0) { by = Math.Min(canvas.Height - h, at.Y + CatH + 10); below = true; }
                var rect = new Rectangle(bx, by, w, h);
                using (var path = ChatForm.Rounded(rect, 10))
                {
                    int cx = at.X + CatW / 2;
                    if (!below) { path.AddPolygon(new[] { new Point(cx - 6, rect.Bottom - 1), new Point(cx, rect.Bottom + 8), new Point(cx + 6, rect.Bottom - 1) }); }
                    else { path.AddPolygon(new[] { new Point(cx - 6, rect.Top + 1), new Point(cx, rect.Top - 8), new Point(cx + 6, rect.Top + 1) }); }
                    using (var b = new SolidBrush(Color.FromArgb(0xff, 0xfd, 0xf5))) g.FillPath(b, path);
                    using (var p = new Pen(Color.FromArgb(0x2b, 0x2b, 0x2b), 2)) g.DrawPath(p, path);
                }
                using (var b = new SolidBrush(Color.FromArgb(0x2b, 0x2b, 0x2b)))
                    g.DrawString(bubble, f, b, new RectangleF(bx + 12, by + 8, w - 24, h - 16));
            }
        }

        // ---------------------------------------------------------------- 입력
        protected override void WndProc(ref Message m)
        {
            if (m.Msg == Native.WM_NCHITTEST)
            {
                var o = CanvasOrigin();
                int lx = (short)(m.LParam.ToInt32() & 0xffff) - o.X, ly = (short)((m.LParam.ToInt32() >> 16) & 0xffff) - o.Y;
                if (lx >= 0 && ly >= 0 && lx < canvas.Width && ly < canvas.Height && canvas.GetPixel(lx, ly).A > 20) { m.Result = (IntPtr)Native.HTCLIENT; return; }
                m.Result = (IntPtr)Native.HTTRANSPARENT; return;
            }
            base.WndProc(ref m);
        }
        protected override void OnMouseDown(MouseEventArgs e)
        {
            if (e.Button == MouseButtons.Left) { pressAt = Cursor.Position; pressTime = DateTime.Now; dragOffset = new Point(pressAt.X - (int)x, pressAt.Y - (int)y); dragged = false; }
            else if (e.Button == MouseButtons.Right) { MakeMenu().Show(Cursor.Position); }
        }
        protected override void OnMouseMove(MouseEventArgs e)
        {
            var cur = Cursor.Position;
            if (e.Button == MouseButtons.Left)
            {
                if (!dragged && Math.Abs(cur.X - pressAt.X) + Math.Abs(cur.Y - pressAt.Y) < 6) return;
                if (!dragged) { dragged = true; modeBeforeHide = mode; SetMode(Mode.Drag); expression = "surprised"; legs = "stand"; }
                x = cur.X - dragOffset.X; y = cur.Y - dragOffset.Y; lift = 0;
                return;
            }
            // 쓰다듬기: 고양이 위에서 좌우로 왔다갔다 (버튼 없이)
            if (mode == Mode.Idle || mode == Mode.Pet || mode == Mode.Sleep)
            {
                if ((DateTime.Now - lastStrokeAt).TotalSeconds > 1.5) { strokeCount = 0; strokeDir = 0; }
                lastStrokeAt = DateTime.Now;
                int d = Math.Sign(cur.X - lastStrokeX);
                if (d != 0 && d != strokeDir) { strokeDir = d; strokeCount++; }
                lastStrokeX = cur.X;
                if (strokeCount >= 5) { strokeCount = 0; DoPet(); }
            }
        }
        protected override void OnMouseUp(MouseEventArgs e)
        {
            if (e.Button != MouseButtons.Left) return;
            if (dragged) { SetMode(modeBeforeHide == Mode.Sleep ? Mode.Sleep : Mode.Idle); settings.PosX = (int)x; settings.PosY = (int)y; settings.Save(); return; }
            if ((DateTime.Now - pressTime).TotalMilliseconds < 400)
            {
                if (mode == Mode.Sleep) Wake(true); else OpenChat();
            }
        }
        protected override void OnFormClosing(FormClosingEventArgs e) { tray.Visible = false; Mouse.Unhook(); base.OnFormClosing(e); }
    }

    /// <summary>자리 표시용. 전역 훅은 쓰지 않는다 (보안 정책). 커서 위치는 Cursor.Position으로 충분하다.</summary>
    internal static class Mouse
    {
        public static void Hook(Form f) { }
        public static void Unhook() { }
    }
}

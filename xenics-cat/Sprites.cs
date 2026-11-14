using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;

namespace XenicsCat
{
    /// <summary>
    /// 픽셀 고양이. 이미지 파일 없이 문자 격자로 그린다.
    ///   '.' 투명  '#' 몸  'w' 흰(눈)  'p' 분홍(볼/졸린 눈)  'o' 입 안(하품)
    /// 디자이너 스프라이트로 바꿀 때는 Render()만 교체하면 된다.
    /// </summary>
    internal static class Sprites
    {
        public const int GW = 16, GH = 14;
        static readonly Dictionary<char, Color> Palette = new Dictionary<char, Color> {
            { '#', Color.FromArgb(0x2b, 0x2b, 0x2b) }, { 'w', Color.FromArgb(0xf4, 0xf4, 0xf4) },
            { 'p', Color.FromArgb(0xf2, 0xa6, 0xb0) }, { 'o', Color.FromArgb(0xd9, 0x6c, 0x7a) },
        };

        static readonly string[] Body = {
            "..##........##..", "..###......###..", "..############..", "..############..",
            ".##############.", ".##############.", "################", ".##pp######pp##.",
            "..############..", "..############..", "..############..", "...##.....##....",
            "...##.....##....", "................" };
        static readonly string[] BodyBaby = {
            "................", "..##........##..", "..############..", "..############..",
            ".##############.", ".##############.", ".##############.", ".##pp######pp##.",
            "..############..", "..############..", "...##########...", "....##....##....",
            "................", "................" };

        // 다리: 서기 / 걷기1 / 걷기2 / 앉기(식빵)
        static readonly Dictionary<string, string[]> Legs = new Dictionary<string, string[]> {
            { "stand", new[] { "...##.....##....", "...##.....##...." } },
            { "walk1", new[] { "..##.......##...", "..##.......##..." } },
            { "walk2", new[] { "....##...##.....", "....##...##....." } },
            { "sit",   new[] { "..####...####...", "................" } },
        };
        // 표정: 왼쪽 눈 3x3, 오른쪽 눈 3x3 (행 4~6, 열 4~6 / 9~11)
        static readonly Dictionary<string, string[][]> Eyes = new Dictionary<string, string[][]> {
            { "normal",    new[] { new[] { "ww#", "ww#", "###" }, new[] { "#ww", "#ww", "###" } } },
            { "smile",     new[] { new[] { "#w#", "w#w", "###" }, new[] { "#w#", "w#w", "###" } } },
            { "excited",   new[] { new[] { "w##", "#w#", "w##" }, new[] { "##w", "#w#", "##w" } } },
            { "surprised", new[] { new[] { "www", "w#w", "www" }, new[] { "www", "w#w", "www" } } },
            { "dizzy",     new[] { new[] { "www", "w#w", "ww#" }, new[] { "www", "w#w", "#ww" } } },
            { "sleepy",    new[] { new[] { "###", "ppp", "###" }, new[] { "###", "ppp", "###" } } },
            { "blink",     new[] { new[] { "###", "ww#", "###" }, new[] { "###", "#ww", "###" } } },
            { "love",      new[] { new[] { "p#p", "ppp", "#p#" }, new[] { "p#p", "ppp", "#p#" } } },
        };
        // 꼬리(몸 오른쪽 밖, 3칸 x 4행). 프레임 3개를 번갈아 흔든다.
        static readonly string[][] Tail = {
            new[] { "...", "..#", ".##", "##." },
            new[] { "...", "...", ".##", "##." },
            new[] { ".#.", ".#.", ".##", "##." },
        };

        static readonly Dictionary<string, Bitmap> Cache = new Dictionary<string, Bitmap>();

        public static Bitmap Render(string expr, string legs, int scale, bool flip, bool baby, int tailFrame, bool yawn)
        {
            string key = string.Join("|", expr, legs, scale, flip, baby, tailFrame, yawn);
            Bitmap cached;
            if (Cache.TryGetValue(key, out cached)) return cached;

            var rows = new List<char[]>();
            foreach (var r in (baby ? BodyBaby : Body)) rows.Add(r.ToCharArray());
            var e = Eyes.ContainsKey(expr) ? Eyes[expr] : Eyes["normal"];
            for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) { rows[4 + i][4 + j] = e[0][i][j]; rows[4 + i][9 + j] = e[1][i][j]; }
            if (yawn) { rows[8][6] = 'o'; rows[8][7] = 'o'; rows[8][8] = 'o'; rows[8][9] = 'o'; rows[9][7] = 'o'; rows[9][8] = 'o'; }
            if (baby)
            {
                if (legs == "walk1") rows[11] = "...##......##...".ToCharArray();
                else if (legs == "walk2") rows[11] = ".....##..##.....".ToCharArray();
                else if (legs == "sit") rows[11] = "...###....###...".ToCharArray();
            }
            else
            {
                var l = Legs.ContainsKey(legs) ? Legs[legs] : Legs["stand"];
                rows[11] = l[0].ToCharArray(); rows[12] = l[1].ToCharArray();
            }

            int tw = 3; // 꼬리 폭
            var bmp = new Bitmap((GW + tw) * scale, GH * scale, PixelFormat.Format32bppArgb);
            using (var g = Graphics.FromImage(bmp))
            {
                g.Clear(Color.Transparent);
                int W = GW + tw;
                Action<int, int, char> put = (x, y, ch) => {
                    Color c; if (!Palette.TryGetValue(ch, out c)) return;
                    int px = flip ? (W - 1 - x) : x;
                    using (var b = new SolidBrush(c)) g.FillRectangle(b, px * scale, y * scale, scale, scale);
                };
                for (int y = 0; y < GH; y++) for (int x = 0; x < GW; x++) put(x, y, rows[y][x]);
                // 꼬리: 몸 오른쪽에 붙임 (앉았을 때는 몸에 감긴 듯 낮게)
                if (tailFrame >= 0)
                {
                    var t = Tail[tailFrame % Tail.Length];
                    int baseRow = (legs == "sit" || baby) ? 8 : 7;
                    for (int i = 0; i < t.Length; i++) for (int j = 0; j < 3; j++) put(GW - 1 + j, baseRow + i, t[i][j]);
                }
            }
            Cache[key] = bmp;
            return bmp;
        }

        /// <summary>트레이 아이콘용</summary>
        public static Icon MakeIcon()
        {
            var bmp = Render("smile", "stand", 2, false, false, 1, false);
            var sq = new Bitmap(32, 32, PixelFormat.Format32bppArgb);
            using (var g = Graphics.FromImage(sq)) { g.Clear(Color.Transparent); g.DrawImage(bmp, (32 - bmp.Width) / 2, (32 - bmp.Height) / 2); }
            return Icon.FromHandle(sq.GetHicon());
        }
    }
}

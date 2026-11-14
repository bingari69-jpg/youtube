using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;

namespace XenicsCat
{
    /// <summary>모든 데이터는 %LOCALAPPDATA%\XenicsCat 아래에만 저장한다. 외부로 보내는 것은 없다.</summary>
    internal static class Paths
    {
        public static readonly string Dir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "XenicsCat");
        public static readonly string ExeDir = AppDomain.CurrentDomain.BaseDirectory;
        public static string In(string name) { Directory.CreateDirectory(Dir); return Path.Combine(Dir, name); }
    }

    internal static class Json
    {
        static readonly JavaScriptSerializer S = new JavaScriptSerializer();
        public static T Load<T>(string path) where T : class
        {
            try { if (File.Exists(path)) return S.Deserialize<T>(File.ReadAllText(path, Encoding.UTF8)); } catch { }
            return null;
        }
        public static void Save(string path, object o)
        {
            try { File.WriteAllText(path, S.Serialize(o), Encoding.UTF8); } catch { }
        }
        public static object Parse(string text) { try { return S.DeserializeObject(text); } catch { return null; } }
    }

    internal class Settings
    {
        public string Name = "먹물";
        public int Size = 2;                 // 1 작게, 2 보통, 3 크게
        public bool Follow = true;           // 마우스 따라가기(느리게)
        public string Talk = "normal";       // often | normal | rare | off
        public int StretchMinutes = 50;      // 0이면 끔
        public int QuietFrom = 0, QuietTo = 0; // 조용한 시간(시). 같으면 없음
        public int RitualHour = 18;          // 퇴근 의식 시각. -1이면 끔
        public bool Notices = true;
        public string NoticeUrl = "";
        public string UpdateUrl = "";
        public bool Sound = false;
        public int PosX = -1, PosY = -1;

        static readonly string P = Paths.In("settings.json");
        public static Settings Load() { return Json.Load<Settings>(P) ?? new Settings(); }
        public void Save() { Json.Save(P, this); }
    }

    /// <summary>반려묘 성장. 친밀도와 함께한 날이 둘 다 차야 단계가 오른다. 페널티는 없다.</summary>
    internal class Growth
    {
        public int Xp = 0;
        public string Adopted = DateTime.Today.ToString("yyyy-MM-dd");
        public int Stage = 0;
        public string LastDaily = "";
        public int Pets = 0, Chats = 0, Rituals = 0;
        [ScriptIgnore] public DateTime LastPet = DateTime.MinValue;

        public static readonly string[] StageNames = { "아기 고양이", "어린 고양이", "청소년 고양이", "어른 고양이" };
        static readonly int[] NeedXp = { 0, 120, 400, 1000 };
        static readonly int[] NeedDays = { 0, 3, 10, 30 };
        public static readonly double[] SizeMult = { 0.62, 0.80, 0.92, 1.0 };
        static readonly string P = Paths.In("growth.json");

        public static Growth Load() { var g = Json.Load<Growth>(P) ?? new Growth(); g.TouchDaily(); return g; }
        public void Save() { Json.Save(P, this); }
        public int DaysTogether() { DateTime d; return DateTime.TryParse(Adopted, out d) ? (int)(DateTime.Today - d.Date).TotalDays + 1 : 1; }
        public string StageName { get { return StageNames[Stage]; } }
        public string Tone { get { return Stage == 0 ? "baby" : Stage == 1 ? "kid" : "adult"; } }

        public bool TouchDaily()
        {
            string today = DateTime.Today.ToString("yyyy-MM-dd");
            if (LastDaily == today) return false;
            LastDaily = today; Xp += 15; bool up = CheckStage(); Save(); return up;
        }
        /// <summary>경험치를 주고 단계가 올랐으면 true. 종류: pet chat ritual wake</summary>
        public bool Gain(string kind)
        {
            int add = 0;
            switch (kind)
            {
                case "pet": if ((DateTime.Now - LastPet).TotalSeconds < 60) return false; LastPet = DateTime.Now; Pets++; add = 4; break;
                case "chat": Chats++; add = 2; break;
                case "ritual": Rituals++; add = 10; break;
                case "wake": add = 1; break;
            }
            Xp += add; bool up = CheckStage(); Save(); return up;
        }
        bool CheckStage()
        {
            int n = Stage, days = DaysTogether();
            for (int i = 0; i < NeedXp.Length; i++) if (Xp >= NeedXp[i] && days >= NeedDays[i]) n = i;
            if (n > Stage) { Stage = n; return true; }
            return false;
        }
        public string NextRequirement()
        {
            if (Stage >= NeedXp.Length - 1) return null;
            var parts = new List<string>();
            if (Xp < NeedXp[Stage + 1]) parts.Add("친밀도 " + (NeedXp[Stage + 1] - Xp) + " 더");
            if (DaysTogether() < NeedDays[Stage + 1]) parts.Add((NeedDays[Stage + 1] - DaysTogether()) + "일 더");
            return parts.Count == 0 ? "곧!" : string.Join(", ", parts);
        }
        public string Summary()
        {
            var n = NextRequirement();
            return StageName + " · 함께한 지 " + DaysTogether() + "일 · 친밀도 " + Xp + "\n쓰다듬 " + Pets + "번 · 대화 " + Chats + "번 · 퇴근 의식 " + Rituals + "번" +
                   (n != null ? "\n다음 단계까지: " + n : "\n다 컸어! 이제 어른이다냥.");
        }
    }

    /// <summary>퇴근 의식에서 적은 "오늘 한 일" 한 줄들. journal.txt</summary>
    internal static class Journal
    {
        static readonly string P = Paths.In("journal.txt");
        public static void Add(string line)
        {
            try { File.AppendAllText(P, DateTime.Now.ToString("yyyy-MM-dd HH:mm") + " | " + line.Trim() + Environment.NewLine, Encoding.UTF8); } catch { }
        }
        public static List<string> ThisWeek()
        {
            var outp = new List<string>();
            try
            {
                if (!File.Exists(P)) return outp;
                var monday = DateTime.Today.AddDays(-(((int)DateTime.Today.DayOfWeek + 6) % 7));
                foreach (var ln in File.ReadAllLines(P, Encoding.UTF8))
                {
                    DateTime d; var parts = ln.Split(new[] { " | " }, 2, StringSplitOptions.None);
                    if (parts.Length == 2 && DateTime.TryParse(parts[0], out d) && d.Date >= monday) outp.Add(d.ToString("M/d") + " " + parts[1]);
                }
            }
            catch { }
            return outp;
        }
        public static bool DoneToday()
        {
            try
            {
                if (!File.Exists(P)) return false;
                var last = File.ReadLines(P, Encoding.UTF8).LastOrDefault(l => l.Trim().Length > 0);
                return last != null && last.StartsWith(DateTime.Today.ToString("yyyy-MM-dd"));
            }
            catch { return false; }
        }
    }

    /// <summary>
    /// 브랜드 소식. exe 옆 notices.json + 설정의 https 주소(정적 파일)에서 하루 한 번 받는다.
    /// 같은 id는 한 번만, 하루 최대 1건. 서버 프로그램은 필요 없다.
    /// </summary>
    internal class NoticeItem { public string id; public string text; public string from; public string until; }
    internal class Notices
    {
        readonly Settings settings;
        readonly List<NoticeItem> items = new List<NoticeItem>();
        Dictionary<string, string> seen;
        DateTime lastFetch = DateTime.MinValue;
        readonly object gate = new object();
        static readonly string SeenPath = Paths.In("seen_notices.json");

        public Notices(Settings s)
        {
            settings = s;
            seen = Json.Load<Dictionary<string, string>>(SeenPath) ?? new Dictionary<string, string>();
            LoadFrom(Path.Combine(Paths.ExeDir, "notices.json"));
        }
        void LoadFrom(string path)
        {
            try
            {
                if (!File.Exists(path)) return;
                var arr = Json.Parse(File.ReadAllText(path, Encoding.UTF8)) as object[];
                if (arr != null) Merge(arr);
            }
            catch { }
        }
        void Merge(object[] arr)
        {
            lock (gate)
            {
                foreach (var o in arr)
                {
                    var d = o as Dictionary<string, object>; if (d == null) continue;
                    var it = new NoticeItem { id = Str(d, "id"), text = Str(d, "text"), from = Str(d, "from"), until = Str(d, "until") };
                    if (string.IsNullOrEmpty(it.id) || string.IsNullOrEmpty(it.text)) continue;
                    if (!items.Any(x => x.id == it.id)) items.Add(it);
                }
            }
        }
        static string Str(Dictionary<string, object> d, string k) { object v; return d.TryGetValue(k, out v) && v != null ? v.ToString() : null; }

        public string Next()
        {
            if (!settings.Notices) return null;
            if ((DateTime.Now - lastFetch).TotalHours > 24) { lastFetch = DateTime.Now; ThreadPool.QueueUserWorkItem(_ => Fetch()); }
            string today = DateTime.Today.ToString("yyyy-MM-dd");
            string lastDay; if (seen.TryGetValue("__last_day__", out lastDay) && lastDay == today) return null;
            lock (gate)
            {
                foreach (var it in items)
                {
                    if (seen.ContainsKey(it.id) || !Active(it)) continue;
                    seen[it.id] = today; seen["__last_day__"] = today; Json.Save(SeenPath, seen);
                    return it.text.Length > 300 ? it.text.Substring(0, 300) : it.text;
                }
            }
            return null;
        }
        static bool Active(NoticeItem it)
        {
            DateTime d;
            if (!string.IsNullOrEmpty(it.from) && DateTime.TryParse(it.from, out d) && DateTime.Today < d.Date) return false;
            if (!string.IsNullOrEmpty(it.until) && DateTime.TryParse(it.until, out d) && DateTime.Today > d.Date) return false;
            return true;
        }
        void Fetch()
        {
            var url = (settings.NoticeUrl ?? "").Trim();
            if (!url.StartsWith("https://")) return;
            var text = Http.Get(url); if (text == null) return;
            var arr = Json.Parse(text) as object[]; if (arr != null) Merge(arr);
        }
    }

    internal static class Http
    {
        public static string Get(string url, int timeoutMs = 8000)
        {
            try
            {
                ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12;
                var req = (HttpWebRequest)WebRequest.Create(url);
                req.Timeout = timeoutMs; req.UserAgent = "XenicsCat/1.0";
                using (var resp = (HttpWebResponse)req.GetResponse())
                using (var sr = new StreamReader(resp.GetResponseStream(), Encoding.UTF8)) return sr.ReadToEnd();
            }
            catch { return null; }
        }
    }

    /// <summary>업데이트 확인: 설정의 https 주소에서 {"version":"1.1.0","url":"https://..."} 를 읽는다. 강제하지 않는다.</summary>
    internal static class Updater
    {
        public static void Check(Settings s, Action<string, string> onNew)
        {
            var url = (s.UpdateUrl ?? "").Trim();
            if (!url.StartsWith("https://")) return;
            ThreadPool.QueueUserWorkItem(_ =>
            {
                var text = Http.Get(url); if (text == null) return;
                var d = Json.Parse(text) as Dictionary<string, object>; if (d == null) return;
                object v, u; if (!d.TryGetValue("version", out v) || !d.TryGetValue("url", out u)) return;
                Version remote, local;
                if (Version.TryParse(v.ToString(), out remote) && Version.TryParse(App.Version, out local) && remote > local) onNew(v.ToString(), u.ToString());
            });
        }
    }
}

using System;
using System.Collections.Generic;

namespace XenicsCat
{
    /// <summary>고양이가 "먼저 말을 걸" 때를 정한다. 키 입력 내용은 모르고, 쉬는 중/일하는 중만 안다.</summary>
    internal class Monitor
    {
        readonly Settings s;
        readonly Random r = new Random();
        readonly Dictionary<string, string> slotDone = new Dictionary<string, string>();
        DateTime workStart = DateTime.MinValue;   // 연속 작업 시작
        DateTime lastActive = DateTime.MinValue;  // 마지막으로 활동 중이었던 시각
        DateTime lastStretch = DateTime.MinValue;
        DateTime lastRandom = DateTime.Now;
        DateTime lastLongWork = DateTime.MinValue;
        DateTime lastNight = DateTime.MinValue;
        public string RitualDoneDay = "";
        public int TalkCountToday = 0;
        string talkDay = "";

        public Monitor(Settings settings) { s = settings; }

        public bool UserActive { get { return Native.IdleSeconds() < 300; } }   // 5분 안에 입력이 있었나
        public bool UserAway { get { return Native.IdleSeconds() > 900; } }     // 15분 넘게 자리 비움
        public double WorkMinutes { get { return workStart == DateTime.MinValue ? 0 : (DateTime.Now - workStart).TotalMinutes; } }

        bool Quiet()
        {
            if (s.QuietFrom == s.QuietTo) return false;
            int h = DateTime.Now.Hour;
            return s.QuietFrom < s.QuietTo ? (h >= s.QuietFrom && h < s.QuietTo) : (h >= s.QuietFrom || h < s.QuietTo);
        }
        bool OnceToday(string key)
        {
            string today = DateTime.Today.ToString("yyyy-MM-dd");
            string d; if (slotDone.TryGetValue(key, out d) && d == today) return false;
            slotDone[key] = today; return true;
        }
        int DailyCap() { switch (s.Talk) { case "often": return 6; case "rare": return 2; case "off": return 0; default: return 4; } }
        int RandomInterval() { switch (s.Talk) { case "often": return 45; case "rare": return 180; default: return 90; } }

        /// <summary>매 틱(1초) 호출. 활동 세션을 추적한다.</summary>
        public void Tick()
        {
            var now = DateTime.Now;
            double idle = Native.IdleSeconds();
            if (idle < 60)
            {
                if ((now - lastActive).TotalMinutes > 5) workStart = now;   // 5분 넘게 쉬었으면 새 세션
                lastActive = now;
            }
            string today = DateTime.Today.ToString("yyyy-MM-dd");
            if (talkDay != today) { talkDay = today; TalkCountToday = 0; }
        }

        /// <summary>지금 할 말이 있으면 (문장, 표정, 종류). 없으면 null. 종류: stretch slot long random</summary>
        public Tuple<string, string, string> Check()
        {
            var now = DateTime.Now;
            if (!UserActive) return null;

            // 1) 오래 앉아 있음: 말 걸기 꺼도 동작 (건강 알림), 조용한 시간엔 쉼
            if (s.StretchMinutes > 0 && WorkMinutes >= s.StretchMinutes && (now - lastStretch).TotalMinutes >= s.StretchMinutes && !Quiet())
            {
                lastStretch = now; workStart = now;
                return Tuple.Create(string.Format(Lines.Pick(Lines.Stretch), s.StretchMinutes), "surprised", "stretch");
            }
            if (s.Talk == "off" || Quiet() || TalkCountToday >= DailyCap()) return null;

            int h = now.Hour; var wd = now.DayOfWeek;
            string slot = null;
            if (wd == DayOfWeek.Monday && h >= 8 && h < 11) slot = "monday_morning";
            else if ((wd == DayOfWeek.Saturday || wd == DayOfWeek.Sunday) && h >= 8 && h < 12) slot = "weekend_morning";
            else if (h >= 6 && h < 11) slot = "morning";
            else if (h >= 12 && h < 14) slot = "lunch";
            else if (h >= 15 && h < 16) slot = "afternoon_slump";
            else if (h >= 18 && h < 21) slot = wd == DayOfWeek.Friday ? "friday_evening" : "evening";
            else if (h >= 22 || h < 5) slot = "late_night";
            if (slot != null && OnceToday(slot))
            {
                TalkCountToday++;
                string expr = (slot == "late_night" || slot == "afternoon_slump") ? "sleepy" : "smile";
                return Tuple.Create(Lines.Pick(Lines.Slots[slot]), expr, "slot");
            }
            if (WorkMinutes >= 120 && (now - lastLongWork).TotalHours > 2)
            {
                lastLongWork = now; TalkCountToday++;
                return Tuple.Create(Lines.Pick(Lines.Slots["long_work"]), "normal", "long");
            }
            double interval = RandomInterval() * (0.8 + r.NextDouble() * 0.5);
            if ((now - lastRandom).TotalMinutes > interval)
            {
                lastRandom = now; TalkCountToday++;
                return Tuple.Create(Lines.Pick(Lines.Random), "smile", "random");
            }
            return null;
        }

        /// <summary>퇴근 의식을 띄울 때인가 (하루 1회, 설정 시각부터 2시간 안, 사용자 활동 중)</summary>
        public bool RitualDue()
        {
            if (s.RitualHour < 0) return false;
            string today = DateTime.Today.ToString("yyyy-MM-dd");
            if (RitualDoneDay == today || Journal.DoneToday()) return false;
            int h = DateTime.Now.Hour;
            return h >= s.RitualHour && h < s.RitualHour + 2 && UserActive && !Quiet();
        }
        public void MarkRitual() { RitualDoneDay = DateTime.Today.ToString("yyyy-MM-dd"); }

        /// <summary>고양이가 스스로 잠들 때: 사용자가 자리를 비웠거나 밤</summary>
        public bool ShouldSleep()
        {
            int h = DateTime.Now.Hour;
            return UserAway || (h >= 23 || h < 6);
        }
    }
}

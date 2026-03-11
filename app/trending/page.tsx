'use client';

import { useState, useEffect } from 'react';
import { Header } from '@/components/layout/header';
import { TrendingUp, Users, PlaySquare, Eye, ExternalLink, RefreshCw } from 'lucide-react';
import { formatCount } from '@/lib/youtube';
import Link from 'next/link';
import Image from 'next/image';

interface TrendingChannel {
  id: string;
  title: string;
  description: string;
  thumbnailUrl: string;
  subscriberCount: number;
  videoCount: number;
  viewCount: number;
  trendingVideoCount: number;
  topVideoTitle?: string;
}

const regions = [
  { code: 'KR', name: '대한민국', emoji: '🇰🇷' },
  { code: 'US', name: '미국', emoji: '🇺🇸' },
  { code: 'JP', name: '일본', emoji: '🇯🇵' },
  { code: 'IN', name: '인도', emoji: '🇮🇳' },
  { code: 'BR', name: '브라질', emoji: '🇧🇷' },
  { code: 'GB', name: '영국', emoji: '🇬🇧' },
  { code: 'ES', name: '스페인', emoji: '🇪🇸' },
];

export default function TrendingPage() {
  const [region, setRegion] = useState('KR');
  const [channels, setChannels] = useState<TrendingChannel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTrending = async (regionCode: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/youtube/api/trending?regionCode=${regionCode}`);
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setChannels(data.channels);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTrending(region);
  }, [region]);

  return (
    <div className="min-h-screen bg-[#0C0C0E] text-white">
      <Header />

      <main className="max-w-[1400px] mx-auto px-6 py-12">
        {/* 히어로 섹션 */}
        <section className="mb-12">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-8">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cl-500/10 border border-cl-500/20 text-cl-400 text-xs font-bold uppercase tracking-wider mb-3">
                <TrendingUp size={14} />
                Real-time Insights
              </div>
              <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight mb-4">
                글로벌 <span className="brand-text-gradient">떡상 채널</span> 추천
              </h1>
              <p className="text-gray-400 text-lg max-w-2xl">
                국가별 인기 급상승 동영상을 분석하여 현재 가장 화제가 되고 있는 채널들을 선정했습니다. 
                지금 뜨는 글로벌 트렌드를 확인해 보세요.
              </p>
            </div>

            {/* 국가 선택 */}
            <div className="flex flex-wrap gap-2 p-1.5 bg-gray-900/50 rounded-2xl border border-gray-800/50 backdrop-blur-md">
              {regions.map((r) => (
                <button
                  key={r.code}
                  onClick={() => setRegion(r.code)}
                  className={`
                    flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all
                    ${region === r.code 
                      ? 'bg-cl-500 text-white shadow-lg shadow-cl-500/25' 
                      : 'text-gray-400 hover:text-white hover:bg-gray-800'
                    }
                  `}
                >
                  <span className="text-lg">{r.emoji}</span>
                  {r.name}
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* 채널 그리드 */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-40 gap-4">
            <RefreshCw className="animate-spin text-cl-500" size={48} />
            <p className="text-gray-400 font-medium animate-pulse">각 나라의 실시간 트렌드를 분석 중입니다...</p>
          </div>
        ) : error ? (
          <div className="glass border-red-900/50 p-12 text-center rounded-3xl max-w-xl mx-auto">
            <p className="text-red-400 font-medium mb-4">에러: {error}</p>
            <button 
              onClick={() => fetchTrending(region)} 
              className="px-6 py-2 bg-gray-800 rounded-xl hover:bg-gray-700 transition"
            >
              다시 시도
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {channels.map((channel, idx) => (
              <div 
                key={channel.id}
                className="group glass relative overflow-hidden rounded-3xl border border-gray-800/50 hover:border-cl-500/50 transition-all duration-500 hover:-translate-y-1"
              >
                {/* 랭킹 뱃지 */}
                <div className="absolute top-4 left-4 z-10 size-8 flex items-center justify-center rounded-full bg-black/40 backdrop-blur-md border border-white/10 text-xs font-bold pointer-events-none">
                  {idx + 1}
                </div>

                <a 
                  href={`https://www.youtube.com/channel/${channel.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block p-6 hover:bg-white/[0.02] transition-colors"
                >
                  <div className="flex items-start gap-4 mb-6">
                    <div className="relative size-20 flex-shrink-0">
                      <Image
                        src={channel.thumbnailUrl}
                        alt={channel.title}
                        fill
                        className="rounded-2xl object-cover ring-2 ring-gray-800/50"
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-lg font-bold text-white truncate group-hover:text-cl-400 transition mb-1 uppercase tracking-tight">
                        {channel.title}
                      </h3>
                      <p className="text-xs text-gray-500 line-clamp-2 leading-relaxed mb-3">
                        {channel.description || '이 채널에 대한 정보가 없습니다.'}
                      </p>
                      <div className="flex gap-4 text-xs font-medium text-gray-300">
                        <div className="flex items-center gap-1.5">
                          <Users size={12} className="text-cl-500" />
                          {formatCount(channel.subscriberCount)}
                        </div>
                        <div className="flex items-center gap-1.5">
                          <PlaySquare size={12} className="text-cl-500" />
                          {formatCount(channel.videoCount)}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* 트렌딩 요약 */}
                  <div className="bg-white/5 rounded-2xl p-4 border border-white/5 space-y-3">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-gray-400">인기 급상승 지수</span>
                      <div className="flex items-center gap-1 text-cl-400 font-bold">
                        <TrendingUp size={12} />
                        +{channel.trendingVideoCount * 20} pts
                      </div>
                    </div>
                    
                    {channel.topVideoTitle && (
                      <div className="pt-2 border-t border-white/5">
                        <p className="text-[10px] text-gray-500 uppercase tracking-widest font-bold mb-1.5">Hot Topic</p>
                        <p className="text-sm text-gray-100 font-medium line-clamp-2 leading-snug">
                          {channel.topVideoTitle}
                        </p>
                      </div>
                    )}
                  </div>
                </a>

                {/* 하단 버튼 */}
                <div className="flex border-t border-white/5">
                  <Link
                    href={`/channel-analysis?id=${channel.id}`}
                    className="flex-1 flex items-center justify-center gap-2 py-4 text-xs font-bold text-gray-400 hover:text-white hover:bg-white/5 transition"
                  >
                    데이터 분석 <Eye size={14} />
                  </Link>
                  <a
                    href={`https://www.youtube.com/channel/${channel.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 flex items-center justify-center gap-2 py-4 text-xs font-bold text-gray-400 hover:text-white hover:bg-white/5 border-l border-white/5 transition"
                  >
                    채널 방문 <ExternalLink size={14} />
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 안내문구 */}
        <section className="mt-20 text-center">
            <div className="inline-block p-8 rounded-[40px] bg-gradient-to-b from-gray-900/50 to-transparent border border-gray-800/30 max-w-3xl">
                <p className="text-gray-400 text-sm leading-relaxed">
                    * <b>떡상 지수</b>는 최근 24시간 동안 실시간으로 올라온 각 국가별 인기 동영상(Trending) 목록에 해당 채널이 얼마나 자주 노출되었는지를 기준으로 산출됩니다. <br/>
                    트렌드 데이터는 5분마다 갱신되며, 유튜브 공식 API 데이터에 기반합니다.
                </p>
            </div>
        </section>
      </main>

      <footer className="border-t border-white/5 py-12 text-center text-gray-600 text-xs">
        © 2026 XENICS Youtube Analytics. All rights reserved.
      </footer>
    </div>
  );
}

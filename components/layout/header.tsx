'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Search, BarChart3, Folder, TrendingUp, Gamepad2 } from 'lucide-react';
import { SettingsButton } from './settings-modal';

// 네비게이션 메뉴 항목 (newTab: 앱 밖의 전체 화면 페이지를 새 탭으로 연다)
const navItems = [
  { href: '/', label: '영상 찾기', icon: Search },
  { href: '/channel-search', label: '채널 찾기', icon: BarChart3 },
  { href: '/trending', label: '떡상 추천', icon: TrendingUp },
  { href: '/channel-analysis', label: '채널 분석', icon: BarChart3 },
  { href: '/collected', label: '수집한 영상', icon: Folder },
  { href: '/games/stunt-agency', label: '스턴트 대역 사무소', icon: Gamepad2, newTab: true },
];

// CreatorLens 공통 헤더 (글래스모피즘 + sticky)
export function Header() {
  const pathname = usePathname();

  return (
    <header className="glass sticky top-0 z-50">
      <div className="max-w-[1400px] mx-auto px-4 py-0 flex items-center gap-8">
        {/* 로고 */}
        <Link href="/" className="text-xl font-bold text-gray-100 flex items-center gap-1 py-4 flex-shrink-0">
          <span className="brand-text-gradient">XENICS</span> 유튜브 분석기
        </Link>

        {/* 네비게이션 */}
        <nav className="flex items-center gap-0 overflow-x-auto flex-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href ||
              (item.href === '/' && pathname === '/') ||
              (item.href === '/channel-search' && (pathname === '/channel-search' || pathname.startsWith('/channel/')) ) ||
              (item.href === '/channel-analysis' && pathname === '/channel-analysis') ||
              (item.href === '/collected' && pathname === '/collected');

            // 게임은 Next 페이지가 아니라 HTML 한 장이라 새 탭에서 연다
            // (Link 를 써야 next.config 의 basePath '/youtube' 가 주소 앞에 붙는다)
            if (item.newTab) {
              const Icon = item.icon;
              return (
                <Link
                  key={item.label}
                  href={item.href}
                  target="_blank"
                  rel="noopener"
                  prefetch={false}
                  className="flex items-center gap-1.5 px-4 py-4 text-sm whitespace-nowrap transition-colors border-b-2 text-gray-400 border-transparent hover:text-gray-200"
                >
                  <Icon className="w-4 h-4" />
                  {item.label}
                </Link>
              );
            }

            return (
              <Link
                key={item.label}
                href={item.href}
                className={`
                  flex items-center gap-1.5 px-4 py-4 text-sm whitespace-nowrap transition-colors border-b-2
                  ${isActive
                    ? 'text-cl-500 border-cl-500 font-medium'
                    : 'text-gray-400 border-transparent hover:text-gray-200'
                  }
                `}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* 설정 버튼 */}
        <SettingsButton />
      </div>
    </header>
  );
}

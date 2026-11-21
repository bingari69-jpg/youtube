import { readFile } from 'node:fs/promises';
import path from 'node:path';

// GET /games/stunt-agency — 게임 폴더의 index.html을 그대로 내보낸다.
// 게임 원본은 games/stunt-agency/index.html 하나만 두고, 여기서는 복사하지 않고 읽기만 한다.
export const dynamic = 'force-dynamic';

export async function GET() {
  const file = path.join(process.cwd(), 'games', 'stunt-agency', 'index.html');
  try {
    const html = await readFile(file, 'utf-8');
    return new Response(html, {
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-store',
      },
    });
  } catch {
    return new Response('게임 파일을 찾을 수 없습니다: games/stunt-agency/index.html', {
      status: 404,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
  }
}

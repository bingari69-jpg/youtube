/**
 * 영상 제목과 태그에서 빈도 높은 키워드를 추출합니다.
 */
export function extractTrendKeywords(videos: Array<{ title: string; description?: string }>) {
  const wordMap = new Map<string, number>();

  // 조사, 공백 등 제외할 패턴 (간단하게)
  const stopWords = new Set(['이', '가', '은', '는', '도', '를', '을', '의', '와', '과', '에', '에서', '로', '으로', '하고', '그리고', '하지만']);

  for (const video of videos) {
    // 제목에서 단어 추출 (특수문자 제거 후 공백 기준)
    const words = video.title
      .replace(/[^\w\s가-힣]/g, ' ')
      .split(/\s+/)
      .filter((w) => w.length > 1 && !stopWords.has(w));

    for (const w of words) {
      wordMap.set(w, (wordMap.get(w) || 0) + 1);
    }
  }

  // 빈도순 정렬 (상위 20개)
  return Array.from(wordMap.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 20)
    .map(([text, value]) => ({ text, value }));
}

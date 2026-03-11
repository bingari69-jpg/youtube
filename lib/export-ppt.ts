/**
 * 채널 분석 데이터를 PPT 파일로 내보냅니다.
 * (서버 사이드 API를 호출하여 처리)
 */
export const exportToPPT = async (data: any) => {
  try {
    const res = await fetch('/api/export-ppt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    if (!res.ok) throw new Error('PPT 리포트 생성 실패');

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `YouTube_Report_${data.channelTitle.replace(/[\s\/]/g, '_')}.pptx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Export error:', error);
    alert('PPT 리포트 생성 중 오류가 발생했습니다.');
  }
};

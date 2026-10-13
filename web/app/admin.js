// 관리자 모드: 누가 '관리자'인지 정하는 곳.
// 아래 목록에 적힌 이메일로 로그인했을 때만 '기준 등록' 탭이 열려요. (Firebase 콘솔 > Authentication 에서 만든 계정의 이메일)
// 이메일을 바꾸거나 더하려면 이 목록만 고치면 돼요. 비밀번호는 여기에 적지 마세요(적을 필요도 없어요).
export const ADMIN_EMAILS = ["sysadmin@hanwha.com"];

export function isAdminEmail(email) {
  if (!email) return false;
  const e = String(email).trim().toLowerCase();
  return ADMIN_EMAILS.some((a) => a.trim().toLowerCase() === e);
}

// Firebase 로그인 오류 -> 쉬운 한국어
export function authErrorText(e) {
  const code = (e && e.code) || "";
  if (/network/.test(code)) return "인터넷에 연결돼 있지 않아요. 연결을 확인하고 다시 해 보세요.";
  if (/too-many/.test(code)) return "시도가 너무 많아요. 잠시 뒤에 다시 해 보세요.";
  if (/invalid-email/.test(code)) return "이메일 모양이 맞지 않아요.";
  if (/invalid-credential|wrong-password|user-not-found|invalid-login/.test(code)) return "이메일이나 비밀번호가 맞지 않아요. (관리자 계정이 아니면 로그인할 수 없어요)";
  return "로그인하지 못했어요: " + ((e && e.message) || e);
}

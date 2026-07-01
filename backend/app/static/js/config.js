// ===== 全局状态 =====
const API_BASE = '';
let currentUser = null;
let currentQuestion = null;
let selectedOption = null;
let studySessionId = null;
let isAnswered = false;
let _sessionCorrect = 0;
let _sessionXp = 0;
let _askedQuestionIds = new Set();

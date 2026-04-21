export type Preset = "full" | "quick" | "low_energy" | "quiz" | "card_sprint";
export type CardType = "basic" | "cloze" | "reversed";
export type Score = "strong" | "partial" | "missing";

export interface QuizQuestion {
  id: string;
  question_text: string;
  question_type: "multiple_choice" | "fill_blank" | "calculation" | "short_answer";
  options: string[] | null;
  difficulty: "easy" | "medium" | "hard";
  topic: string | null;
}

export interface QuizAnswer {
  id: string;
  question_id: string;
  answer_text: string;
  score: Score;
  feedback: string;
  answer_key: string | null;
}

export interface GapAnalysis {
  strong_areas: string[];
  weak_areas: string[];
  missing_areas: string[];
}

export interface ElaborationTurn {
  id: string;
  role: "buddy" | "user";
  content: string;
  position: number;
}

export interface ApplicationOut {
  id: string;
  challenge_text: string;
  user_response: string | null;
  buddy_feedback: string | null;
}

export interface CardProposal {
  id: string;
  front: string;
  back: string;
  card_type: CardType;
  tags: string[];
  source_topic: string | null;
  is_gap_card: boolean;
  duplicate_warning: boolean;
  approved: boolean;
  committed: boolean;
  anki_note_id: number | null;
}

export interface SessionSummary {
  id: string;
  title: string | null;
  preset: Preset;
  current_step: number;
  status: string;
  created_at: string;
  weak_areas: string[];
  cards_committed: number;
}

export interface SessionDetail {
  id: string;
  title: string | null;
  preset: Preset;
  active_steps: number[];
  current_step: number;
  status: string;
  created_at: string;
  updated_at: string;
  target_deck: string | null;
  topics: string[];
  priming_questions: string[];
  quiz_questions: QuizQuestion[];
  quiz_answers: QuizAnswer[];
  gap_analysis: GapAnalysis | null;
  elaboration_turns: ElaborationTurn[];
  application: ApplicationOut | null;
  card_proposals: CardProposal[];
}

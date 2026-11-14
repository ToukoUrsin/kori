export type Lang = "en" | "fi";
export type BasketKey = "fixed" | "surprise" | "everyday";
export type Status = "comfortable" | "tight" | "very_tight" | "empty";
export type Tone = "warn" | "info" | "good";

export interface Persona {
  id: string;
  name: string;
  age: number;
  area: string;
  blurb: string;
  partial_view: boolean;
  safe?: number;
  status?: Status;
}

export interface SpokenFor {
  key: "fixed" | "surprise" | "saving" | "cushion" | "safe" | "buffer" | string;
  label: string;
  amount: number;
}

export interface Upcoming {
  date: string;
  category: string;
  amount: number;
  label: string;
  window?: [string, string];
}

export interface SafeData {
  pay_word?: string;
  amount: number;
  per_day: number;
  this_week: number;
  week_days: number;
  days_to_payday: number;
  next_payday: string;
  status: Status;
  status_label?: string;
  status_line?: string;
  limit: "budget" | "cash";
  balance: number;
  usual_per_day: number;
  pace_ratio: number;
  budget: {
    income: number;
    fixed: number;
    surprise: number;
    saving: number;
    everyday_monthly: number;
    cycle_days: number;
    everyday_budget: number;
    everyday_spent: number;
    left: number;
    cycle_start: string;
  };
  cash: {
    balance: number;
    fixed_due: number;
    surprise_reserve: number;
    saving_left: number;
    cushion: number;
    free: number;
  };
  upcoming: Upcoming[];
  spoken_for: SpokenFor[];
  late_pay: { date: string; extra_days: number; rate: number; extra_needed: number; covered: boolean } | null;
  partial_view: boolean;
  cushion: number;
}

export interface ForecastEvent {
  type: "bill" | "payday" | string;
  category?: string;
  label?: string;
  amount: number;
}
export interface ForecastPoint {
  date: string;
  balance: number;
  events: ForecastEvent[];
}
export interface ForecastPace {
  pace: string;
  series: ForecastPoint[];
  lowest: { balance: number; date: string };
  before_payday: number;
  next_payday: string;
  goes_negative: boolean;
  below_cushion: boolean;
  bills?: { total: number; count: number; label: string; items?: { date: string; category: string; label: string; amount: number }[]; largest_day?: { date: string; total: number; count: number; label: string } };
}
export interface ForecastData {
  pay_word?: string;
  usual: ForecastPace;
  safe: ForecastPace;
  cushion: number;
  per_day: { usual: number; safe: number };
  salary: number;
  today: string;
}

export interface BasketCategory {
  category: string;
  label: string;
  icon: string;
  amount: number;
  count: number;
  usual: number;
}
export interface Basket {
  key: BasketKey;
  label: string;
  short: string;
  desc: string;
  amount: number;
  usual: number;
  vs_usual_pct: number | null;
  categories: BasketCategory[];
  share: number;
}
export interface BasketsData {
  month: string;
  is_current: boolean;
  days_elapsed: number;
  days_in_month: number;
  income: number;
  baskets: Basket[];
  spend: number;
  usual_spend: number;
  saved: number;
  left_over: number;
}

export interface Notice {
  id: string;
  tone: Tone;
  priority?: number;
  title: string;
  body: string;
  ask: string;
  card?: string | null;
  metric?: number;
}

export interface SaveData {
  now: number;
  monthly_capacity: number;
  already_saving_monthly: number;
  extra_monthly: number;
  buffer: {
    balance: number;
    musts_monthly: number;
    months_covered: number;
    target_months: number;
    target: number;
    gap: number;
  };
  partial_view?: boolean;
}

export interface ShapeAxis {
  key: string;
  label: string;
  score: number;
}
export interface ProfileData {
  archetype: { key: string; name: string; tagline: string };
  traits?: { key: string; name: string; percentile: number; evidence: string }[];
  shape: ShapeAxis[];
  fitness: number;
  strongest?: ShapeAxis;
  weakest?: ShapeAxis;
  compared_with?: string;
}

export interface Goal {
  name: string;
  amount: number;
  monthly_room: number;
  months: number | null;
}

export interface Home {
  persona: Persona;
  today: string;
  greeting: string;
  pay_word?: string;
  lessons_total?: number;
  safe: SafeData;
  forecast: ForecastData;
  baskets: BasketsData;
  notices: Notice[];
  save: SaveData;
  profile: ProfileData;
  suggestions: string[];
  goal: Goal | null;
  lessons: {
    done: number;
    total: number;
    next: { id: string; title: string; minutes: number; concept: string } | null;
  };
  pins: number;
  loop?: LoopData;
}

export interface LoopHistoryRow {
  label: string;
  within: boolean;
}
export interface LoopCheckIn {
  available: boolean;
  headline: string;
  what_did_it?: string | null;
  driver_line?: string | null;
  history_line?: string | null;
  period?: string | null;
  within?: boolean;
  over_by?: number;
  difference?: number;
  partial_view?: boolean;
  linked_view?: { note?: string; [key: string]: unknown } | null;
  history?: LoopHistoryRow[];
}
export interface LoopReplay {
  unit?: string;
  held: number;
  total: number;
  rows: { label: string; total: number; held: boolean }[];
  text: string;
}
export interface LoopWorth { amount: number; of_overshoot?: number; text: string }
export interface LoopQuestion { text: string; answers: { label: string; pick: number; title: string; key?: string }[] }
export interface LoopSuggestion {
  kind: "cap_category" | "pause_category" | "daily_pace" | "set_aside" | "none" | string;
  target?: string | null;
  target_label?: string | null;
  cap?: number | null;
  amount?: number | null;
  until?: string | null;
  until_label?: string | null;
  days_left?: number | null;
  title: string;
  why: string;
  worth?: LoopWorth | null;
  replay?: LoopReplay | null;
  reversible?: string | null;
  alternatives?: (LoopSuggestion & { question?: null })[];
  question?: LoopQuestion | null;
  next?: string | null;
  cycle?: { start: string; end: string; everyday_available?: number; everyday_spent?: number; within?: boolean; over_by?: number; difference?: number; driver?: { label: string; purchases?: LoopPurchase[] } | null };
}
export interface LoopPurchase { date: string; merchant?: string | null; amount: number; category?: string }
export interface LoopAction {
  kind: string;
  target?: string | null;
  target_label?: string | null;
  cap?: number | null;
  amount?: number | null;
  title: string;
  days_left?: number;
  until_label?: string | null;
  verdict: "on_track" | "at_risk" | "over" | "done" | string;
  limit?: number;
  spent?: number;
  left?: number;
  unit: "cycle" | "day" | string;
  days_in?: number;
  left_per_week?: number;
  lands_at_current_pace?: number;
  pace_now?: number;
  saving_monthly?: number;
  purchases?: LoopPurchase[];
  why?: string;
  line: string;
  follow_up_preview?: { label: string; text: string; held?: boolean; [key: string]: unknown } | null;
}
export interface LoopData {
  check_in: LoopCheckIn;
  suggestion?: LoopSuggestion | null;
  action?: LoopAction | null;
}

export interface Tx {
  id?: number;
  date: string;
  time?: string;
  amount: number;
  category?: string;
  category_label?: string;
  kind?: string;
  kind_label?: string;
  merchant?: string | null;
  basket?: BasketKey;
}

export interface HistoryMonth {
  month: string;
  label: string;
  fixed: number;
  surprise: number;
  everyday: number;
  income: number;
  spend: number;
  partial: boolean;
}
export interface BasketsResponse {
  current: BasketsData;
  history: HistoryMonth[];
  usual: Record<BasketKey, number>;
  income: number;
  left_over: number;
  categories: {
    category: string;
    label: string;
    icon: string;
    basket: BasketKey;
    default_basket: BasketKey;
    usual: number;
  }[];
  slips: {
    days: number;
    under: number;
    count: number;
    total: number;
    per_year: number;
    average: number;
    top_kinds: { kind: string; total: number; count: number; label?: string }[];
  };
  labels: Record<BasketKey, { label: string; short: string; desc: string }>;
}

export interface PlanResponse {
  usual: { income: number; fixed: number; surprise: number; everyday: number; saving: number; left_over: number };
  categories: { key: string; label: string; icon: string; basket: BasketKey; usual: number }[];
  prefs: {
    cushion: number | null;
    savings_goal_monthly: number | null;
    basket_overrides: Record<string, BasketKey>;
    goal: { name: string; amount: number } | null;
  };
  cushion: number;
  savings_plan: number;
  goal: Goal | null;
  safe: { amount: number; per_day: number; days_to_payday: number; status: Status; status_label?: string; status_line?: string; usual_per_day: number };
  save: SaveData;
  balance: number;
  reason?: string | null;
}

export type Change =
  | { type: "cut"; target: string; pct: number }
  | { type: "set"; target: string; monthly: number }
  | { type: "one_off"; label: string; amount: number }
  | { type: "save"; monthly: number }
  | { type: "add_cost"; label?: string; monthly: number }
  | { type: "income"; monthly: number };

export interface WhatIfLine {
  type: string;
  target?: string;
  label: string;
  basket?: BasketKey;
  pct?: number | null;
  from_monthly?: number;
  to_monthly?: number;
  monthly_change?: number;
  amount?: number;
}
export interface WhatIfData {
  changes: WhatIfLine[];
  months: number;
  monthly_effect: number;
  yearly_effect: number;
  one_off_total: number;
  total_effect_over_period: number;
  left_over: { now: number; after: number };
  everyday_per_day: { now: number; after: number };
  series: { month: number; baseline: number; scenario: number }[];
  yearly_equals?: { what: string; count: number }[];
  if_set_aside?: {
    monthly: number;
    years: { years: number; no_return: number; example_4pct: number }[];
    note: string;
  };
  goal?: { name: string; amount: number; months_now: number | null; months_after: number | null };
  safe_effect?: {
    kind: string;
    per_cycle: { now: number | null; after: number | null; change: number };
    per_day: { now: number | null; after: number | null; change: number };
    safe_to_spend: { before: number; after: number; change: number; per_day_before: number; per_day_after: number };
    today: { amount: number; per_day: number; until: string; changes_now: boolean };
    starts: string;
    partial_view: boolean;
    text: string;
  };
  saving?: { monthly: number; yearly: number; from_left_over: number; from_trim: number; fits: boolean };
  gap?: { monthly: number; per_day: number; trim_per_day: number; everyday_per_day_before: number; everyday_per_day_after: number; already_short_monthly: number; everyday_usual_monthly: number; everyday_needed_monthly: number; text: string };
  projection?: { meaningful: boolean; reason: string | null };
  one_off?: {
    balance_now: number;
    balance_after: number;
    covered_by_balance: boolean;
    surprise_reserve_monthly: number;
    months_of_reserve: number | null;
    months_to_rebuild: number | null;
    musts_covered_after_months: number | null;
  };
}

export interface QueryGroup {
  key?: string;
  label: string;
  total: number;
  count: number;
  share?: number;
  partial?: boolean;
}
export interface QueryData {
  period: { label: string; from: string; to: string; days: number };
  total: number;
  count: number;
  average_per_purchase: number;
  per_month?: number | null;
  per_day?: number | null;
  group_by?: string;
  groups?: QueryGroup[];
  average?: number | null;
  comparison?: { label: string; total: number; count: number; delta: number; pct: number | null };
  transactions?: Tx[];
}

export interface PeerRow {
  key: string;
  label: string;
  you: number;
  median: number;
  p25: number;
  p75: number;
  percentile: number;
  diff: number;
  diff_pct: number | null;
  icon?: string;
  finland?: { eur_month: number; source: string; group?: string; survey_year?: number; basis?: string };
}
export interface PeersData {
  group: { by: string; label: string; size: number; min_group_size?: number };
  window?: string;
  categories: PeerRow[];
  baskets: PeerRow[];
  saving?: PeerRow;
  income?: PeerRow;
  note: string;
}

export interface TrackItem {
  month: string;
  label: string;
  as_of: string;
  safe: number;
  per_day: number;
  days: number;
  spent: number;
  within: boolean;
  held: boolean;
  lowest_if_followed: number;
  went_below_zero: boolean;
  real_lowest: number;
  pay_late: boolean;
  counted: boolean;
  why: string | null;
  cause: string | null;
}
export interface TrackData {
  day_of_month: number;
  months_checked: number;
  held: number;
  missed: number;
  stayed_within: number;
  went_over: number;
  below_zero_when_within: number;
  below_zero_when_over: number;
  pay_late_months: number;
  items: TrackItem[];
  method?: string;
  months_number_would_have_held?: number;
  months_stayed_within_number?: number;
  count_labels?: { en: { held: string; stayed_within: string }; fi: { held: string; stayed_within: string } };
  population?: {
    customers: number;
    cases: number;
    held_pct: number;
    balance_as_budget_pct: number;
    labels?: { en: { held_pct: string; balance_as_budget_pct: string }; fi: { held_pct: string; balance_as_budget_pct: string } };
  } | null;
}

export interface LessonCardData {
  id: string;
  concept: string;
  minutes: number;
}

export interface AffordData {
  amount: number;
  label: string;
  basket: BasketKey | string;
  verdict: string;
  headline: string;
  short_by: number;
  safe: { before: number; after: number };
  per_day: { before: number; after: number };
  usual_per_day: number;
  days_to_payday: number;
  next_payday: string;
  status: { before: Status; after: Status };
  from_safe_to_spend: number;
  reserve: { available: number; used: number; left_after: number; covers_it: boolean; beyond_reserve: number; from_buffer: number; from_safe_to_spend: number } | null;
  account: { balance_before: number; balance_after: number; can_take_it: boolean; buffer_before: number; buffer_after: number };
  options: { key: string; date?: string; days?: number; per_day_until_then?: number; per_day_after_buying_then?: number; months?: number; monthly?: number; fits_in_left_over?: boolean; left_over_monthly?: number; per_day?: number; text: string }[];
  partial_view: boolean;
  action_effect?: { line: string; [key: string]: unknown } | null;
}

export interface SlipsData {
  days: number;
  under: number;
  count: number;
  total: number;
  per_year: number;
  per_month: number;
  average: number;
  share_of_everyday: number;
  top_kinds: { kind: string; label: string; total: number; count: number }[];
  top_places: { merchant: string; total: number; count: number }[];
  window_label?: string;
  headline?: string;
}

export interface CalculateData {
  expression: string;
  shown: string;
  result: number;
  unit: string;
  result_text: string;
  label?: string | null;
  inputs: { name: string; label: string; value: number; unit: string }[];
  text: string;
}

export type CardType =
  | "safe"
  | "forecast"
  | "baskets"
  | "stat"
  | "breakdown"
  | "trend"
  | "whatif"
  | "peers"
  | "profile"
  | "save"
  | "notices"
  | "track"
  | "lesson"
  | "afford"
  | "slips"
  | "calculate";

export interface Card<T = unknown> {
  id: string;
  type: CardType | string;
  title: string;
  subtitle?: string | null;
  data: T;
  source?: { tool: string; args: Record<string, unknown> } | null;
  note?: string | null;
  pin_id?: string;
}

export interface LessonSummary {
  id: string;
  title: string;
  concept: string;
  minutes: number;
  done: boolean;
  slides: number;
}
export interface Lesson {
  id: string;
  title: string;
  concept: string;
  minutes: number;
  slides: LessonSlide[];
  check?: { question: string; options: string[]; correct: number; why: string };
  teach_back?: { prompt: string; rubric?: string[] };
  done: boolean;
}
export interface LessonSortItem {
  id: number;
  merchant: string | null;
  date: string;
  amount: number;
  category: string;
  category_label: string;
  basket: BasketKey;
  basket_label?: string;
  why: string;
}
export interface LessonSortSlide {
  title: string;
  body: string;
  kind: "sort";
  items: LessonSortItem[];
}
export interface LessonSlide {
  title: string;
  body: string;
  basket?: BasketKey;
  card?: Card | null;
  kind?: "sort";
  items?: LessonSortItem[];
}
export interface LessonSortResult {
  lesson: string;
  score: { right: number; total: number; percent: number };
  items: { id: number; picked: BasketKey | null; correct: BasketKey; right: boolean; explanation: string; payment: LessonSortItem }[];
  stored: boolean;
  basket_overrides?: string;
}
export interface TeachBack {
  grade?: "got_it" | "partly" | "not_yet";
  passed: boolean;
  got: string;
  missing: string;
  encouragement: string;
  hint?: string;
  by?: string;
}

export interface Minute {
  beats: { key: string; focus: string; text: string; word_from: number; word_to: number }[];
  text: string;
  audio: string | null;
  words: { w: string; start: number; end: number }[];
}

export interface VoiceSession {
  session: string;
  agent_id: string;
  token?: string;
  signed_url?: string;
  first_message: string;
  voice_id: string;
  language: string;
}

export interface ChatDone {
  grounded: boolean;
  flagged: string[];
  checked: number;
  /** the answer failed the number check twice and was replaced by a sentence saying so */
  withheld?: boolean;
  /** the model gave no answer: offer "try again" */
  error?: boolean;
  followups: string[];
  tools: string[];
  consistency?: { quantity: string; values: number[] }[];
  ms: number;
  figures?: { text: string; label: string; source: string; rounded?: boolean; [key: string]: unknown }[];
}

export type ChatEvent =
  | { event: "session"; data: { session: string; turn?: string } }
  | { event: "status"; data: { tool: string; label: string; first?: boolean } }
  | { event: "card"; data: { card: Card } }
  | { event: "effect"; data: { type: string; lesson?: string; changed?: unknown } }
  | { event: "text"; data: { text: string } }
  | { event: "done"; data: ChatDone }
  | { event: "error"; data: { message: string; detail?: string } };

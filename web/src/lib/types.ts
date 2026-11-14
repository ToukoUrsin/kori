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
  amount: number;
  per_day: number;
  this_week: number;
  week_days: number;
  days_to_payday: number;
  next_payday: string;
  status: Status;
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
}
export interface ForecastData {
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
  safe: { amount: number; per_day: number; days_to_payday: number; status: Status; usual_per_day: number };
  save: SaveData;
  balance: number;
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
}

export interface LessonCardData {
  id: string;
  concept: string;
  minutes: number;
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
  | "lesson";

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
  slides: { title: string; body: string; basket?: BasketKey; card?: Card | null }[];
  check?: { question: string; options: string[]; correct: number; why: string };
  teach_back?: { prompt: string; rubric?: string[] };
  done: boolean;
}
export interface TeachBack {
  passed: boolean;
  got: string;
  missing: string;
  encouragement: string;
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
  ms: number;
}

export type ChatEvent =
  | { event: "session"; data: { session: string; turn?: string } }
  | { event: "status"; data: { tool: string; label: string; first?: boolean } }
  | { event: "card"; data: { card: Card } }
  | { event: "effect"; data: { type: string; lesson?: string; changed?: unknown } }
  | { event: "text"; data: { text: string } }
  | { event: "done"; data: ChatDone }
  | { event: "error"; data: { message: string; detail?: string } };

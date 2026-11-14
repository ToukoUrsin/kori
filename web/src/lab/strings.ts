export type LabLang = "en" | "fi";

type Strings = {
  name: string;
  tagline: string;
  home: string;
  language: string;
  menu: string;
  reset: string;
  emptyTitle: string;
  emptyIntro: string;
  placeholder: string;
  send: string;
  voice: string;
  thinking: string;
  thinkingShort: string;
  ask: string;
  work: string;
  working: string;
  sandbox: (rows: number) => string;
  writing: (lines: number) => string;
  done: string;
  underHood: string;
  isolation: string;
  isolationText: string;
  sources: string;
  check: (figures: number, runs: number) => string;
  warning: (figures: number) => string;
  openWork: string;
  close: string;
  noWork: string;
  noSources: string;
  voiceUnavailable: string;
  tryAgain: string;
  starter: string[];
};

export const strings: Record<LabLang, Strings> = {
  en: {
    name: "Kori",
    tagline: "Your money, made clear.",
    home: "Home",
    language: "Language",
    menu: "Open menu",
    reset: "New conversation",
    emptyTitle: "What do you want to know about your money?",
    emptyIntro: "Ask anything about your spending, plans or next move.",
    placeholder: "Ask Kori anything…",
    send: "Send",
    voice: "Talk to Kori",
    thinking: "Kori is working…",
    thinkingShort: "Thinking",
    ask: "Ask anything",
    work: "Show the work",
    working: "Working",
    sandbox: (rows) => `Private sandbox · ${rows.toLocaleString("en-GB")} of your payments · no network`,
    writing: (lines) => `writing code · ${lines} line${lines === 1 ? "" : "s"}`,
    done: "Done",
    underHood: "Under the hood",
    isolation: "Private by design",
    isolationText: "One customer’s data, an isolated sandbox, a small set of doors, and a locked frame. No network inside the answer.",
    sources: "Sources",
    check: (figures, runs) => `${figures} figure${figures === 1 ? "" : "s"}, all from ${runs === 1 ? "one run" : `${runs} runs`} of code on your own data`,
    warning: (figures) => `${figures} figure${figures === 1 ? "" : "s"} here could not be checked against your data`,
    openWork: "Open work",
    close: "Close",
    noWork: "No work to show yet.",
    noSources: "No external sources for this answer.",
    voiceUnavailable: "Voice is available from the main coach. Keep typing here for now.",
    tryAgain: "Try again",
    starter: [
      "Where does my money go on weekends?",
      "Can my grocery shopping be cheaper?",
      "I need a new laptop. What can I afford?",
      "What if I save €150 a month for ten years?",
      "Show me my year",
    ],
  },
  fi: {
    name: "Kori",
    tagline: "Rahasi, selkeästi.",
    home: "Koti",
    language: "Kieli",
    menu: "Avaa valikko",
    reset: "Uusi keskustelu",
    emptyTitle: "Mitä haluat tietää rahoistasi?",
    emptyIntro: "Kysy menoistasi, suunnitelmistasi tai seuraavasta askeleesta.",
    placeholder: "Kysy Korilta mitä vain…",
    send: "Lähetä",
    voice: "Puhu Korille",
    thinking: "Kori työskentelee…",
    thinkingShort: "Mietin",
    ask: "Kysy mitä vain",
    work: "Näytä työ",
    working: "Työn alla",
    sandbox: (rows) => `Oma hiekkalaatikko · ${rows.toLocaleString("fi-FI")} maksuasi · ei verkkoyhteyttä`,
    writing: (lines) => `kirjoittaa koodia · ${lines} ${lines === 1 ? "rivi" : "riviä"}`,
    done: "Valmis",
    underHood: "Konepellin alla",
    isolation: "Yksityisyys ensin",
    isolationText: "Yhden asiakkaan tiedot, eristetty hiekkalaatikko, rajatut ovet ja lukittu näkymä. Vastauksen sisällä ei ole verkkoyhteyttä.",
    sources: "Lähteet",
    check: (figures, runs) => `${figures} lukua, kaikki ${runs === 1 ? "yhdestä koodiajosta" : `${runs} koodiajosta`} omilla tiedoillasi`,
    warning: (figures) => figures === 1 ? "Yhtä lukua ei voitu tarkistaa tiedoistasi" : `${figures} lukua ei voitu tarkistaa tiedoistasi`,
    openWork: "Avaa työ",
    close: "Sulje",
    noWork: "Työtä ei ole vielä näytettäväksi.",
    noSources: "Tässä vastauksessa ei ole ulkoisia lähteitä.",
    voiceUnavailable: "Ääni löytyy päävalmentajasta. Jatka toistaiseksi kirjoittamalla.",
    tryAgain: "Yritä uudelleen",
    starter: [
      "Mihin rahani menevät viikonloppuisin?",
      "Voisinko käyttää ruokaostoksiin vähemmän?",
      "Tarvitsen uuden läppärin. Mihin minulla on varaa?",
      "Mitä jos säästän 150 € kuussa kymmenen vuoden ajan?",
      "Näytä vuoteni",
    ],
  },
};

export type LabStrings = Strings;

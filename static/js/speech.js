(() => {
  const Speech = {
    preferredLangs: ["ca-ES", "ca_ES", "ca"],

    pickVoice() {
      if (!window.speechSynthesis) return null;
      const voices = window.speechSynthesis.getVoices() || [];
      for (const code of Speech.preferredLangs) {
        const hit = voices.find((voice) =>
          String(voice.lang || "").toLowerCase().startsWith(code.toLowerCase().slice(0, 2))
        );
        if (hit) return hit;
      }
      return voices[0] || null;
    },

    speak(text, opts = {}) {
      if (!window.speechSynthesis || !text) {
        return Promise.reject(new Error("Speech synthesis unavailable"));
      }
      window.speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(String(text));
      utter.lang = opts.lang || "ca-ES";
      utter.rate = opts.rate != null ? opts.rate : 0.9;
      const voice = Speech.pickVoice();
      if (voice) utter.voice = voice;
      return new Promise((resolve, reject) => {
        utter.onend = () => resolve();
        utter.onerror = () => reject(new Error("Speech failed"));
        window.speechSynthesis.speak(utter);
      });
    },

    recognitionAvailable() {
      const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
      return Boolean(Ctor);
    },

    listenOnce(opts = {}) {
      const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!Ctor) {
        return Promise.reject(new Error("Speech recognition unavailable"));
      }
      const recog = new Ctor();
      recog.lang = opts.lang || "ca-ES";
      recog.interimResults = false;
      recog.maxAlternatives = 1;
      return new Promise((resolve, reject) => {
        recog.onresult = (event) => {
          const transcript = event.results?.[0]?.[0]?.transcript || "";
          resolve(transcript);
        };
        recog.onerror = () => reject(new Error("Recognition failed"));
        recog.start();
      });
    },
  };

  window.LaQueta = window.LaQueta || {};
  window.LaQueta.Speech = Speech;

  if (window.speechSynthesis) {
    window.speechSynthesis.onvoiceschanged = () => {
      Speech.pickVoice();
    };
  }
})();

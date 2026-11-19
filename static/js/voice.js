/* Voice layer: speech recognition + speech synthesis. It never talks to the
   backend; app.js decides what to do with recognised text. */
(function () {
  'use strict';
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const handlers = {};
  const emit = (name, ...args) => handlers[name] && handlers[name](...args);

  const ERRORS = {
    'not-allowed': 'Microphone access was denied. Allow the microphone in your browser address bar, then try again.',
    'service-not-allowed': 'Speech recognition is blocked in this browser. Allow the microphone and try again.',
    'no-speech': 'I did not hear anything. Press the mic and try again.',
    'audio-capture': 'No microphone was found. Connect one and try again.',
    'network': 'Speech recognition needs an internet connection in this browser. Check your connection or type the command.',
    'language-not-supported': 'This browser does not support the selected speech language.',
    'aborted': 'Listening stopped.',
  };

  const Voice = {
    supported: !!SR,
    listening: false,
    rec: null,
    on(name, fn) { handlers[name] = fn; },

    start(lang) {
      if (!SR) { emit('error', 'unsupported', 'Speech recognition is not supported in this browser. Use Chrome or Edge, or type your command.'); return; }
      if (Voice.listening) return;
      const rec = new SR();
      let finalText = '';
      rec.lang = lang;
      rec.interimResults = true;
      rec.continuous = false;
      rec.maxAlternatives = 1;
      rec.onstart = () => { Voice.listening = true; emit('start'); };
      rec.onresult = (e) => {
        let interim = '';
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const t = e.results[i][0].transcript;
          if (e.results[i].isFinal) finalText += t; else interim += t;
        }
        emit('interim', finalText || interim);
      };
      rec.onerror = (e) => emit('error', e.error, ERRORS[e.error] || ('Speech recognition error: ' + e.error));
      rec.onend = () => { Voice.listening = false; emit('end', finalText.trim()); };
      Voice.rec = rec;
      try { rec.start(); } catch (err) { emit('error', 'start-failed', 'Could not start the microphone. Try again.'); }
    },

    stop() { if (Voice.rec && Voice.listening) Voice.rec.stop(); },

    voices() { return 'speechSynthesis' in window ? window.speechSynthesis.getVoices() : []; },

    pickVoice(lang, name) {
      const all = Voice.voices();
      if (name) { const byName = all.find((v) => v.name === name); if (byName) return byName; }
      const base = lang.split('-')[0].toLowerCase();
      return all.find((v) => v.lang.toLowerCase().replace('_', '-') === lang.toLowerCase()) ||
             all.find((v) => v.lang.toLowerCase().startsWith(base)) || null;
    },

    hasVoiceFor(lang) { return !!Voice.pickVoice(lang, ''); },

    /* Returns true if speech started. Bengali is only spoken when a Bengali voice exists. */
    speak(text, lang, voiceName, onEnd) {
      if (!('speechSynthesis' in window)) return false;
      const voice = Voice.pickVoice(lang, voiceName);
      if (!voice && lang.startsWith('bn')) return false;
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      if (voice) { u.voice = voice; u.lang = voice.lang; } else { u.lang = lang; }
      u.onend = u.onerror = () => onEnd && onEnd();
      window.speechSynthesis.speak(u);
      return true;
    },
  };
  window.JarvisVoice = Voice;
})();

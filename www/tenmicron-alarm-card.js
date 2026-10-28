/* 10Micron Alarm Card v0.7.0 - optional, local browser audio only.
   No commands are sent to the mount or Home Assistant. */
(() => {
  "use strict";
  const TEXT = {
    cs: {
      title: "10Micron – alarm sledování", clear: "Bez alarmu",
      alarm: "ALARM: neočekávané zastavení sledování",
      unavailable: "Stav montáže není dostupný", missing: "Entita nenalezena",
      enabled: "Zvuk povolen", disabled: "Zvuk vypnut", silenced: "Aktivní alarm umlčen",
      arm: "Povolit zvuk", disarm: "Vypnout zvuk", silence: "Umlčet",
      test: "Test 1 s", error: "Přehrávání zablokováno prohlížečem.",
      note: "Prohlížeč musí zůstat otevřený. Není to bezpečnostní interlock."
    },
    en: {
      title: "10Micron – tracking alarm", clear: "No tracking alarm",
      alarm: "ALARM: unexpected tracking stop",
      unavailable: "Mount status unavailable", missing: "Entity not found",
      enabled: "Sound enabled", disabled: "Sound disabled", silenced: "Active alarm silenced",
      arm: "Enable sound", disarm: "Disable sound", silence: "Silence",
      test: "Test 1 s", error: "Browser blocked audio playback.",
      note: "Keep the browser open. Not an independent safety interlock."
    }
  };
  class TenMicronAlarmCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._config = null;
      this._hass = null;
      this._previous = null;
      this._armed = false;
      this._muted = false;
      this._error = false;
      this._context = null;
      this._osc = null;
      this._gain = null;
      this._interval = null;
      this._testTimer = null;
      this._audioGeneration = 0;
      this._built = false;
    }
    setConfig(config) {
      if (!config || typeof config.entity !== "string" || !config.entity.startsWith("binary_sensor.")) {
        throw new Error("10Micron Alarm Card: configure entity: binary_sensor.xxx");
      }
      this._stop();
      this._config = { ...config };
      this._previous = null;
      this._armed = false;
      this._muted = false;
      this._render();
    }
    static getStubConfig(hass) {
      const found = Object.keys(hass?.states || {}).find(id =>
        id.startsWith("binary_sensor.") && id.includes("unexpected_tracking_stop"));
      return { entity: found || "binary_sensor.10micron_mount_unexpected_tracking_stop" };
    }
    getCardSize() { return 2; }
    connectedCallback() { this._render(); }
    disconnectedCallback() {
      this._stop();
      this._armed = false;
      if (this._context) {
        const context = this._context;
        this._context = null;
        void context.close().catch(() => {});
      }
    }
    set hass(hass) {
      this._hass = hass;
      const state = this._state();
      const previous = this._previous;
      this._previous = state;
      if (state !== "on") {
        this._muted = false;
        this._stop();
      } else if (previous === "off" && this._armed && !this._muted) {
        // Never ring for a historical 'on' state after dashboard reload.
        void this._tone(false);
      }
      this._update();
    }
    _state() {
      const entity = this._hass?.states?.[this._config?.entity];
      return entity ? entity.state : (this._hass ? "missing" : "unknown");
    }
    _labels() {
      const lang = this._config?.language || this._hass?.language || "en";
      return TEXT[String(lang).toLowerCase().startsWith("cs") ? "cs" : "en"];
    }
    _render() {
      if (!this._config || !this.isConnected) return;
      if (!this._built) {
        this.shadowRoot.innerHTML = `
          <style>
            ha-card { padding: 16px; color: var(--primary-text-color); }
            header { display:flex; justify-content:space-between; align-items:center; gap:10px; font-weight:650; }
            .sound { font-size:.8rem; opacity:.8; }
            .state { margin-top:12px; padding:10px; border-radius:8px; background:var(--secondary-background-color, #ddd); }
            .state.active { border:1px solid var(--error-color,#c62828); background:color-mix(in srgb,var(--error-color,#c62828) 13%,transparent); }
            .state.unknown { border:1px solid var(--warning-color,#e9a300); }
            .controls { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
            button { cursor:pointer; font:inherit; border:1px solid var(--divider-color,#999); background:transparent; color:var(--primary-text-color); border-radius:8px; padding:9px 12px; }
            button:first-child { background:var(--primary-color,#008ec2); color:#fff; border-color:transparent; }
            button:disabled { opacity:.35; cursor:default; }
            small { display:block; margin-top:10px; opacity:.75; }
            .error { color:var(--error-color,#c62828); }
          </style>
          <ha-card>
            <header><span id="title"></span><span id="sound" class="sound"></span></header>
            <div id="state" class="state" aria-live="polite"></div>
            <div class="controls">
              <button id="arm"></button><button id="silence"></button><button id="test"></button>
            </div>
            <small id="error" class="error" hidden></small>
            <small id="note"></small>
          </ha-card>`;
        this.shadowRoot.getElementById("arm").addEventListener("click", () => { void this._toggle(); });
        this.shadowRoot.getElementById("silence").addEventListener("click", () => {
          this._muted = true; this._stop(); this._update();
        });
        this.shadowRoot.getElementById("test").addEventListener("click", () => { void this._tone(true); });
        this._built = true;
      }
      this._update();
    }
    _update() {
      if (!this._built) return;
      const s = this._state(), t = this._labels(), active = s === "on";
      const state = this.shadowRoot.getElementById("state");
      this.shadowRoot.getElementById("title").textContent = this._config.title || t.title;
      this.shadowRoot.getElementById("sound").textContent =
        active && this._muted ? t.silenced : (this._armed ? t.enabled : t.disabled);
      state.textContent = active ? t.alarm : s === "off" ? t.clear :
        s === "missing" ? t.missing : t.unavailable;
      state.className = "state" + (active ? " active" : s !== "off" ? " unknown" : "");
      this.shadowRoot.getElementById("arm").textContent = this._armed ? t.disarm : t.arm;
      const silence = this.shadowRoot.getElementById("silence");
      silence.textContent = t.silence;
      silence.disabled = !active || this._muted;
      this.shadowRoot.getElementById("test").textContent = t.test;
      this.shadowRoot.getElementById("note").textContent = t.note;
      const error = this.shadowRoot.getElementById("error");
      error.hidden = !this._error;
      error.textContent = this._error ? t.error : "";
    }
    async _toggle() {
      if (this._armed) {
        this._armed = false; this._stop(); this._update(); return;
      }
      this._armed = true;
      this._muted = false;
      this._error = false;
      try {
        const Audio = window.AudioContext || window.webkitAudioContext;
        if (!Audio) throw Error("Audio unavailable");
        if (!this._context) this._context = new Audio();
        await this._context.resume(); // user gesture required
        if (this._armed && this._state() === "on") await this._tone(false);
      } catch (_) {
        this._error = true;
        this._armed = false;
      }
      this._update();
    }
    async _tone(test) {
      this._stop();
      this._error = false;
      const generation = this._audioGeneration;
      try {
        const Audio = window.AudioContext || window.webkitAudioContext;
        if (!Audio) throw Error("Audio unavailable");
        if (!this._context) this._context = new Audio();
        await this._context.resume();
        if (generation !== this._audioGeneration) return;
        if (!test && (!this._armed || this._muted || this._state() !== "on")) return;
        const osc = this._context.createOscillator();
        const gain = this._context.createGain();
        const requested = Number(this._config.volume ?? 0.08);
        gain.gain.value = Number.isFinite(requested) ? Math.max(0.005, Math.min(requested, 0.2)) : 0.08;
        osc.type = "sine";
        osc.frequency.setValueAtTime(760, this._context.currentTime);
        osc.connect(gain);
        gain.connect(this._context.destination);
        osc.start();
        this._osc = osc;
        this._gain = gain;
        let high = false;
        this._interval = setInterval(() => {
          high = !high;
          if (this._osc && this._context)
            this._osc.frequency.setValueAtTime(high ? 1020 : 760, this._context.currentTime);
        }, 320);
        if (test) this._testTimer = setTimeout(() => this._stop(), 1000);
      } catch (_) {
        this._stop();
        this._error = true;
      }
      this._update();
    }
    _stop() {
      this._audioGeneration += 1;
      if (this._interval !== null) clearInterval(this._interval);
      if (this._testTimer !== null) clearTimeout(this._testTimer);
      this._interval = null;
      this._testTimer = null;
      if (this._osc) { try { this._osc.stop(); this._osc.disconnect(); } catch (_) {} }
      if (this._gain) { try { this._gain.disconnect(); } catch (_) {} }
      this._osc = null;
      this._gain = null;
    }
  }
  if (!customElements.get("tenmicron-alarm-card"))
    customElements.define("tenmicron-alarm-card", TenMicronAlarmCard);
  window.customCards = window.customCards || [];
  if (!window.customCards.some(card => card.type === "tenmicron-alarm-card"))
    window.customCards.push({
      type: "tenmicron-alarm-card", name: "10Micron Alarm",
      description: "Opt-in local browser sound for unexpected tracking stop", preview: false
    });
})();

/*
 * CompitAPP Card — card Lovelace per Home Assistant (nessuna dipendenza esterna)
 * Mostra le tessere (compiti oggi/domani, ultimo voto, media, assenze, bacheca) e,
 * toccandole, apre un popup con il dettaglio. Si installa da sola con CompitAPP 2.0.
 *
 * Esempio:
 *   type: custom:compitapp-card
 *   students:
 *     - name: Giorgia          # uguale al nome scritto nella configurazione di CompitAPP
 *       photo: /local/giorgia.jpg   # facoltativo
 *     - name: Claudia
 *   open_url: /hassio/ingress/compitapp   # facoltativo: bottone "Apri CompitAPP"
 */
const COMPITAPP_CARD_VERSION = '2.0.0';

const _slug = (n) => String(n || '').toLowerCase().replace(/ /g, '_');
const _esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const _data = (d) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(d || '');
  return m ? `${m[3]}/${m[2]}/${m[1]}` : (d || '');
};
const _tipo = { A: 'Assenza', R: 'Ritardo', U: 'Uscita anticipata' };

const TILES = [
  { key: 'compiti_oggi', icon: '📖', label: 'compiti per oggi', title: 'Compiti per oggi' },
  { key: 'compiti_domani', icon: '📅', label: 'compiti per domani', title: 'Compiti per domani' },
  { key: 'ultimo_voto', icon: '⭐', label: 'ultimo voto', title: 'Ultimi voti' },
  { key: 'media_voti', icon: '📈', label: 'media voti', title: 'Media per materia' },
  { key: 'assenze', icon: '🚫', label: 'assenze', title: 'Assenze, ritardi e uscite' },
  { key: 'bacheca', icon: '📌', label: 'avvisi in bacheca', title: 'Bacheca' },
];

class CompitappCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._sel = 0;
    this._popup = null;
  }

  setConfig(config) {
    let students = config.students;
    if (!students && config.student) students = [{ name: config.student, photo: config.photo }];
    if (!students || !students.length) throw new Error('Indica "students" (lista) oppure "student" (nome dello studente)');
    this._config = { ...config, students: students.map((s) => (typeof s === 'string' ? { name: s } : s)) };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    // ridisegna solo se i sensori dello studente sono cambiati
    const st = this._stud();
    const firma = st ? TILES.map((t) => { const e = hass.states[this._eid(st, t.key)]; return e ? e.last_updated : '-'; }).join('|') : '';
    if (firma !== this._firma) { this._firma = firma; this._render(); }
  }

  getCardSize() { return 5; }

  static getStubConfig() { return { students: [{ name: 'Nome studente' }] }; }

  _stud() { return this._config && this._config.students[this._sel]; }
  _slugDi(st) {
    // 1) campo esplicito "entity_slug"; 2) nome identico; 3) unico sensore il cui nome inizia con quello scritto
    if (st.entity_slug) return _slug(st.entity_slug);
    const voluto = _slug(st.name);
    if (!this._hass) return voluto;
    const trovati = Object.keys(this._hass.states)
      .map((k) => /^sensor\.compitapp_(.+)_compiti_oggi$/.exec(k)).filter(Boolean).map((m) => m[1]);
    if (trovati.includes(voluto)) return voluto;
    const simili = trovati.filter((x) => x.startsWith(voluto + '_') || voluto.startsWith(x + '_'));
    return simili.length === 1 ? simili[0] : voluto;
  }
  _eid(st, key) { return `sensor.compitapp_${this._slugDi(st)}_${key}`; }
  _ent(key) { const st = this._stud(); return st && this._hass ? this._hass.states[this._eid(st, key)] : undefined; }

  _render() {
    if (!this._config) return;
    const st = this._stud();
    const aggiornato = (() => {
      const e = this._ent('compiti_oggi');
      if (!e) return '';
      const d = new Date(e.last_updated);
      return `aggiornato alle ${d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })}`;
    })();
    const chips = this._config.students.length > 1
      ? `<div class="chips">${this._config.students.map((s, i) => `<button class="chip ${i === this._sel ? 'on' : ''}" data-i="${i}">${_esc(s.name)}</button>`).join('')}</div>` : '';
    const apri = this._config.open_url ? `<a class="apri" href="${_esc(this._config.open_url)}">📚 Apri CompitAPP</a>` : '';
    const tiles = TILES.map((t) => {
      const e = this._ent(t.key);
      const val = e ? e.state : '–';
      const num = !isNaN(parseFloat(val));
      return `<button class="tile" data-k="${t.key}"><div class="ic">${t.icon}</div><div class="val ${num ? '' : 'nd'}">${_esc(val)}</div><div class="lb">${t.label}</div></button>`;
    }).join('');
    const foto = st.photo ? `<img class="foto" src="${_esc(st.photo)}" alt="">` : `<div class="foto ph">${_esc((st.name || '?')[0].toUpperCase())}</div>`;
    this.shadowRoot.innerHTML = `
      <style>${STILE}</style>
      <ha-card>
        <div class="top">${chips}${apri}</div>
        <div class="head">${foto}<div><div class="nome">${_esc(st.name)}</div><div class="sub">registro DiDUP${aggiornato ? ' · ' + aggiornato : ''}</div></div></div>
        <div class="grid">${tiles}</div>
      </ha-card>`;
    this._mostraPopup();
    this.shadowRoot.querySelectorAll('.chip').forEach((b) => b.addEventListener('click', () => { this._sel = +b.dataset.i; this._chiudiPopup(); this._firma = null; this._render(); }));
    this.shadowRoot.querySelectorAll('.tile').forEach((b) => b.addEventListener('click', () => { this._popup = b.dataset.k; this._mostraPopup(); }));
  }

  _chiudiPopup() {
    this._popup = null;
    if (this._host) { this._host.remove(); this._host = null; }
    if (this._onKey) { document.removeEventListener('keydown', this._onKey); this._onKey = null; }
  }

  // Il popup vive nel body della pagina (non dentro la card): così non viene tagliato
  // dai temi con effetti "vetro" o trasformazioni.
  _mostraPopup() {
    if (this._host) { this._host.remove(); this._host = null; }
    if (!this._popup) return;
    const host = document.createElement('div');
    const cs = getComputedStyle(this);
    const vars = ['--primary-color', '--text-primary-color', '--primary-text-color', '--secondary-text-color',
      '--card-background-color', '--secondary-background-color', '--divider-color']
      .map((v) => `${v}:${cs.getPropertyValue(v)}`).join(';');
    host.attachShadow({ mode: 'open' }).innerHTML = `<style>:host{${vars};font-family:var(--paper-font-body1_-_font-family,inherit)}${STILE}</style>${this._popupHtml()}`;
    document.body.appendChild(host);
    this._host = host;
    const ov = host.shadowRoot.querySelector('.overlay');
    ov.addEventListener('click', (ev) => { if (ev.target === ov) this._chiudiPopup(); });
    host.shadowRoot.querySelector('.close').addEventListener('click', () => this._chiudiPopup());
    this._onKey = (ev) => { if (ev.key === 'Escape') this._chiudiPopup(); };
    document.addEventListener('keydown', this._onKey);
  }

  disconnectedCallback() { this._chiudiPopup(); }

  _popupHtml() {
    const t = TILES.find((x) => x.key === this._popup);
    const e = this._ent(t.key);
    const nome = _esc(this._stud().name);
    let corpo = '';
    const vuoto = (m) => `<div class="vuoto">${m}</div>`;
    const a = (e && e.attributes) || {};
    if (!e) corpo = vuoto('Sensore non trovato. Controlla il nome dello studente nella card.');
    else if (t.key === 'compiti_oggi' || t.key === 'compiti_domani') {
      const l = a.elenco || [];
      corpo = l.length ? l.map((c) => `<div class="riga"><div class="mat">${_esc(c.materia)}</div><div class="txt">${_esc(c.testo)}</div></div>`).join('')
        : vuoto(t.key === 'compiti_oggi' ? 'Nessun compito per oggi 🎉' : 'Nessun compito per domani 🎉');
    } else if (t.key === 'ultimo_voto') {
      const l = a.elenco || [];
      corpo = l.length ? l.map((v) => {
        const n = parseFloat(String(v.voto).replace(',', '.'));
        const cl = isNaN(n) ? '' : (n < 6 ? 'bad' : n < 7 ? 'mid' : 'ok');
        return `<div class="riga voto"><div class="badge ${cl}">${_esc(v.voto)}</div><div><div class="mat">${_esc(v.materia)} <span class="dt">${_data(v.data)}</span></div>${v.descrizione ? `<div class="txt">${_esc(v.descrizione)}</div>` : ''}</div></div>`;
      }).join('') : vuoto('Ancora nessun voto.');
    } else if (t.key === 'media_voti') {
      const l = a.medie || [];
      corpo = (l.length ? `<div class="riga"><div class="mat">Media generale</div><div class="txt"><b>${_esc(e.state)}</b></div></div>` + l.map((m) => {
        const cl = m.media < 6 ? 'bad' : m.media < 7 ? 'mid' : 'ok';
        return `<div class="riga voto"><div class="badge ${cl}">${m.media}</div><div><div class="mat">${_esc(m.materia)}</div><div class="txt">${m.n} ${m.n === 1 ? 'voto' : 'voti'}</div></div></div>`;
      }).join('') : vuoto('Ancora nessun voto.'));
    } else if (t.key === 'assenze') {
      const l = a.elenco || [];
      corpo = l.length ? l.map((x) => `<div class="riga"><div class="mat">${_esc(_tipo[x.tipo] || x.tipo)} <span class="dt">${_data(x.data)}</span></div><div class="txt">${x.giustificata ? '✅ giustificata' : '⚠️ da giustificare'}${x.descrizione ? ' · ' + _esc(x.descrizione) : ''}</div></div>`).join('')
        : vuoto('Nessuna assenza registrata.');
    } else if (t.key === 'bacheca') {
      const l = a.elenco || [];
      corpo = l.length ? l.map((m) => `<div class="riga"><div class="mat">${_esc(m.titolo)} <span class="dt">${_data(m.data)}</span></div>${m.mittente ? `<div class="dt">${_esc(m.mittente)}</div>` : ''}<div class="txt">${_esc(m.testo)}</div></div>`).join('')
        : vuoto('Nessuna comunicazione.');
    }
    return `<div class="overlay"><div class="dialog"><div class="dh"><div><div class="dt1">${t.title}</div><div class="dt2">${nome}</div></div><button class="close" aria-label="Chiudi">✕</button></div><div class="db">${corpo}</div></div></div>`;
  }
}

const STILE = `
:host{display:block}
ha-card{padding:14px}
.top{display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin-bottom:10px}
.chips{display:flex;gap:6px;background:var(--secondary-background-color);padding:4px;border-radius:14px}
.chip{border:0;background:transparent;color:var(--secondary-text-color);padding:7px 14px;border-radius:10px;font:inherit;cursor:pointer}
.chip.on{background:var(--primary-color);color:var(--text-primary-color,#fff)}
.apri{color:var(--primary-text-color);text-decoration:none;background:var(--secondary-background-color);padding:8px 12px;border-radius:12px;font-size:.9em}
.head{display:flex;gap:12px;align-items:center;margin:4px 0 14px}
.foto{width:52px;height:52px;border-radius:50%;object-fit:cover;border:2px solid var(--primary-color)}
.foto.ph{display:flex;align-items:center;justify-content:center;background:var(--secondary-background-color);color:var(--primary-text-color);font-size:1.4em;font-weight:600}
.nome{font-size:1.35em;font-weight:600;color:var(--primary-text-color)}
.sub{font-size:.8em;color:var(--secondary-text-color)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.tile{border:1px solid var(--divider-color);background:var(--card-background-color);border-radius:16px;padding:14px 8px;text-align:center;cursor:pointer;font:inherit;color:var(--primary-text-color);transition:transform .1s,background .15s}
.tile:hover{background:var(--secondary-background-color)}
.tile:active{transform:scale(.97)}
.ic{font-size:1.5em}
.val{font-size:2em;font-weight:700;margin:2px 0;color:var(--primary-color)}
.val.nd{color:var(--secondary-text-color);font-size:1.6em}
.lb{font-size:.8em;color:var(--secondary-text-color)}
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:999;display:flex;align-items:center;justify-content:center;padding:16px}
.dialog{background:var(--card-background-color,#fff);color:var(--primary-text-color);border-radius:18px;max-width:520px;width:100%;max-height:82vh;display:flex;flex-direction:column;box-shadow:0 10px 40px rgba(0,0,0,.4)}
.dh{display:flex;justify-content:space-between;align-items:flex-start;padding:16px 18px 10px;border-bottom:1px solid var(--divider-color)}
.dt1{font-size:1.15em;font-weight:600}.dt2{font-size:.85em;color:var(--secondary-text-color)}
.close{border:0;background:var(--secondary-background-color);color:var(--primary-text-color);width:34px;height:34px;border-radius:50%;cursor:pointer;font-size:1em}
.db{padding:12px 18px 18px;overflow:auto}
.riga{padding:10px 0;border-bottom:1px solid var(--divider-color)}
.riga:last-child{border-bottom:0}
.riga.voto{display:flex;gap:12px;align-items:center}
.mat{font-weight:600}
.txt{margin-top:2px;white-space:pre-wrap;color:var(--primary-text-color);line-height:1.35}
.dt{font-size:.8em;font-weight:400;color:var(--secondary-text-color)}
.badge{min-width:46px;text-align:center;padding:8px 6px;border-radius:12px;font-weight:700;font-size:1.1em;background:var(--secondary-background-color)}
.badge.ok{background:#2e7d3233;color:#43a047}.badge.mid{background:#f9a82533;color:#f9a825}.badge.bad{background:#e5393533;color:#e53935}
.vuoto{padding:24px 0;text-align:center;color:var(--secondary-text-color)}
`;

customElements.define('compitapp-card', CompitappCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: 'compitapp-card', name: 'CompitAPP', description: 'Compiti, voti, assenze e bacheca con popup di dettaglio', preview: false });
console.info(`%c COMPITAPP-CARD %c v${COMPITAPP_CARD_VERSION} `, 'background:#3b82f6;color:#fff', 'background:#222;color:#fff');

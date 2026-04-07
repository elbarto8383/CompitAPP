# 📚 CompitAPP — Home Assistant Add-on

<div align="center">

<img src="compitapp/logo.png" width="128" alt="CompitAPP Logo">

**Compiti, voti e comunicazioni scolastiche via DiDUP/Argo ScuolaNext**
**Notifiche Telegram automatiche — niente più app del registro!**

[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Add--on-41BDF5?logo=home-assistant&logoColor=white)](https://www.home-assistant.io/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![Version](https://img.shields.io/badge/Version-1.0.0-brightgreen.svg)](https://github.com/elbarto8383/CompitAPP)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 💝 Supporta il progetto

CompitAPP è un progetto open source sviluppato nel tempo libero con passione.
Se ti è utile e vuoi supportarne lo sviluppo, considera una donazione!

<div align="center">

[![Donate PayPal](https://img.shields.io/badge/Donate-PayPal-00457C?logo=paypal&logoColor=white&style=for-the-badge)](https://paypal.me/elbarto83)

**[@elbarto83](https://paypal.me/elbarto83)**

*Ogni contributo, anche piccolo, aiuta a mantenere il progetto attivo,*
*coprire i costi di sviluppo e aggiungere nuove funzionalità!*

</div>

## 📋 Cos'è CompitAPP?

**CompitAPP** è un add-on per Home Assistant che si collega automaticamente al registro elettronico **DiDUP / Argo ScuolaNext** e porta tutto il registro scolastico direttamente su Telegram e in una comoda PWA — senza nessun inserimento manuale.

> 💡 **Non dovrai più aprire l'app DiDUP!** CompitAPP controlla il registro ogni 30 minuti e ti notifica automaticamente su Telegram appena il professore inserisce un compito, un voto o una comunicazione.

---

## ✨ Funzionalità complete

### 📱 PWA Web (accessibile da browser e iPhone/Android)

| Tab | Contenuto |
|---|---|
| 🏠 **Oggi** | Compiti di oggi, domani, prossimi giorni + ultimi voti |
| 📅 **Calendario** | Tutti i compiti passati e futuri |
| 📊 **Voti** | Tutti i voti con media per materia |
| 🗓️ **Orario** | Orario settimanale colorato per materia |
| 📢 **Bacheca** | Comunicazioni e circolari della scuola |
| 🏠 **Assenze** | Registro assenze, ritardi e uscite anticipate |
| 📖 **Lezioni** | Argomenti svolti in classe |
| ⚙️ **Config** | Stato connessione, destinatari, impostazioni |

### 🤖 Bot Telegram — comandi disponibili

| Comando | Descrizione |
|---|---|
| `/start` | Benvenuto e ottieni il tuo Chat ID |
| `/chatid` | Mostra il tuo Chat ID |
| `/resoconto` | Riepilogo completo compiti + voti del giorno |
| `/orario` | Orario di oggi |
| `/orario lunedi` | Orario di un giorno specifico |
| `/voti` | Ultimi voti e media per materia |
| `/help` | Lista di tutti i comandi |

### 🔔 Notifiche automatiche Telegram

| Evento | Genitori | Studente |
|---|---|---|
| 📚 Nuovo compito | ✅ immediata | ✅ immediata |
| 🌙 Reminder serale compiti | ✅ | ✅ |
| ⭐ Nuovo voto | ✅ con 🟢🟡🔴 | ❌ privacy |
| 🏠 Assenza/Ritardo | ✅ | ❌ privacy |
| 📢 Comunicazione bacheca | ✅ | ✅ |
| 📋 Promemoria docente | ✅ | ✅ |
| ⚠️ Nota disciplinare | ✅ | ❌ privacy |

### 👨‍👩‍👧 Multi-destinatario intelligente
- **Genitore 1 e 2** — ricevono tutto
- **Studente** — riceve compiti e reminder, **NON voti/assenze/note** (privacy!)
- **Multi-studente** — supporto per più figli nella stessa famiglia

### 🏠 Sensori Home Assistant
Per ogni studente vengono creati automaticamente:
- `sensor.compitapp_<nome>_compiti_oggi`
- `sensor.compitapp_<nome>_compiti_domani`
- `sensor.compitapp_<nome>_ultimo_voto`
- `sensor.compitapp_<nome>_media_voti`
- `sensor.compitapp_<nome>_assenze`
- `sensor.compitapp_<nome>_bacheca`

---

## 🚀 Installazione

### Metodo 1 — Da repository GitHub (consigliato)

1. In Home Assistant vai su **Impostazioni → Add-on → Store**
2. Clicca i **tre puntini** in alto a destra → **Aggiungi repository**
3. Inserisci l'URL: `https://github.com/elbarto8383/CompitAPP`
4. Clicca **Aggiungi**
5. Cerca **CompitAPP** nello store e clicca **Installa**
6. Vai su **Configurazione** e compila i campi
7. Clicca **Avvia**

### Metodo 2 — Installazione locale via Samba

1. Accedi alla cartella `addons` di Home Assistant via Samba (`\\IP-HA\addons`)
2. Crea la cartella `compitapp`
3. Copia tutti i file del repository dentro `compitapp/`
4. In HA vai su **Impostazioni → Add-on** e clicca **Ricarica**
5. Cerca **CompitAPP** e installalo

---

## ⚙️ Configurazione

Dopo l'installazione vai su **Impostazioni → Add-on → CompitAPP → Configurazione**:

```yaml
# Token del bot Telegram (ottienilo da @BotFather)
telegram_token: "123456:ABC-DEF..."

# Destinatari
genitore1_nome: "Mario"           # Nome Genitore 1
genitore1_chat_id: "44413116"     # Chat ID Genitore 1
genitore2_nome: "Lucia"           # Nome Genitore 2 (opzionale)
genitore2_chat_id: ""             # Chat ID Genitore 2 (opzionale)
studente_nome: "Luigi"            # Nome studente
studente_chat_id: ""              # Chat ID studente (opzionale, non riceve voti)

# Impostazioni
soglia_voto_alert: 7              # Alert se voto sotto questa soglia
orario_reminder_sera: "20:00"     # Orario reminder serale compiti
polling_intervallo_minuti: 30     # Frequenza controllo DiDUP (minuti)
anno_scolastico: "2025/2026"      # Anno scolastico corrente

# Studenti (uno o più figli)
studenti:
  - nome: "Luigi Rossi"
    codice_scuola: "SC12345"      # Codice scuola dalla segreteria
    username: "l.rossi"           # Username DiDUP
    password: "la_tua_password"   # Password DiDUP
```

### Come trovare il tuo Chat ID Telegram
1. Cerca il tuo bot su Telegram (quello creato con @BotFather)
2. Invia `/start`
3. Il bot risponderà con il tuo **Chat ID**
4. Copialo nel campo corrispondente

### Come trovare il codice scuola
Il codice scuola si trova nell'app DiDUP nella schermata del profilo (es. `SC26639`).

---

## 🤖 Configurazione Bot Telegram

1. Apri Telegram e cerca **@BotFather**
2. Invia `/newbot` e segui le istruzioni
3. Copia il **token** e incollalo nella configurazione
4. Imposta i comandi con `/setcommands`:

```
start - Benvenuto e ottieni il tuo Chat ID
chatid - Mostra il tuo Chat ID
resoconto - Riepilogo compiti e voti di oggi
orario - Orario di oggi (o /orario lunedi)
voti - Ultimi voti e medie per materia
help - Mostra tutti i comandi
```

---

## 📡 Accesso alla PWA

Dopo l'avvio, la PWA è accessibile a:
- **Rete locale**: `http://IP-HOME-ASSISTANT:5002`
- **Pannello HA**: aggiungi una scheda **Pagina Web** nella dashboard con l'URL sopra

---

## ❓ FAQ

**Il bot non risponde ai comandi**
→ Verifica che l'add-on sia avviato e che il token sia corretto nella configurazione.

**Non vedo i compiti nella PWA**
→ Clicca il pulsante 🔄 Sync in alto a destra. Il primo sync può richiedere qualche secondo.

**Il codice scuola viene convertito in minuscolo**
→ È normale, il sistema lo gestisce correttamente anche in minuscolo.

**Posso usare CompitAPP con più figli?**
→ Sì! Aggiungi più voci nella sezione `studenti` della configurazione.

**Lo studente riceve i voti?**
→ No, se configuri `studente_chat_id` separatamente, lo studente riceve solo compiti e reminder — mai voti, assenze o note disciplinari.

---

## 🛠️ Supporto

Se trovi un bug o hai una richiesta, apri una [Issue su GitHub](https://github.com/elbarto8383/CompitAPP/issues).

---

<div align="center">

Fatto con ❤️ per i genitori italiani

**[⬆ Torna su](#-compitapp--home-assistant-add-on)**

</div>

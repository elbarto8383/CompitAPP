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

[![Donate PayPal](https://img.shields.io/badge/Donate-PayPal-00457C?logo=paypal&logoColor=white&style=for-the-badge)](https://paypal.me/elbarto83)

**[@elbarto83](https://paypal.me/elbarto83)**

*Ogni contributo, anche piccolo, aiuta a mantenere il progetto attivo,*
*coprire i costi di sviluppo e aggiungere nuove funzionalità!*

---

</div>

## 📋 Cos'è CompitAPP?

**CompitAPP** è un add-on per Home Assistant che si collega automaticamente al registro elettronico **DiDUP / Argo ScuolaNext** e porta tutto il registro scolastico direttamente su Telegram e in una comoda PWA — senza nessun inserimento manuale.

> 💡 **Non dovrai più aprire l'app DiDUP!** CompitAPP controlla il registro ogni 30 minuti e ti notifica automaticamente su Telegram appena il professore inserisce un compito, un voto o una comunicazione.

---

## ✨ Funzionalità complete

### 📱 PWA Web — accessibile da browser, iPhone e Android

| Tab | Contenuto |
|---|---|
| 🏠 **Oggi** | Compiti di oggi, domani, prossimi giorni + ultimi voti |
| 📅 **Calendario** | Tutti i compiti passati e futuri con toggle passati/futuri |
| 📊 **Voti** | Tutti i voti con media per materia e barre di progresso |
| 🗓️ **Orario** | Orario settimanale colorato per materia (mobile + desktop) |
| 📢 **Bacheca** | Comunicazioni e circolari della scuola |
| 🏠 **Assenze** | Registro assenze, ritardi e uscite anticipate con statistiche |
| 📖 **Lezioni** | Argomenti svolti in classe negli ultimi 30 giorni |
| ⚙️ **Config** | Stato connessione DiDUP, destinatari Telegram, impostazioni |

### 🤖 Bot Telegram — comandi disponibili

> ✅ I comandi vengono configurati **automaticamente** all'avvio — non serve nessun intervento su @BotFather!

| Comando | Descrizione |
|---|---|
| `/start` | Benvenuto e ottieni il tuo Chat ID |
| `/chatid` | Mostra il tuo Chat ID |
| `/resoconto` | Riepilogo completo compiti + voti del giorno |
| `/orario` | Orario di oggi |
| `/orario lunedi` | Orario di un giorno specifico (lun/mar/mer/gio/ven) |
| `/voti` | Ultimi voti e media per materia con semaforo |
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
- **Genitore 1 e 2** — ricevono tutto: compiti, voti, assenze, comunicazioni
- **Studente** — riceve solo compiti e reminder, **mai voti, assenze o note** (privacy!)
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

## 🔒 Sicurezza e Privacy

### CompitAPP è sicuro al 100% — ecco perché

**📖 Solo lettura**
CompitAPP si connette al registro DiDUP esclusivamente in **modalità lettura**. Non può inserire voti, modificare dati, giustificare assenze o compiere qualsiasi azione sul registro. È tecnicamente impossibile che causi danni ai dati scolastici.

**🏠 Dati solo in casa tua**
Tutti i dati (compiti, voti, assenze) vengono scaricati e salvati **localmente sul tuo Home Assistant**. Non transitano su server esterni, non vengono condivisi con nessuno, non escono dalla tua rete domestica.

**🔐 Accesso protetto da HA Ingress**
La PWA di CompitAPP è accessibile tramite il sistema **Ingress di Home Assistant** — lo stesso meccanismo usato da tutti gli add-on ufficiali (File Editor, Terminal, ecc.). Questo significa:
- ✅ Protetta da HTTPS automaticamente
- ✅ Accessibile solo agli utenti autenticati in HA
- ✅ **Non esposta su nessuna porta pubblica**
- ✅ Funziona in remoto tramite il tunnel sicuro di HA

**👨‍👩‍👧 Privacy in famiglia**
CompitAPP distingue i destinatari Telegram per ruolo:
- **Genitori** — ricevono tutto: compiti, voti, assenze, comunicazioni
- **Studente** — riceve solo compiti e reminder, **mai voti, assenze o note disciplinari**

**🔑 Credenziali al sicuro**
Le credenziali DiDUP sono salvate solo nella configurazione locale di Home Assistant, mai trasmesse a terzi. Il token Telegram è oscurato nell'interfaccia di configurazione.

---

## 🚀 Installazione

### Metodo 1 — Da repository GitHub (consigliato)

1. In Home Assistant vai su **Impostazioni → Add-on → Store**
2. Clicca i **tre puntini** in alto a destra → **Aggiungi repository**
3. Inserisci l'URL: `https://github.com/elbarto8383/CompitAPP`
4. Clicca **Aggiungi**
5. Cerca **CompitAPP** nello store e clicca **Installa**
6. Vai su **Configurazione** e compila i campi
7. Clicca **Salva** → **Avvia**

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
telegram_token: "123456:ABC-DEF..."   # Campo oscurato per sicurezza

# Destinatari — Genitore 1 (obbligatorio)
genitore1_nome: "Mario"
genitore1_chat_id: ""

# Destinatari — Genitore 2 (opzionale)
genitore2_nome: "Lucia"
genitore2_chat_id: ""

# Destinatari — Studente (opzionale, NON riceve voti/assenze/note)
studente_nome: "Luigi"
studente_chat_id: ""

# Impostazioni notifiche
soglia_voto_alert: 7              # Alert se voto sotto questa soglia
orario_reminder_sera: "20:00"     # Orario reminder serale compiti
polling_intervallo_minuti: 30     # Frequenza controllo DiDUP (minuti)
anno_scolastico: "2025/2026"

# Studenti (uno o più figli)
studenti:
  - nome: "Luigi Rossi"
    codice_scuola: "SC12345"      # Codice scuola (dalla segreteria o dall'app DiDUP)
    username: "l.rossi"           # Username DiDUP
    password: "la_tua_password"
```

### Come trovare il tuo Chat ID Telegram
1. Cerca il tuo bot su Telegram
2. Invia `/start`
3. Il bot risponderà con il tuo **Chat ID**
4. Copialo nel campo corrispondente

### Come trovare il codice scuola
Il codice scuola si trova nell'app DiDUP nella schermata del profilo (es. `SC12345`).

---

## 📡 Accesso alla PWA

Dopo l'avvio, CompitAPP appare automaticamente nella **barra laterale di Home Assistant** grazie al sistema Ingress — nessuna configurazione aggiuntiva necessaria!

Per aggiungerlo come scheda nella dashboard:
- **Aggiungi scheda → Pagina Web**
- URL: `/api/hassio_ingress/4016d9e7_compitapp/`

> ⚠️ Non usare `http://IP:5002` come URL nella dashboard — non funziona dall'esterno e causa errori di mixed content con HTTPS.

---

## ❓ FAQ

**Il bot non risponde ai comandi**
→ Verifica che l'add-on sia avviato e che il token sia corretto. Prova a riavviare l'add-on.

**Non vedo i compiti nella PWA**
→ Clicca il pulsante 🔄 Sync in alto a destra. Il primo sync può richiedere qualche secondo.

**Il codice scuola viene convertito in minuscolo**
→ È normale, il sistema lo gestisce correttamente anche in minuscolo.

**Posso usare CompitAPP con più figli?**
→ Sì! Aggiungi più voci nella sezione `studenti` della configurazione. Ogni figlio avrà i propri sensori HA e le proprie notifiche.

**Lo studente riceve i voti?**
→ No. Se configuri `studente_chat_id`, lo studente riceve solo compiti e reminder — mai voti, assenze o note disciplinari.

**La PWA non si apre dall'esterno**
→ Usa la barra laterale di HA o il pulsante "Apri interfaccia utente Web" dalla pagina dell'add-on. CompitAPP usa l'Ingress di HA che funziona anche da remoto tramite HTTPS.

**Non ricevo le notifiche automatiche**
→ Verifica che i `chat_id` siano corretti nelle opzioni. Puoi testare manualmente scrivendo `/resoconto` al bot.

---

## 🛠️ Supporto

Se trovi un bug o hai una richiesta, apri una [Issue su GitHub](https://github.com/elbarto8383/CompitAPP/issues).

---

<div align="center">

Fatto con ❤️ per i genitori italiani

by [@elbarto8383](https://github.com/elbarto8383)

**[⬆ Torna su](#-compitapp--home-assistant-add-on)**

</div>

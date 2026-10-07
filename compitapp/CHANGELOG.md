# Changelog

## 1.0.14

- Più figli con lo stesso account DiDUP: nuovo campo facoltativo `alunno` dentro ogni studente (1 = primo figlio, 2 = secondo, come nell'app DiDUP). Prima i dati dei figli si mescolavano e su Telegram arrivavano gli stessi compiti. Nei registri l'app avvisa se l'account contiene più alunni e il campo non è compilato.
- I registri non stampano più le password degli studenti all'avvio.

## 1.0.13

- Corretto il problema per cui voti, assenze e media risultavano sempre a zero / N/D: l'app leggeva i nomi dei campi di una vecchia versione di Argo. Ora legge `voti` e `appello` (assenze, ritardi, uscite) e, per sicurezza, anche i vecchi nomi.
- Le annotazioni dei docenti senza voto (valore 0) non vengono più contate come voti: non abbassano più la media e non fanno scattare avvisi di voto basso. Quelle già salvate vengono ripulite in automatico.
- Le comunicazioni in bacheca senza titolo non vengono più scartate (come titolo si usa la categoria).
- Grazie a chi ha segnalato il problema e passato i nomi dei campi reali.

## 1.0.12

- Nei registri dell'app compare sempre quanti voti, assenze e comunicazioni arrivano da Argo e per quanti giorni (es. "Voti Nome: 5 ricevuti da Argo (ultimi 7 giorni)"), così si capisce subito se i dati arrivano o no.

## 1.0.11

- **Voti, assenze e comunicazioni di bacheca ora si caricano anche se precedenti all'installazione**: la richiesta ad Argo restituiva solo le novità di "oggi", quindi un voto o un'assenza compariva soltanto se inserito dopo l'avvio dell'app. Per questo molti vedevano sempre "N/D" e "0" nei sensori. Ora al primo avvio viene letto tutto l'anno scolastico e poi gli ultimi 7 giorni.
- **Nessuna notifica per lo storico**: il primo caricamento è silenzioso, quindi Telegram non viene riempito di voti e assenze vecchi. Le notifiche partono solo per le novità successive.
- **Sensori di Home Assistant aggiornati a fine sincronizzazione** (prima venivano aggiornati solo dopo i compiti, e non se quel giorno non c'erano compiti): ultimo voto, media, assenze e bacheca ora riflettono i dati più recenti.
- Il sensore "avvisi in bacheca" conta le comunicazioni degli ultimi 30 giorni.
- Letture da Argo più leggere: i dati ricevuti vengono riutilizzati per qualche secondo durante lo stesso ciclo.
- Nuova tabella `meta` nel database, creata in automatico (nessuna azione richiesta).

## 1.0.10

- Il recupero dello storico del registro parte subito (al primo controllo dopo l'avvio) invece di attendere fino a un'ora, e si ripete a ogni controllo finché l'archivio delle lezioni non ha almeno 10 giorni.
- Nei registri dell'app compare quanti giorni di lezioni restituisce Argo quando si chiede lo storico.

## 1.0.9

- **Orario completo fin dal primo avvio (tentativo)**: la lettura del registro chiedeva ad Argo solo le novità di oggi, quindi arrivava un solo giorno alla volta. Ora CompitAPP chiede anche i giorni passati (fino a 60 giorni, la prima volta) e ricostruisce subito l'orario completo. Se Argo non risponde in questo modo, usa il metodo precedente, che accumula un giorno alla volta.
- Dopo il primo recupero basta controllare gli ultimi giorni, così le richieste restano leggere.
- Nei registri dell'app compare quanti giorni di lezioni ha ricevuto da Argo.

## 1.0.8

- **Orario che si completa giorno dopo giorno**: Argo restituisce soltanto le lezioni degli ultimi giorni, quindi prima l'orario poteva mostrare un solo giorno e, aggiornandosi, perdere i precedenti. Ora CompitAPP conserva le lezioni viste e ricostruisce l'orario da tutto lo storico: ogni giorno di scuola ne aggiunge uno, e dopo circa una settimana è completo.
- Aggiornamento dell'orario più frequente (ogni ora invece che ogni 6) per non perdere le lezioni del giorno.
- Nei registri dell'app compare un riepilogo per capire cosa restituisce Argo (quante lezioni e di quali giorni).
- Nuova tabella `lezioni_registro` nel database, creata in automatico all'avvio (nessuna azione richiesta).

## 1.0.7

- **Descrizioni chiare nella configurazione**: ogni campo ora ha un nome comprensibile e una spiegazione con esempi (in particolare le frasi personalizzate del riepilogo serale, `reminder_testo_vuoto` e `reminder_testo_chiusura`).
- **Corretta l'opzione `reminder_mostra_orario`** (e `reminder_modalita`): tornava spenta dopo il riavvio perché era dichiarata facoltativa pur avendo un valore predefinito. Ora il valore scelto viene salvato. Se l'avevi attivata prima dell'aggiornamento, controllala e riattivala.
- Allineato lo stesso difetto anche al `chat_id` dello studente.

## 1.0.6

- **Chat ID Telegram per ogni studente**: nella lista `studenti` ogni figlio ha ora il campo facoltativo `chat_id`. Ogni ragazzo riceve solo le proprie notifiche (compiti, riepilogo serale, bacheca, promemoria), mai voti, assenze o note.
- **Corretto l'invio allo studente**: prima il chat ID dello studente veniva mostrato in configurazione ma i messaggi partivano solo verso i genitori. Ora arrivano anche allo studente, come descritto nel README.
- Il vecchio campo `studente_chat_id` continua a funzionare, ma solo se è configurato **un solo** studente.
- La pagina Configurazione mostra nome e chat ID dello studente selezionato.

## 1.0.5

- **Voti con la virgola** (es. 7,5): ora il colore (verde/giallo/rosso) viene calcolato correttamente, prima venivano sempre segnati come insufficienti.
- **Pagina Configurazione**: le "Statistiche database" ora mostrano i dati dello studente selezionato (prima erano sempre a zero).
- Aggiunti gli screenshot nel README.

## 1.0.4

- **Corretto il cambio tra più figli**: con due o più studenti configurati, toccare il nome del figlio faceva uscire dalla PWA e riapriva Home Assistant. Ora il cambio resta dentro CompitAPP e mantiene la pagina in cui ti trovi.
- I comandi Telegram `/resoconto` e `/voti` ora sono separati per studente (un messaggio per ciascun figlio, con il nome giusto).
- Rimosso un nome di studente scritto nel codice nel comando `/voti`.

## 1.0.3

- **Riepilogo serale intelligente**: in modalità `auto` (predefinita) il messaggio "Nessun compito per domani" non viene più inviato quando domani non è giorno di scuola. I giorni di scuola sono riconosciuti dalle lezioni del registro, quindi chi ha lezione il sabato continua a riceverlo; se ci sono compiti, il riepilogo parte sempre.
- **Riepilogo personalizzabile** dalla configurazione: `reminder_modalita` (auto / sempre / solo_con_compiti), `reminder_mostra_orario` (aggiunge l'orario di domani), `reminder_testo_vuoto` e `reminder_testo_chiusura` (frasi tue).
- **Sabato nell'orario**: se lo studente ha lezioni il sabato, compare nella pagina Orario e nel comando `/orario sab`.
- Le nuove opzioni sono facoltative: se non le tocchi, tutto funziona come prima (con il riepilogo `auto`).

## 1.0.2

- **Orario scolastico dinamico**: Argo non espone l'orario nella dashboard, quindi CompitAPP lo ricostruisce dalle lezioni del registro (ultime 3 settimane) e lo aggiorna da solo, anche a inizio anno scolastico.
- Pagina **Orario** e comando Telegram `/orario` leggono i dati dal database invece di un orario scritto nel codice.
- Anno scolastico e nome dello studente calcolati in automatico: niente più "2025/2026" e "Classe 3B" fissi.
- Gestione corretta di righe doppie, giornate corte (es. primi giorni di scuola) e supplenze isolate.
- Nuova tabella `orario` nel database (creata in automatico all'avvio, nessuna azione richiesta).
- Il campo `anno_scolastico` della configurazione non viene più usato.

## 1.0.1

- Versione precedente.

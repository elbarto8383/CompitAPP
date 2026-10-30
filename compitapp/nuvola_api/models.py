"""
Modelli di dati (dataclass) per la deserializzazione tipizzata delle risposte Nuvola.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class Alunno:
    """Rappresenta uno studente associato all'account."""
    id: int
    nome: str
    cognome: str
    nome_completo: str
    attivo: bool
    classe: str
    scuola: str
    codice_fiscale: Optional[str] = None
    data_nascita: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Alunno":
        return cls(
            id=data.get("id", 0),
            nome=data.get("nome", ""),
            cognome=data.get("cognome", ""),
            nome_completo=data.get("nomeCompleto", f"{data.get('nome', '')} {data.get('cognome', '')}".strip()),
            attivo=data.get("attivoInAnnoScolasticoCorrente", True),
            classe=data.get("classe", ""),
            scuola=data.get("scuola", ""),
            codice_fiscale=data.get("codiceFiscale"),
            data_nascita=data.get("dataNascita"),
            raw=data
        )


@dataclass
class Compito:
    """Rappresenta un compito per casa assegnato."""
    docente: str
    materia: str
    data_assegnazione: Optional[str]
    data_consegna: Optional[str]
    descrizione: str
    classe: str
    classe_id: Optional[int] = None
    nome_argomento: Optional[str] = None
    allegati: List[Any] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Compito":
        desc_raw = data.get("descrizioneCompito", "")
        if isinstance(desc_raw, list):
            descrizione = "\n".join(str(item) for item in desc_raw)
        else:
            descrizione = str(desc_raw or "")

        return cls(
            docente=data.get("docente", ""),
            materia=data.get("materia", ""),
            data_assegnazione=data.get("dataAssegnazione"),
            data_consegna=data.get("dataConsegna"),
            descrizione=descrizione,
            classe=data.get("classe", ""),
            classe_id=data.get("classeId"),
            nome_argomento=data.get("nomeArgomento"),
            allegati=data.get("allegati", []),
            raw=data
        )


@dataclass
class ArgomentoLezione:
    """Dettaglio di un singolo argomento di lezione svolto durante l'ora."""
    id: int
    materia: str
    docente: str
    tipo: str
    nome_argomento: str
    annotazioni: Optional[str] = None
    descrizione_estesa: Optional[str] = None
    compresenza: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArgomentoLezione":
        return cls(
            id=data.get("id", 0),
            materia=data.get("materia", ""),
            docente=data.get("docente", ""),
            tipo=data.get("tipo", ""),
            nome_argomento=data.get("nomeArgomento", ""),
            annotazioni=data.get("annotazioni"),
            descrizione_estesa=data.get("descrizioneEstesa"),
            compresenza=data.get("compresenza"),
            raw=data
        )


@dataclass
class OraLezione:
    """Rappresenta un blocco orario scolastico con i relativi argomenti."""
    numero_ora: int
    inizio_ora: str
    fine_ora: str
    giorno: str
    argomenti: List[ArgomentoLezione] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OraLezione":
        args = [
            ArgomentoLezione.from_dict(a)
            for a in data.get("argomenti", [])
        ]
        return cls(
            numero_ora=data.get("numeroOra", 0),
            inizio_ora=data.get("inizioOra", ""),
            fine_ora=data.get("fineOra", ""),
            giorno=data.get("giorno", ""),
            argomenti=args,
            raw=data
        )


@dataclass
class EventoClasse:
    """Rappresenta una verifica programmata, uscita didattica o avviso di classe."""
    id: int
    tipo: str
    nome: str
    descrizione: str
    docente: str
    data_inizio: str
    ora_inizio: Optional[str] = None
    data_fine: Optional[str] = None
    ora_fine: Optional[str] = None
    visto: bool = False
    adesione_richiesta: bool = False
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventoClasse":
        return cls(
            id=data.get("id", 0),
            tipo=data.get("tipo", ""),
            nome=data.get("nome", ""),
            descrizione=data.get("descrizione", ""),
            docente=data.get("docente", ""),
            data_inizio=data.get("dataInizio", ""),
            ora_inizio=data.get("oraInizio"),
            data_fine=data.get("dataFine"),
            ora_fine=data.get("oraFine"),
            visto=data.get("visto", False),
            adesione_richiesta=data.get("adesioneRichiesta", False),
            raw=data
        )


@dataclass
class FrazioneTemporale:
    """Periodo dell'anno scolastico (es. 1° Quadrimestre, 2° Quadrimestre, Intero Anno)."""
    id: int
    nome: str
    corrente: bool

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FrazioneTemporale":
        return cls(
            id=data.get("id", 0),
            nome=data.get("nome", ""),
            corrente=data.get("corrente", False)
        )


@dataclass
class VotoSintetico:
    """Valutazione sintetica all'interno del riepilogo materia."""
    data: str
    valutazione: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VotoSintetico":
        return cls(
            data=data.get("data", ""),
            valutazione=data.get("valutazione", "")
        )


@dataclass
class MateriaVoti:
    """Riepilogo dei voti e della media per una specifica materia."""
    id: int
    materia: str
    conteggio_voti: int
    media: Optional[str]
    voti: List[VotoSintetico] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def media_float(self) -> Optional[float]:
        try:
            return float(self.media) if self.media is not None else None
        except (ValueError, TypeError):
            return None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MateriaVoti":
        voti_list = [VotoSintetico.from_dict(v) for v in data.get("voti", [])]
        return cls(
            id=data.get("id", 0),
            materia=data.get("materia", ""),
            conteggio_voti=data.get("conteggioVoti", 0),
            media=data.get("media"),
            voti=voti_list,
            raw=data
        )


@dataclass
class VotoDettaglio:
    """Dettaglio completo di una singola valutazione."""
    data: str
    docente: str
    tipologia: str
    valutazione: str
    valutazione_matematica: Optional[str]
    fa_media: bool
    peso: str
    descrizione: str
    nome_materia: str
    id_materia: int
    id_frazione_temporale: int
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def valore_numerico(self) -> Optional[float]:
        try:
            return float(self.valutazione_matematica) if self.valutazione_matematica is not None else None
        except (ValueError, TypeError):
            return None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VotoDettaglio":
        return cls(
            data=data.get("data", ""),
            docente=data.get("docente", ""),
            tipologia=data.get("tipologia", ""),
            valutazione=data.get("valutazione", ""),
            valutazione_matematica=data.get("valutazioneMatematica"),
            fa_media=data.get("faMedia", True),
            peso=data.get("peso", "100%"),
            descrizione=data.get("descrizione", ""),
            nome_materia=data.get("nomeMateria", ""),
            id_materia=data.get("idMateria", 0),
            id_frazione_temporale=data.get("idFrazioneTemporale", 0),
            raw=data
        )


@dataclass
class Assenza:
    """Registrazione di assenza, ritardo o uscita anticipata."""
    id: int
    data: str
    turno: str
    tipo: str
    giustificata: bool
    giustificabile: bool
    ora: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Assenza":
        return cls(
            id=data.get("id", 0),
            data=data.get("data", ""),
            turno=data.get("turno", ""),
            tipo=data.get("tipo", ""),
            giustificata=data.get("giustificata", False),
            giustificabile=data.get("giustificabile", False),
            ora=data.get("ora"),
            raw=data
        )


@dataclass
class Nota:
    """Nota disciplinare o annotazione del registro."""
    id: int
    data: str
    docente: str
    registro_di_classe: bool
    materia: Optional[str]
    tipologia: str
    descrizione: str
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Nota":
        return cls(
            id=data.get("id", 0),
            data=data.get("data", ""),
            docente=data.get("docente", ""),
            registro_di_classe=data.get("registroDiClasse", False),
            materia=data.get("materia"),
            tipologia=data.get("tipologia", ""),
            descrizione=data.get("descrizione", ""),
            raw=data
        )


@dataclass
class ConteggioNotifiche:
    """Conteggio delle notifiche non lette per eventi e bacheche."""
    eventi: int
    bacheche: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConteggioNotifiche":
        return cls(
            eventi=data.get("eventi", 0),
            bacheche=data.get("bacheche", 0)
        )


@dataclass
class Pagamento:
    """Registrazione contributo scolastico / avviso PagoPA."""
    id: str
    tassa: str
    rata: str
    importo: str
    stato_pagamento: str
    modalita_pagamento: Optional[str]
    data_scadenza: Optional[str]
    data_pagamento: Optional[str]
    nome_alunno: Optional[str]
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pagamento":
        return cls(
            id=str(data.get("id", "")),
            tassa=data.get("tassa", ""),
            rata=data.get("rata", ""),
            importo=data.get("importo", ""),
            stato_pagamento=data.get("statoPagamento", ""),
            modalita_pagamento=data.get("modalitaPagamento"),
            data_scadenza=data.get("dataScadenzaRata"),
            data_pagamento=data.get("dataPagamento"),
            nome_alunno=data.get("nomeAlunno"),
            raw=data
        )
